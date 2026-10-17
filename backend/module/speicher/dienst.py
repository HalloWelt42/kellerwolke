"""SpeicherDienst - die Anwendungslogik des Datei-Kerns.

Orchestriert BlobStore (physische Bloecke) und MetadataRepository (logischer
Baum, Versionen, Journal). REST-API und WebDAV rufen ausschliesslich diesen
Dienst, damit ETags und Journal immer konsistent bleiben.
"""

import asyncio
import hashlib
import io
import os
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.adapters.externe_quelle import DateibaumQuelle
from app.adapters.filesystem_blobstore import FilesystemBlobStore
from app.adapters.postgres_metadata import PostgresMetadataRepository
from app.config import EINSTELLUNGEN
from app.inhaltstyp import inhaltstyp_aus_name
from app.io_pool import im_thread
from app.ports import SpeicherNichtVerfuegbar
from module.medien.arten import such_muster


class _ZipStrom:
    """Nimmt die Bytes des ZIP-Schreibers entgegen und gibt sie haeppchenweise weiter.

    Bewusst OHNE seek/tell: fehlen die, schreibt zipfile im Stroemungsmodus und
    springt nie zurueck - genau das erlaubt es, das Archiv auszuliefern, waehrend
    es noch entsteht, statt es erst komplett im Speicher zu bauen.
    """

    def __init__(self) -> None:
        self._teile: list[bytes] = []

    def write(self, daten) -> int:
        self._teile.append(bytes(daten))
        return len(daten)

    def flush(self) -> None:
        pass

    def entnehmen(self) -> bytes:
        if not self._teile:
            return b""
        d = b"".join(self._teile)
        self._teile.clear()
        return d


class ArchivZuGross(Exception):
    """Die ZIP-Auswahl ueberschreitet die konfigurierte Gesamtgroesse."""


def _kopiere_pool(quelle, ziel, fortschritt):
    """Kopiert alle Bloecke aus quelle nach ziel (Struktur erhalten, vorhandene
    ueberspringen). Ruft fortschritt(kopiert, gesamt) auf."""
    quelle_p = Path(quelle)
    ziel_p = Path(ziel)
    dateien = [p for p in quelle_p.rglob("*") if p.is_file()]
    gesamt = len(dateien)
    fortschritt(0, gesamt)
    for i, p in enumerate(dateien, 1):
        ziel_datei = ziel_p / p.relative_to(quelle_p)
        if not ziel_datei.exists():
            ziel_datei.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, ziel_datei)
        fortschritt(i, gesamt)


def _pool_groesse(pfad) -> int:
    """Summe der Dateigroessen unter pfad (Bytes) - fuer die Platzpruefung."""
    return sum(p.stat().st_size for p in Path(pfad).rglob("*") if p.is_file())


def _ist_unterpfad(a, b) -> bool:
    """True, wenn a gleich b ist oder a innerhalb von b liegt (verhindert ein
    Verschieben in sich selbst)."""
    a = os.path.abspath(a)
    b = os.path.abspath(b)
    return a == b or a.startswith(b + os.sep)


def _ist_uuid(wert) -> bool:
    try:
        uuid.UUID(str(wert))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _ist_hash(wert) -> bool:
    return isinstance(wert, str) and len(wert) == 64 and all(
        c in "0123456789abcdef" for c in wert
    )


def _auf_systemplatte(pfad) -> bool:
    """True, wenn pfad (oder sein naechster vorhandener Elternordner) auf
    DERSELBEN Geraete-Nummer wie '/' liegt - also NICHT auf einer eigenen,
    gemounteten Platte. Nur als Erst-Einrichtungs-Schutz gedacht (K12): ein
    fehlender Mount laesst den Pool-Pfad auf die Systemplatte zeigen."""
    try:
        root_dev = os.stat("/").st_dev
    except OSError:
        return False
    p = os.path.abspath(pfad)
    while p and not os.path.exists(p):
        eltern = os.path.dirname(p)
        if eltern == p:
            break
        p = eltern
    try:
        return os.stat(p).st_dev == root_dev
    except OSError:
        return False


def _pool_pruefen_fs(wurzel, soll, tief):
    """Vergleicht den physischen Pool mit dem Soll-Zustand (Liste von
    {besitzer_id, hash, groesse} aus der DB). Laeuft im Thread, weil er ueber die
    ganze Platte geht. Liefert:
      verwaist    - auf der Platte, aber nicht in der DB (Rest abgebrochener
                    Vorgaenge/temp-Dateien); Platz kann zurueck.
      fehlend     - in der DB, aber nicht auf der Platte (echter Verlust).
      beschaedigt - nur bei tief: Inhalt passt nicht zum Hash (Bitfaeule).
    Layout: <wurzel>/<benutzer_id>/<hh>/<hash>. Die Marker-Datei am Wurzel liegt
    nicht in einem Benutzerordner und wird so automatisch uebersprungen."""
    wurzel_p = Path(wurzel)
    soll_map = {(str(b["besitzer_id"]), b["hash"]): int(b["groesse"]) for b in soll}
    gesehen = set()
    verwaist = []
    beschaedigt = []
    geprueft = 0
    for benutzer_dir in (wurzel_p.iterdir() if wurzel_p.is_dir() else []):
        if not benutzer_dir.is_dir():
            continue
        benutzer = benutzer_dir.name
        for datei in benutzer_dir.rglob("*"):
            if not datei.is_file():
                continue
            geprueft += 1
            schluessel = (benutzer, datei.name)
            if schluessel in soll_map:
                gesehen.add(schluessel)
                if tief and hashlib.sha256(datei.read_bytes()).hexdigest() != datei.name:
                    beschaedigt.append(
                        {"besitzer_id": benutzer, "hash": datei.name, "groesse": soll_map[schluessel]}
                    )
            else:
                try:
                    g = datei.stat().st_size
                except OSError:
                    g = 0
                verwaist.append(
                    {"pfad": str(datei), "groesse": g, "besitzer_id": benutzer, "name": datei.name}
                )
    fehlend = [
        {"besitzer_id": b, "hash": h, "groesse": g}
        for (b, h), g in soll_map.items()
        if (b, h) not in gesehen
    ]
    return {"verwaist": verwaist, "fehlend": fehlend, "beschaedigt": beschaedigt, "geprueft": geprueft}


def name_mit_zusatz(name: str, zusatz: str, ist_datei: bool) -> str:
    """Hängt einen Zusatz in Klammern an, bei Dateien vor der Endung: "Bericht (wiederhergestellt).pdf"."""
    stamm, punkt, endung = name.rpartition(".")
    if ist_datei and punkt and stamm:
        return f"{stamm} ({zusatz}).{endung}"
    return f"{name} ({zusatz})"


class ZielUngueltig(ValueError):
    """Der Zielordner ist kein lebender Ordner des Kontos (gelöscht, fremd, keiner)."""


class NameBelegt(Exception):
    """Unter dem Namen liegt im Ordner schon ein Objekt anderer Art (Datei gegen Ordner)."""


class PruefsummeFalsch(Exception):
    """Der angekommene Inhalt hat eine andere Prüfsumme als angekündigt (Übertragung beschädigt)."""


class VorbedingungVerletzt(Exception):
    """Der Stand der Datei passt nicht zur Bedingung des Schreibers (If-Match oder If-None-Match)."""


class Gesperrt(Exception):
    """Eine andere App hält die Bearbeitungssperre der Datei."""

    def __init__(self, sperre: dict) -> None:
        super().__init__(f"Gesperrt von {sperre['app']} bis {sperre['bis']:%H:%M:%S}" + (f" ({sperre['grund']})" if sperre["grund"] else ""))
        self.sperre = sperre


@dataclass(frozen=True)
class Bedingung:
    """Bedingung für das Schreiben einer Datei, geprüft unter Zeilensperre in derselben Transaktion wie das
    Eintragen der Version: so gewinnt von zwei gleichzeitigen Schreibern mit demselben Stand genau einer.

    etag: nur schreiben, wenn die Datei genau diesen Stand hat (If-Match); nur_neu: nur anlegen, nie überschreiben
    (If-None-Match: *)."""

    etag: str | None = None
    nur_neu: bool = False
    zugang_id: str | None = None      # schreibende App: eine Bearbeitungssperre einer anderen App weist ab


@dataclass(frozen=True)
class DateiStand:
    """Eine Datei in genau einer Version: Knoten und Blöcke, festgehalten beim Nachschlagen."""

    knoten: dict
    teile: tuple

    @property
    def groesse(self) -> int:
        return sum(c.get("groesse", 0) for c in self.teile)

    @property
    def eigentuemer(self) -> str:
        return str(self.knoten["besitzer_id"])

    @property
    def etag(self) -> str | None:
        return self.knoten["etag"]


class SpeicherDienst:
    def __init__(self, pool, blobstore) -> None:
        self.pool = pool
        self.blobstore = blobstore
        # Stand der laufenden Datenablage-Verschiebung (in-memory, fuer Polling).
        self.verschiebung = {"status": "leer", "kopiert": 0, "gesamt": 0, "ziel": None,
                             "fehler": None}

    def _datentraeger(self):
        """Gesamt- und Freiplatz des Datentraegers, auf dem der Objekt-Pool
        liegt. Faellt auf den naechsten vorhandenen Ueberordner zurueck."""
        pfad = str(getattr(self.blobstore, "wurzel", "")) or "."
        while pfad and not os.path.exists(pfad):
            eltern = os.path.dirname(pfad)
            if eltern == pfad:
                break
            pfad = eltern
        try:
            du = shutil.disk_usage(pfad or "/")
            return du.total, du.free
        except OSError:
            return None, None

    async def speicher_status(self, besitzer_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            status = await repo.speicher_status(besitzer_id)
        verfuegbar = await self.speicher_erreichbar()
        # Bei abgehaengtem Pool NICHT den freien Platz der Systemplatte zeigen
        # (das wuerde falsche Sicherheit vorgaukeln) - dann keine Zahlen.
        if verfuegbar:
            gesamt, frei = self._datentraeger()
        else:
            gesamt, frei = None, None
        status["gesamt"] = gesamt
        status["frei"] = frei
        status["ort"] = str(getattr(self.blobstore, "wurzel", "")) or None
        status["verfuegbar"] = verfuegbar
        return status

    # --- Favoriten ------------------------------------------------------------

    async def favoriten(self, besitzer_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.favoriten(besitzer_id)

    async def favorit_setzen(self, besitzer_id, knoten_id, an: bool):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                if an:
                    await repo.favorit_setzen(besitzer_id, knoten_id)
                else:
                    await repo.favorit_entfernen(besitzer_id, knoten_id)

    # --- Freigaben (Geteilt) -------------------------------------------------

    async def teilen(self, besitzer_id, knoten_id, ziel_id, rechte):
        """Gibt einen eigenen Knoten an ein Konto frei (nur der Eigentuemer)."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.knoten_holen(knoten_id)
                if not knoten or knoten["besitzer_id"] != besitzer_id or knoten["geloescht"]:
                    return False
                await repo.freigabe_setzen(knoten_id, ziel_id, rechte)
                return True

    async def teilen_entfernen(self, besitzer_id, knoten_id, ziel_id):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.knoten_holen(knoten_id)
                if not knoten or knoten["besitzer_id"] != besitzer_id:
                    return False
                await repo.freigabe_entfernen(knoten_id, ziel_id)
                return True

    async def freigaben(self, besitzer_id, knoten_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["besitzer_id"] != besitzer_id:
                return None
            return await repo.freigaben(knoten_id)

    async def geteilt_mit(self, benutzer_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.geteilt_mit(benutzer_id)

    async def geteilt_kinder(self, leser_id, knoten_id):
        """Kinder eines geteilten Ordners - nur bei Lesezugriff (Eigentuemer oder
        Freigabe auf dem Knoten/einem Vorfahren)."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            if not await repo.lese_zugriff(leser_id, knoten_id):
                return None
            return await repo.kinder_nach_parent(knoten_id)

    # --- Konsistenz / Reparatur ----------------------------------------------

    async def pool_pruefen(self, tief: bool = False) -> dict:
        """Gleicht den physischen Pool mit der DB ab (nur lesend). Liefert
        verwaiste (Platz zurueckgewinnbar), fehlende (echter Verlust) und bei
        tief beschaedigte Bloecke. Laeuft ueber die Platte -> im Thread, der
        Event-Loop bleibt frei."""
        if not await self.speicher_erreichbar():
            raise SpeicherNichtVerfuegbar("Speicher nicht erreichbar - Prüfung abgebrochen")
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            soll = await repo.alle_blobs()
        wurzel = str(getattr(self.blobstore, "wurzel", ""))
        return await asyncio.to_thread(_pool_pruefen_fs, wurzel, soll, tief)

    async def pool_aufraeumen(self) -> dict:
        """Entfernt verwaiste Bloecke und gibt den Platz zurueck. Re-scannt und
        prueft jeden Kandidaten unmittelbar vor dem Loeschen erneut gegen die DB,
        damit ein zwischenzeitlich (durch einen gleichzeitigen Upload) wieder
        referenzierter Block nie geloescht wird."""
        if not await self.speicher_erreichbar():
            raise SpeicherNichtVerfuegbar("Speicher nicht erreichbar - Aufräumen abgebrochen")
        bericht = await self.pool_pruefen()
        entfernt, bytes_frei = 0, 0
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            for o in bericht["verwaist"]:
                # Nur ein plausibler Block (UUID-Ordner + 64-stelliger Hash)
                # koennte ueberhaupt in der DB stehen; temp-Reste oder fremde
                # Dateien sind sicher verwaist. So bricht ein Nicht-UUID-Name
                # auch nie die uuid-Abfrage.
                if _ist_uuid(o["besitzer_id"]) and _ist_hash(o["name"]):
                    if await repo.blob_holen(o["besitzer_id"], o["name"]):
                        continue  # inzwischen wieder referenziert -> behalten
                try:
                    await asyncio.to_thread(os.unlink, o["pfad"])
                    entfernt += 1
                    bytes_frei += o["groesse"]
                except FileNotFoundError:
                    pass
        return {"entfernt": entfernt, "bytes": bytes_frei}

    # --- Speicherort (Datenablage) -------------------------------------------

    async def aktiver_pfad(self) -> str:
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            row = await repo.speicherort_holen()
            return row["pfad"] if row else str(self.blobstore.wurzel)

    # --- Nicht-blockierende Blob-Ein-/Ausgabe --------------------------------
    # Jeder Plattenzugriff laeuft im Thread-Pool mit Zeitlimit, damit eine
    # haengende Platte den Event-Loop nie einfriert (siehe app/io_pool.py).

    def _io_timeout(self, groesse: int = 0) -> float:
        z = EINSTELLUNGEN.io_timeout
        return z + (groesse / EINSTELLUNGEN.io_min_durchsatz if groesse else 0)

    async def blob_put(self, benutzer_id: str, daten: bytes):
        return await im_thread(
            self.blobstore.put, benutzer_id, daten, timeout=self._io_timeout(len(daten))
        )

    async def blob_put_strom(self, benutzer_id: str, quelle, max_bytes: int = 0):
        """Streamendes Ablegen. Die Groesse ist vorab unbekannt, deshalb wird das
        Zeitlimit auf die erlaubte Obergrenze bemessen - eine grosse Datei darf
        lange dauern, ohne dass die Wache zuschlaegt."""
        return await im_thread(
            self.blobstore.put_strom, benutzer_id, quelle, max_bytes,
            timeout=self._io_timeout(max_bytes or EINSTELLUNGEN.max_upload),
        )

    async def blob_get(self, benutzer_id: str, blob_hash: str, groesse: int = 0) -> bytes:
        return await im_thread(
            self.blobstore.get, benutzer_id, blob_hash, timeout=self._io_timeout(groesse)
        )

    async def blob_get_bereich(self, benutzer_id: str, blob_hash: str, start: int,
                               laenge: int) -> bytes:
        """Nur den Ausschnitt holen. Das Zeitlimit bemisst sich an der Ausschnitts-
        groesse, nicht an der Datei - ein kleiner Sprung bleibt schnell."""
        return await im_thread(
            self.blobstore.get_bereich, benutzer_id, blob_hash, start, laenge,
            timeout=self._io_timeout(max(laenge, 0)),
        )

    async def blob_delete(self, benutzer_id: str, blob_hash: str) -> None:
        await im_thread(
            self.blobstore.delete, benutzer_id, blob_hash, timeout=self._io_timeout()
        )

    async def speicher_erreichbar(self) -> bool:
        """Wie verfuegbar(), aber nicht-blockierend mit Zeitlimit."""
        try:
            return await im_thread(self.blobstore.verfuegbar, timeout=EINSTELLUNGEN.io_timeout)
        except SpeicherNichtVerfuegbar:
            return False

    async def speicher_initialisieren(self, standard: str) -> str:
        """Beim Start: aktiven Pool-Pfad + Volume-Marker ermitteln und den
        BlobStore konfigurieren. Quelle der Wahrheit ist die speicherort-Zeile.

        - Bereits eingerichtet (Zeile mit Marker): nur konfigurieren. Ob der Pool
          erreichbar ist, entscheidet danach die Marker-Datei (verfuegbar()).
        - Erst-Einrichtung/Adoption (keine Zeile oder ohne Marker): frischen
          Marker erzeugen, ERST die Marker-Datei schreiben, dann in der DB
          festschreiben - so steht in der DB nie ein Marker ohne zugehoerige Datei.

        K12-Schutz: Ist KELLERWOLKE_POOL_MUSS_EXTERN gesetzt und liegt der Pfad
        beim Erststart noch auf der Systemplatte (Mount fehlt), wird gar nicht
        eingerichtet - sonst saet man den Pool still auf die Root-Platte. Der Pool
        bleibt nicht verfuegbar, bis die Platte da ist; beim naechsten Start wird
        erneut versucht."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            row = await repo.speicherort_holen()

        if row and row.get("marker"):
            self.blobstore.setze_wurzel(row["pfad"], row["marker"])
            return row["pfad"]

        pfad = row["pfad"] if row else standard

        if EINSTELLUNGEN.pool_muss_extern and _auf_systemplatte(pfad):
            self.blobstore.setze_wurzel(pfad, None)
            print(
                f"[kellerwolke] Pool-Pfad {pfad} liegt auf der Systemplatte und "
                "KELLERWOLKE_POOL_MUSS_EXTERN ist gesetzt - Einrichtung verschoben, "
                "warte auf den Mount.",
                flush=True,
            )
            return pfad

        marker = str(uuid.uuid4())
        self.blobstore.setze_wurzel(pfad, marker)
        try:
            self.blobstore.marker_schreiben(marker)
        except OSError:
            # Platte doch nicht beschreibbar/da -> nicht in der DB festschreiben,
            # beim naechsten Start erneut versuchen.
            return pfad
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                await repo.speicherort_setzen(pfad, marker)
        return pfad

    async def datenablage_verschieben(self, ziel: str) -> None:
        """Verschiebt den Objekt-Pool gehaertet auf einen anderen Pfad: validieren,
        kopieren, frischen Marker am Ziel setzen, aktiven Pfad + Marker atomar
        umstellen, Rest nachziehen, Quelle ERST DANN loeschen. Fortschritt steht
        in self.verschiebung.

        Sicherheit: Die Quelle wird erst nach dem vollstaendigen Kopieren
        entfernt - bei einem Absturz mittendrin gehen keine Bloecke verloren
        (sie liegen noch an der Quelle, die DB zeigt im Zweifel noch dorthin).
        Das Ziel bekommt einen frischen Volume-Marker mit eigener Identitaet, die
        Quelle bleibt mit ihrem alten Marker als 'falsches Laufwerk' erkennbar."""
        quelle = os.path.abspath(await self.aktiver_pfad())
        ziel = os.path.abspath(os.path.expanduser(ziel))
        self.verschiebung = {"status": "laeuft", "kopiert": 0, "gesamt": 0, "ziel": ziel,
                             "fehler": None}

        def fort(k, g):
            self.verschiebung["kopiert"] = k
            self.verschiebung["gesamt"] = g

        try:
            if ziel == quelle:
                self.verschiebung["status"] = "fertig"
                return
            # Validierung: Quelle erreichbar, Ziel sinnvoll, genug Platz.
            if not await self.speicher_erreichbar():
                raise SpeicherNichtVerfuegbar("Quelle nicht erreichbar - Verschiebung abgebrochen")
            if _ist_unterpfad(ziel, quelle) or _ist_unterpfad(quelle, ziel):
                raise ValueError("Ziel darf nicht im Quellordner liegen (oder umgekehrt)")
            os.makedirs(ziel, exist_ok=True)
            if not os.access(ziel, os.W_OK):
                raise ValueError("Ziel ist nicht beschreibbar")
            groesse = await asyncio.to_thread(_pool_groesse, quelle)
            frei = await asyncio.to_thread(lambda: shutil.disk_usage(ziel).free)
            if frei < groesse:
                raise ValueError(f"Zu wenig Platz am Ziel ({groesse} benötigt, {frei} frei)")

            # 1. Bestand kopieren (Quelle bleibt waehrenddessen aktiv).
            await asyncio.to_thread(_kopiere_pool, quelle, ziel, fort)
            # 2. Frischen Marker am Ziel anlegen (eigene Laufwerk-Identitaet).
            neuer_marker = str(uuid.uuid4())
            await asyncio.to_thread(FilesystemBlobStore(ziel).marker_schreiben, neuer_marker)
            # 3. Aktiven Pfad + Marker atomar umstellen (neue Uploads -> Ziel).
            async with self.pool.connection() as conn:
                async with conn.transaction():
                    repo = PostgresMetadataRepository(conn)
                    await repo.speicherort_setzen(ziel, neuer_marker)
            self.blobstore.setze_wurzel(ziel, neuer_marker)
            # 4. Waehrend des Kopierens an der Quelle Hinzugekommenes nachziehen
            #    (ueberspringt den schon frischen Marker), dann Quelle entfernen.
            await asyncio.to_thread(_kopiere_pool, quelle, ziel, fort)
            await asyncio.to_thread(shutil.rmtree, quelle, True)
            self.verschiebung["status"] = "fertig"
        except Exception as f:  # noqa: BLE001 - Status fuer das Polling festhalten
            self.verschiebung["status"] = "fehler"
            self.verschiebung["fehler"] = str(f)

    async def papierkorb_leeren(self, besitzer_id):
        """Loescht alle Knoten im Papierkorb endgueltig: Refcounts senken,
        Knoten samt Teilbaum (CASCADE) entfernen, verwaiste Bloecke physisch
        loeschen. Liefert die Zahl entfernter Wurzeln."""
        # Vorab pruefen: ist der Pool nicht erreichbar, gar nicht erst die
        # DB-Zeilen loeschen (sonst blieben verwaiste Bloecke auf der Platte).
        if not await self.speicher_erreichbar():
            raise SpeicherNichtVerfuegbar("Papierkorb kann nicht geleert werden")
        verwaiste = []
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                wurzeln = await repo.papierkorb_wurzeln(besitzer_id)
                if not wurzeln:
                    return 0
                for ref in await repo.blobrefs_im_teilbaum(wurzeln):
                    neu = await repo.blob_refcount_senken(besitzer_id, ref["hash"], ref["n"])
                    if neu is not None and neu <= 0:
                        verwaiste.append(ref["hash"])
                await repo.knoten_hart_loeschen(wurzeln)
                for h in verwaiste:
                    await repo.blob_zeile_loeschen(besitzer_id, h)
                for w in wurzeln:
                    await repo.journal_anhaengen(besitzer_id, w, "entfernt")
                anzahl = len(wurzeln)
        # Erst nach erfolgreichem Commit die Dateien von der Platte nehmen.
        for h in verwaiste:
            await self.blob_delete(str(besitzer_id), h)
        return anzahl

    async def knoten_endgueltig_loeschen(self, besitzer_id, knoten_id):
        """Entfernt einen einzelnen Papierkorb-Knoten samt Teilbaum endgueltig.
        Nur erlaubt fuer eigene, bereits geloeschte Knoten. Gleiche GC-Logik wie
        beim Leeren, aber nur fuer diese eine Wurzel. Liefert True bei Erfolg."""
        if not await self.speicher_erreichbar():
            raise SpeicherNichtVerfuegbar("Knoten kann nicht endgültig gelöscht werden")
        verwaiste = []
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.knoten_holen(knoten_id)
                if not knoten or knoten["besitzer_id"] != besitzer_id or not knoten["geloescht"]:
                    return False
                wurzeln = [knoten_id]
                for ref in await repo.blobrefs_im_teilbaum(wurzeln):
                    neu = await repo.blob_refcount_senken(besitzer_id, ref["hash"], ref["n"])
                    if neu is not None and neu <= 0:
                        verwaiste.append(ref["hash"])
                await repo.knoten_hart_loeschen(wurzeln)
                for h in verwaiste:
                    await repo.blob_zeile_loeschen(besitzer_id, h)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "entfernt")
        # Erst nach erfolgreichem Commit die Dateien von der Platte nehmen.
        for h in verwaiste:
            await self.blob_delete(str(besitzer_id), h)
        return True

    async def ordner_anlegen(self, besitzer_id, parent_id, name):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                if not await repo.ordner_lebt(besitzer_id, parent_id):
                    raise ZielUngueltig("Zielordner nicht gefunden")
                knoten = await repo.ordner_anlegen(besitzer_id, parent_id, name)
                await repo.journal_anhaengen(besitzer_id, knoten["id"], "erstellt")
                return knoten

    async def datei_hochladen(self, besitzer_id, parent_id, name, daten):
        # 1. Block zuerst auf die Platte (inhaltsadressiert). neu sagt, ob dieser
        #    Aufruf den Block erzeugt hat - wichtig fuer die Kompensation unten.
        blob_hash, neu = await self.blob_put(str(besitzer_id), daten)
        return await self._datei_eintragen(
            besitzer_id, parent_id, name, blob_hash, neu, len(daten)
        )

    async def datei_hochladen_strom(self, besitzer_id, parent_id, name, quelle, max_bytes: int = 0,
                                    bedingung: Bedingung | None = None, pruefsumme: str | None = None):
        """Wie datei_hochladen, nimmt den Inhalt aber als Datei-Objekt und streamt
        ihn auf die Platte - der Speicherbedarf haengt NICHT an der Dateigroesse.
        Mit pruefsumme (sha256, hex) wird nur eingetragen, wenn der Inhalt genau
        diese hat; sonst PruefsummeFalsch und der neue Block verschwindet wieder.
        Liefert (knoten, blob_hash, groesse); Hash und Groesse braucht der Aufrufer
        fuer die Indizierung, ohne die Bytes festhalten zu muessen."""
        blob_hash, neu, groesse = await self.blob_put_strom(str(besitzer_id), quelle, max_bytes)
        if pruefsumme is not None and blob_hash != pruefsumme:
            if neu:
                async with self.pool.connection() as conn:
                    rest = await PostgresMetadataRepository(conn).blob_holen(besitzer_id, blob_hash)
                if not rest:
                    await self.blob_delete(str(besitzer_id), blob_hash)
            raise PruefsummeFalsch("Der Inhalt passt nicht zur angegebenen Prüfsumme")
        knoten = await self._datei_eintragen(
            besitzer_id, parent_id, name, blob_hash, neu, groesse, bedingung
        )
        return knoten, blob_hash, groesse

    async def _datei_eintragen(self, besitzer_id, parent_id, name, blob_hash, neu, groesse,
                               bedingung: Bedingung | None = None):
        """Traegt einen bereits geschriebenen Block als Datei-Version ein. Geteilt
        von der Bytes- und der Strom-Variante, damit Idempotenz, Journal und die
        Kompensation nur an einer Stelle stehen."""
        try:
            async with self.pool.connection() as conn:
                async with conn.transaction():
                    repo = PostgresMetadataRepository(conn)
                    if not await repo.ordner_lebt(besitzer_id, parent_id):
                        raise ZielUngueltig("Zielordner nicht gefunden")
                    # Atomar anlegen/finden (kein Check-then-act-Race).
                    knoten = await repo.datei_upsert(besitzer_id, parent_id, name)
                    if knoten["typ"] != "datei":
                        raise NameBelegt(f"{name} ist ein Ordner")
                    war_neu = knoten["eingefuegt"]
                    # Die Zeile ist ab hier bis zum Ende der Transaktion gesperrt (ON CONFLICT DO UPDATE),
                    # der gelesene ETag ist also der gültige Stand.
                    if bedingung and bedingung.nur_neu and not war_neu:
                        raise VorbedingungVerletzt("Die Datei gibt es schon")
                    if bedingung and bedingung.etag is not None and (war_neu or knoten["etag"] != bedingung.etag):
                        raise VorbedingungVerletzt("Die Datei wurde inzwischen geändert")
                    if bedingung and bedingung.zugang_id and not war_neu:
                        fremd = await repo.fremde_sperre(knoten["id"], bedingung.zugang_id)
                        if fremd:
                            raise Gesperrt(fremd)
                    # Idempotenz: identischer Inhalt wie aktuelle Version -> No-Op.
                    if not war_neu and knoten["aktuelle_version_id"]:
                        aktuell = await repo.version_holen(knoten["aktuelle_version_id"])
                        if aktuell and aktuell["inhalt_hash"] == blob_hash:
                            return await repo.knoten_holen(knoten["id"])
                    await repo.blob_erhoehen(besitzer_id, blob_hash, groesse)
                    version = await repo.version_anlegen(knoten["id"], groesse, blob_hash, besitzer_id)
                    await repo.chunk_anlegen(version["id"], 0, blob_hash, groesse)
                    # ETag pro Version (eindeutig), nicht der reine Inhalts-Hash:
                    # bei Dedup haetten sonst verschiedene Knoten denselben ETag.
                    await repo.knoten_setzen_version(knoten["id"], version["id"], str(version["id"]))
                    await repo.journal_anhaengen(
                        besitzer_id, knoten["id"], "erstellt" if war_neu else "geaendert", version["id"]
                    )
                    return await repo.knoten_holen(knoten["id"])
        except Exception:
            # Kompensation: nur einen in DIESEM Aufruf neu geschriebenen, jetzt
            # unreferenzierten Block entfernen (die Transaktion wurde zurueckgerollt).
            if neu:
                async with self.pool.connection() as conn:
                    repo = PostgresMetadataRepository(conn)
                    rest = await repo.blob_holen(besitzer_id, blob_hash)
                if not rest:
                    # Beste-Muehe-Aufraeumung: ein Zeitlimit hier darf den
                    # urspruenglichen Fehler nicht verdecken (verwaister Block
                    # wird spaeter von der Konsistenzpruefung gefunden).
                    try:
                        await self.blob_delete(str(besitzer_id), blob_hash)
                    except SpeicherNichtVerfuegbar:
                        pass
            raise

    async def inhaltstyp(self, knoten) -> str:
        """Inhaltstyp für die Auslieferung: gespeichert (von der schreibenden App) oder aus dem Namen."""
        async with self.pool.connection() as conn:
            typ = await PostgresMetadataRepository(conn).inhaltstyp(knoten["id"])
        return typ or inhaltstyp_aus_name(knoten["name"])

    # --- Lesen: ein Weg für eigene und geteilte Dateien ----------------------------------------------------------

    async def _stand(self, repo, knoten) -> DateiStand | None:
        if not knoten or knoten["typ"] != "datei" or knoten["geloescht"] or not knoten["aktuelle_version_id"]:
            return None
        teile = await repo.chunks(knoten["aktuelle_version_id"])
        return DateiStand(knoten=knoten, teile=tuple(teile))

    async def eigene_datei(self, besitzer_id, knoten_id) -> DateiStand | None:
        """Stand einer lebenden Datei des Kontos, ohne den Inhalt zu lesen - sonst None."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["besitzer_id"] != besitzer_id:
                return None
            return await self._stand(repo, knoten)

    async def lesbare_datei(self, leser_id, knoten_id) -> DateiStand | None:
        """Stand einer lebenden Datei, die das Konto lesen darf: eigene oder freigegebene (am Knoten oder einem
        Vorfahren) - sonst None."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            if not await repo.lese_zugriff(leser_id, knoten_id):
                return None
            return await self._stand(repo, await repo.knoten_holen(knoten_id))

    async def stand_stroemen(self, stand: DateiStand, start: int = 0, laenge: int = -1,
                             stueck: int = 1024 * 1024):
        """Inhalt eines Stands stückweise, aus dem Pool des Eigentümers. Der Stand hält die Version fest: wer den Kopf
        mit ETag bekommen hat, bekommt auch genau diesen Inhalt, selbst wenn inzwischen eine neue Version kam."""
        ende = stand.groesse if laenge < 0 else min(start + laenge, stand.groesse)
        pos = 0
        for c in stand.teile:
            cg = c.get("groesse", 0)
            c_start, c_ende = pos, pos + cg
            pos = c_ende
            if c_ende <= start:
                continue
            if c_start >= ende:
                break
            offen, bis = max(0, start - c_start), min(cg, ende - c_start)
            # Auch innerhalb eines Blocks in Häppchen: ein großer Block landet nie am Stück im Speicher.
            while offen < bis:
                nun = min(stueck, bis - offen)
                yield await self.blob_get_bereich(stand.eigentuemer, c["blob_hash"], offen, nun)
                offen += nun

    async def stand_pfad(self, stand: DateiStand) -> str | None:
        """Lokaler Pfad des Inhalts - oder None, wenn er aus mehreren Blöcken besteht oder der Speicher keine Pfade
        kennt. Nur für Werkzeuge, die zwingend eine echte Datei brauchen (Bild- und Videobearbeitung lesen daraus
        gezielt, statt dass die Datei in den Speicher kommt); der Aufrufer MUSS None vertragen."""
        holen = getattr(self.blobstore, "pfad", None)
        if holen is None or len(stand.teile) != 1:
            return None
        return await im_thread(holen, stand.eigentuemer, stand.teile[0]["blob_hash"], timeout=EINSTELLUNGEN.io_timeout)

    async def datei_stroemen(self, besitzer_id, knoten_id, start: int = 0, laenge: int = -1,
                             stueck: int = 1024 * 1024):
        """Eigene Datei stückweise (ZIP, WebDAV); wirft FileNotFoundError, wenn es sie nicht gibt."""
        stand = await self.eigene_datei(besitzer_id, knoten_id)
        if stand is None:
            raise FileNotFoundError("Datei nicht gefunden")
        async for brocken in self.stand_stroemen(stand, start, laenge, stueck):
            yield brocken

    async def datei_lesen(self, besitzer_id, knoten_id) -> bytes:
        """Eigene Datei am Stück - nur für kleine Inhalte; ausgeliefert wird immer über stand_stroemen."""
        return b"".join([b async for b in self.datei_stroemen(besitzer_id, knoten_id)])

    async def _datei_groesse(self, knoten):
        g = knoten.get("groesse")
        return g if g is not None else await self.groesse(knoten)

    async def zip_plan(self, besitzer_id, ids):
        """Sammelt die Archiv-Eintraege und prueft die Groessengrenze.

        Laeuft ausschliesslich ueber die Metadaten - es wird keine einzige Datei
        angefasst. Liefert die Liste (archivpfad, knoten_id | None), wobei None
        einen Verzeichniseintrag meint.
        """
        eintraege = []  # (archivpfad, knoten_id | None); None = Verzeichniseintrag
        gesamt = 0

        async def sammeln(knoten, prefix):
            nonlocal gesamt
            if knoten["typ"] == "datei":
                gesamt += await self._datei_groesse(knoten)
                if gesamt > EINSTELLUNGEN.max_zip:
                    raise ArchivZuGross()
                eintraege.append((prefix + knoten["name"], knoten["id"]))
            elif knoten["typ"] == "ordner":
                unter = prefix + knoten["name"] + "/"
                eintraege.append((unter, None))
                for kind in await self.kinder(besitzer_id, knoten["id"]):
                    await sammeln(kind, unter)

        # dict.fromkeys entdoppelt mehrfach uebergebene IDs (kein Doppel-Pack).
        for kid in dict.fromkeys(ids):
            knoten = await self.knoten_des_nutzers(besitzer_id, kid)
            if not knoten or knoten["geloescht"] or knoten["typ"] not in ("datei", "ordner"):
                continue
            await sammeln(knoten, "")

        return eintraege

    async def zip_stroemen(self, besitzer_id, ids):
        """Packt die Knoten in ein ZIP und gibt es STUECKWEISE heraus.

        Weder das Archiv noch eine einzelne Datei landen dabei vollstaendig im
        Speicher: die Dateien kommen haeppchenweise herein und das fertige Archiv
        geht haeppchenweise hinaus. Damit sind auch grosse Auswahlen moeglich.

        Wirft ArchivZuGross, wenn die Auswahl die eingestellte Grenze sprengt -
        das ist jetzt reine Richtlinie, kein Speicherschutz mehr.
        """
        eintraege = await self.zip_plan(besitzer_id, ids)
        if not eintraege:
            return

        belegt: set[str] = set()

        def eindeutig(pfad: str) -> str:
            # Gleiche Archivpfade (z.B. zwei 'bericht.txt' aus verschiedenen
            # Ordnern) wuerden sich beim Entpacken ueberschreiben - durchnummerieren.
            if pfad not in belegt:
                belegt.add(pfad)
                return pfad
            stamm, punkt, endung = pfad.rpartition(".")
            basis, suffix = (stamm, "." + endung) if punkt else (pfad, "")
            n = 2
            while f"{basis} ({n}){suffix}" in belegt:
                n += 1
            neu = f"{basis} ({n}){suffix}"
            belegt.add(neu)
            return neu

        strom = _ZipStrom()
        geschrieben = 0
        zf = zipfile.ZipFile(strom, "w", zipfile.ZIP_DEFLATED)
        try:
            for archivpfad, knoten_id in eintraege:
                if knoten_id is None:
                    zf.writestr(eindeutig(archivpfad), b"")  # (leerer) Ordner
                    geschrieben += 1
                    if (teil := strom.entnehmen()):
                        yield teil
                    continue
                try:
                    # Erst den Eintrag oeffnen, wenn die Datei wirklich da ist -
                    # sonst bliebe ein halber Eintrag im Archiv stehen.
                    haeppchen = self.datei_stroemen(besitzer_id, knoten_id)
                    erstes = await anext(haeppchen, b"")
                except FileNotFoundError:
                    continue  # waehrend des Packens entfernt (TOCTOU): ueberspringen
                with zf.open(eindeutig(archivpfad), "w") as ziel:
                    if erstes:
                        ziel.write(erstes)
                        if (teil := strom.entnehmen()):
                            yield teil
                    async for brocken in haeppchen:
                        ziel.write(brocken)
                        # Nach jedem Stueck herausgeben: so waechst weder das
                        # Archiv noch die Datei im Speicher mit.
                        if (teil := strom.entnehmen()):
                            yield teil
                geschrieben += 1
                if (teil := strom.entnehmen()):
                    yield teil
        finally:
            zf.close()
        if geschrieben:
            if (teil := strom.entnehmen()):
                yield teil  # Zentralverzeichnis am Ende

    async def als_zip(self, besitzer_id, ids):
        """Wie zip_stroemen, nur am Stueck - fuer Aufrufer, die alles auf einmal
        brauchen (Tests). Liefert None, wenn nichts zu packen ist. Fuer die
        Auslieferung bitte zip_stroemen nehmen, sonst liegt das ganze Archiv im
        Speicher."""
        teile = [t async for t in self.zip_stroemen(besitzer_id, ids)]
        return b"".join(teile) if teile else None

    async def kinder(self, besitzer_id, parent_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.kinder(besitzer_id, parent_id)

    async def medien_im_baum(self, besitzer_id):
        """Alle lebenden Mediendateien des Kontos im ganzen Baum, je mit Ordnerkette und Versionsstand."""
        async with self.pool.connection() as conn:
            return await PostgresMetadataRepository(conn).alle_dateien(besitzer_id, such_muster())

    async def knoten_des_nutzers(self, besitzer_id, knoten_id):
        """Liefert den Knoten nur, wenn er dem Nutzer gehoert - sonst None."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
        if not knoten or knoten["besitzer_id"] != besitzer_id:
            return None
        return knoten

    async def knoten_per_pfad(self, besitzer_id, pfad):
        """Loest einen logischen Pfad (z.B. 'Dok/bericht.txt') zum Knoten auf.
        Leerer Pfad liefert None (= Wurzel). Unbekannter Pfad liefert None."""
        teile = [t for t in pfad.split("/") if t]
        parent, knoten = None, None
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            for teil in teile:
                knoten = await repo.knoten_finden(besitzer_id, parent, teil)
                if not knoten:
                    return None
                parent = knoten["id"]
        return knoten

    async def externe_quelle_anlegen(self, besitzer_id, parent_id, name, extern_pfad):
        """Haengt einen bestehenden Verzeichnisbaum read-only als 'extern'-Knoten
        ein (Admin-Funktion). Nichts wird kopiert; gelesen wird spaeter direkt."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.extern_anlegen(besitzer_id, parent_id, name, extern_pfad)
                await repo.journal_anhaengen(besitzer_id, knoten["id"], "erstellt")
                return knoten

    async def _externe_quelle(self, besitzer_id, knoten_id):
        knoten = await self.knoten_des_nutzers(besitzer_id, knoten_id)
        if (
            not knoten
            or knoten["geloescht"]
            or knoten["typ"] != "extern"
            or not knoten["extern_pfad"]
        ):
            return None
        return DateibaumQuelle(knoten["extern_pfad"])

    async def externe_kinder(self, besitzer_id, knoten_id, unterpfad=""):
        quelle = await self._externe_quelle(besitzer_id, knoten_id)
        if quelle is None:
            return None
        return await im_thread(quelle.auflisten, unterpfad, timeout=EINSTELLUNGEN.io_timeout)

    async def externe_datei(self, besitzer_id, knoten_id, unterpfad):
        """Quelle und Eintrag einer Datei in einer eigenen externen Quelle - None, wenn der Knoten keine ist.
        Wirft FileNotFoundError, PermissionError oder IsADirectoryError für den Unterpfad."""
        quelle = await self._externe_quelle(besitzer_id, knoten_id)
        if quelle is None:
            return None
        eintrag = await im_thread(quelle.info, unterpfad, timeout=EINSTELLUNGEN.io_timeout)
        if eintrag.ist_ordner:
            raise IsADirectoryError(unterpfad)
        return quelle, eintrag

    async def extern_stroemen(self, quelle, unterpfad, start: int = 0, laenge: int = -1,
                              stueck: int = 1024 * 1024, gesamt: int = 0):
        """Inhalt einer externen Datei stückweise; jedes Stück mit Zeitlimit, damit eine hängende Platte nichts
        einfriert."""
        ende = gesamt if laenge < 0 else start + laenge
        pos = start
        while pos < ende:
            nun = min(stueck, ende - pos)
            brocken = await im_thread(quelle.bereich_lesen, unterpfad, pos, nun, timeout=self._io_timeout(nun))
            if not brocken:
                break
            yield brocken
            pos += len(brocken)

    async def groesse(self, knoten) -> int:
        if knoten["typ"] != "datei" or not knoten["aktuelle_version_id"]:
            return 0
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            version = await repo.version_holen(knoten["aktuelle_version_id"])
        return version["groesse"] if version else 0

    async def versionen(self, besitzer_id, knoten_id):
        if not await self.knoten_des_nutzers(besitzer_id, knoten_id):
            return None
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.versionen(knoten_id)

    async def papierkorb(self, besitzer_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.papierkorb(besitzer_id)

    async def lebender_knoten(self, besitzer_id, knoten_id):
        """Der Knoten, wenn er dem Konto gehört und nicht im Papierkorb liegt - sonst None."""
        knoten = await self.knoten_des_nutzers(besitzer_id, knoten_id)
        return knoten if knoten and not knoten["geloescht"] else None

    async def umbenennen(self, besitzer_id, knoten_id, neuer_name):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.knoten_holen(knoten_id)
                if not knoten or knoten["besitzer_id"] != besitzer_id or knoten["geloescht"]:
                    raise ZielUngueltig("Nicht gefunden")
                await repo.knoten_umbenennen(besitzer_id, knoten_id, neuer_name)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "verschoben")
                return await repo.knoten_holen(knoten_id)

    async def _ziel_pruefen(self, repo, besitzer_id, knoten_id, neuer_parent) -> None:
        """Ziel eines Verschiebens: die Wurzel oder ein lebender eigener Ordner, nicht im eigenen Teilbaum."""
        if not await repo.ordner_lebt(besitzer_id, neuer_parent):
            raise ZielUngueltig("Ungültiges Ziel")
        if neuer_parent is not None and await repo.ist_im_teilbaum(knoten_id, neuer_parent):
            raise ZielUngueltig("Das Ziel liegt im eigenen Teilbaum")

    async def verschieben(self, besitzer_id, knoten_id, neuer_parent):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                alt = await repo.knoten_holen(knoten_id)
                if not alt or alt["besitzer_id"] != besitzer_id or alt["geloescht"]:
                    raise ZielUngueltig("Nicht gefunden")
                await self._ziel_pruefen(repo, besitzer_id, knoten_id, neuer_parent)
                await repo.knoten_verschieben(besitzer_id, knoten_id, neuer_parent)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "verschoben", von_parent_id=alt["parent_id"])
                return await repo.knoten_holen(knoten_id)

    async def umziehen(self, besitzer_id, knoten_id, neuer_parent, neuer_name):
        """Verschieben und/oder Umbenennen atomar in EINER Transaktion (fuer
        WebDAV-MOVE), damit nie ein halb angewandter Zustand entsteht."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.knoten_holen(knoten_id)
                if not knoten or knoten["besitzer_id"] != besitzer_id or knoten["geloescht"]:
                    return None
                await self._ziel_pruefen(repo, besitzer_id, knoten_id, neuer_parent)
                if neuer_name and neuer_name != knoten["name"]:
                    await repo.knoten_umbenennen(besitzer_id, knoten_id, neuer_name)
                if neuer_parent != knoten["parent_id"]:
                    await repo.knoten_verschieben(besitzer_id, knoten_id, neuer_parent)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "verschoben", von_parent_id=knoten["parent_id"])
                return await repo.knoten_holen(knoten_id)

    async def loeschen(self, besitzer_id, knoten_id):
        """Legt einen lebenden Knoten samt Teilbaum in den Papierkorb; schon Gelöschtes bleibt unberührt."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.knoten_holen(knoten_id)
                if not knoten or knoten["besitzer_id"] != besitzer_id or knoten["geloescht"]:
                    return
                await repo.knoten_loeschen(besitzer_id, knoten_id)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "geloescht")

    async def wiederherstellen(self, besitzer_id, knoten_id):
        """Holt eine Papierkorb-Wurzel samt Teilbaum zurück. Liegt der Elternordner selbst noch im Papierkorb (oder
        gibt es ihn nicht mehr), kommt sie nach "Meine Dateien"; ist der Name dort vergeben, mit Zusatz."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.knoten_holen(knoten_id)
                if (not knoten or knoten["besitzer_id"] != besitzer_id or not knoten["geloescht"]
                        or knoten["geloescht_wurzel"] != knoten["id"]):
                    return None
                ziel = knoten["parent_id"]
                if ziel is not None:
                    eltern = await repo.knoten_holen(ziel)
                    if not eltern or eltern["geloescht"]:
                        ziel = None
                name = knoten["name"]
                n = 1
                while await repo.knoten_finden(besitzer_id, ziel, name):
                    name = name_mit_zusatz(knoten["name"], "wiederhergestellt" if n == 1 else f"wiederhergestellt {n}",
                                           knoten["typ"] == "datei")
                    n += 1
                await repo.knoten_wiederherstellen(besitzer_id, knoten_id, name, ziel)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "erstellt")
                return await repo.knoten_holen(knoten_id)

    async def journal_stand(self, besitzer_id) -> int:
        async with self.pool.connection() as conn:
            return (await PostgresMetadataRepository(conn).journal_grenzen(besitzer_id))[1]

    async def pfad_aufloesen(self, besitzer_id, pfad: str) -> tuple[list[dict], dict] | None:
        """Ein Pfad im eigenen Baum ("Apps/Probe/notiz.txt", Groß- und Kleinschreibung egal wie bei den Namen) zu
        (Ordnerkette darüber als {id, name}, Knoten). None, wenn ein Teil fehlt oder unterwegs kein Ordner ist."""
        teile = [t for t in pfad.split("/") if t]
        if not teile:
            return None
        kette: list[dict] = []
        eltern = None
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            for i, name in enumerate(teile):
                knoten = await repo.knoten_finden(besitzer_id, eltern, name)
                if knoten is None:
                    return None
                if i < len(teile) - 1:
                    if knoten["typ"] != "ordner":
                        return None
                    kette.append({"id": knoten["id"], "name": knoten["name"]})
                eltern = knoten["id"]
        return kette, knoten

    async def ahnen(self, besitzer_id, knoten_id) -> list[dict] | None:
        """Ordnerkette über einem eigenen Knoten, von oben bis zum Elternordner ({id, name}) - None, wenn er nicht
        dem Konto gehört."""
        if not await self.knoten_des_nutzers(besitzer_id, knoten_id):
            return None
        async with self.pool.connection() as conn:
            return await PostgresMetadataRepository(conn).ahnen(knoten_id)

    async def journal_seit(self, besitzer_id, seit_seq=0, anzahl: int = 1000):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.journal_seit(besitzer_id, seit_seq, anzahl)

    async def journal_im_ordner(self, besitzer_id, ordner_id, seit_seq: int, anzahl: int) -> dict:
        """Änderungen unter einem Ordner seit seq, dazu bis (letzte gelieferte oder aktuelle seq) und luecke (das
        Journal reicht nicht mehr bis seit zurück: der Beobachter muss den Ordner neu lesen)."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            kleinste, groesste = await repo.journal_grenzen(besitzer_id)
            eintraege = await repo.journal_im_ordner(besitzer_id, ordner_id, seit_seq, anzahl)
        luecke = 0 < seit_seq < kleinste - 1
        bis = eintraege[-1]["seq"] if len(eintraege) == anzahl else max(seit_seq, groesste)
        return {"eintraege": eintraege, "bis": bis, "luecke": luecke}

    async def journal_aufraeumen(self, tage: int) -> int:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                return await PostgresMetadataRepository(conn).journal_aufraeumen(tage)
