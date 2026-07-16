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
from pathlib import Path

from app.adapters.externe_quelle import DateibaumQuelle
from app.adapters.filesystem_blobstore import FilesystemBlobStore
from app.adapters.postgres_metadata import PostgresMetadataRepository
from app.config import EINSTELLUNGEN
from app.io_pool import im_thread
from app.ports import SpeicherNichtVerfuegbar


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
                if not knoten or knoten["besitzer_id"] != besitzer_id:
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

    async def geteilt_datei_lesen(self, leser_id, knoten_id):
        """Inhalt einer geteilten Datei - nur bei Lesezugriff. Gelesen wird aus
        dem Pool des EIGENTUEMERS (nicht des Lesers)."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            if not await repo.lese_zugriff(leser_id, knoten_id):
                return None
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
                return None
            teile = await repo.chunks(knoten["aktuelle_version_id"])
            eigentuemer = str(knoten["besitzer_id"])
        bloecke = [await self.blob_get(eigentuemer, c["blob_hash"], c.get("groesse", 0)) for c in teile]
        return (knoten, b"".join(bloecke))

    async def geteilt_datei_kopf(self, leser_id, knoten_id):
        """Prueft den Lesezugriff und liefert (knoten, groesse) - ohne Inhalt.
        Damit kann die Auslieferung streamen, statt erst alles zu laden."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            if not await repo.lese_zugriff(leser_id, knoten_id):
                return None
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
                return None
            teile = await repo.chunks(knoten["aktuelle_version_id"])
        return knoten, sum(c.get("groesse", 0) for c in teile)

    async def geteilt_datei_stroemen(self, leser_id, knoten_id, start: int = 0,
                                     laenge: int = -1, stueck: int = 1024 * 1024):
        """Stueckweiser Inhalt einer geteilten Datei - nur bei Lesezugriff.
        Gelesen wird aus dem Pool des EIGENTUEMERS (nicht des Lesers)."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            if not await repo.lese_zugriff(leser_id, knoten_id):
                raise PermissionError("Kein Lesezugriff")
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
                raise FileNotFoundError("Datei nicht gefunden")
            teile = await repo.chunks(knoten["aktuelle_version_id"])
            eigentuemer = str(knoten["besitzer_id"])
        gesamt = sum(c.get("groesse", 0) for c in teile)
        ende = gesamt if laenge < 0 else min(start + laenge, gesamt)
        pos = 0
        for c in teile:
            cg = c.get("groesse", 0)
            c_start, c_ende = pos, pos + cg
            pos = c_ende
            if c_ende <= start:
                continue
            if c_start >= ende:
                break
            offen, bis = max(0, start - c_start), min(cg, ende - c_start)
            while offen < bis:
                nun = min(stueck, bis - offen)
                yield await self.blob_get_bereich(eigentuemer, c["blob_hash"], offen, nun)
                offen += nun

    # --- Konsistenz / Reparatur ----------------------------------------------

    async def pool_pruefen(self, tief: bool = False) -> dict:
        """Gleicht den physischen Pool mit der DB ab (nur lesend). Liefert
        verwaiste (Platz zurueckgewinnbar), fehlende (echter Verlust) und bei
        tief beschaedigte Bloecke. Laeuft ueber die Platte -> im Thread, der
        Event-Loop bleibt frei."""
        if not await self.speicher_erreichbar():
            raise SpeicherNichtVerfuegbar("Speicher nicht erreichbar - Pruefung abgebrochen")
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
            raise SpeicherNichtVerfuegbar("Speicher nicht erreichbar - Aufraeumen abgebrochen")
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
                raise ValueError(f"Zu wenig Platz am Ziel ({groesse} benoetigt, {frei} frei)")

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
            raise SpeicherNichtVerfuegbar("Knoten kann nicht endgueltig geloescht werden")
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
        # Erst nach erfolgreichem Commit die Dateien von der Platte nehmen.
        for h in verwaiste:
            await self.blob_delete(str(besitzer_id), h)
        return True

    async def ordner_anlegen(self, besitzer_id, parent_id, name):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
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

    async def datei_hochladen_strom(self, besitzer_id, parent_id, name, quelle, max_bytes: int = 0):
        """Wie datei_hochladen, nimmt den Inhalt aber als Datei-Objekt und streamt
        ihn auf die Platte - der Speicherbedarf haengt NICHT an der Dateigroesse.
        Liefert (knoten, blob_hash, groesse); Hash und Groesse braucht der Aufrufer
        fuer die Indizierung, ohne die Bytes festhalten zu muessen."""
        blob_hash, neu, groesse = await self.blob_put_strom(str(besitzer_id), quelle, max_bytes)
        knoten = await self._datei_eintragen(
            besitzer_id, parent_id, name, blob_hash, neu, groesse
        )
        return knoten, blob_hash, groesse

    async def _datei_eintragen(self, besitzer_id, parent_id, name, blob_hash, neu, groesse):
        """Traegt einen bereits geschriebenen Block als Datei-Version ein. Geteilt
        von der Bytes- und der Strom-Variante, damit Idempotenz, Journal und die
        Kompensation nur an einer Stelle stehen."""
        try:
            async with self.pool.connection() as conn:
                async with conn.transaction():
                    repo = PostgresMetadataRepository(conn)
                    # Atomar anlegen/finden (kein Check-then-act-Race).
                    knoten = await repo.datei_upsert(besitzer_id, parent_id, name)
                    war_neu = knoten["eingefuegt"]
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

    async def datei_groesse(self, besitzer_id, knoten_id) -> int:
        """Groesse der aktuellen Version, OHNE den Inhalt zu lesen. Der Range-
        Kopf braucht die Gesamtgroesse - dafuer darf die Datei nicht angefasst
        werden."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
                raise FileNotFoundError("Datei nicht gefunden")
            version = await repo.version_holen(knoten["aktuelle_version_id"])
        if not version:
            raise FileNotFoundError("Datei ohne Version")
        return version["groesse"]

    async def datei_bereich_lesen(self, besitzer_id, knoten_id, start: int, laenge: int) -> bytes:
        """Liest NUR den angeforderten Ausschnitt. Angefasst werden ausschliesslich
        die Bloecke, die den Bereich ueberlappen - ein Sprung im Player holt damit
        nicht mehr die ganze Datei von der Platte."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
                raise FileNotFoundError("Datei nicht gefunden")
            teile = await repo.chunks(knoten["aktuelle_version_id"])
        ende = start + laenge
        stuecke, pos = [], 0
        for c in teile:
            cg = c.get("groesse", 0)
            c_start, c_ende = pos, pos + cg
            pos = c_ende
            if c_ende <= start:
                continue  # liegt komplett vor dem Bereich
            if c_start >= ende:
                break  # ab hier liegt alles dahinter
            von = max(0, start - c_start)
            bis = min(cg, ende - c_start)
            stuecke.append(
                await self.blob_get_bereich(str(besitzer_id), c["blob_hash"], von, bis - von)
            )
        return b"".join(stuecke)

    async def datei_pfad(self, besitzer_id, knoten_id):
        """Lokaler Pfad der Datei - oder None.

        Nur fuer Werkzeuge, die zwingend eine echte Datei brauchen (ffmpeg liest
        daraus selbst gezielt einzelne Stellen, statt dass wir sie in den Speicher
        holen). Liefert None, wenn die Datei aus mehreren Bloecken besteht oder
        der Speicher gar keine Pfade kennt - der Aufrufer MUSS das vertragen.
        """
        holen = getattr(self.blobstore, "pfad", None)
        if holen is None:
            return None
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
                raise FileNotFoundError("Datei nicht gefunden")
            teile = await repo.chunks(knoten["aktuelle_version_id"])
        if len(teile) != 1:
            return None  # zusammengesetzt: es gibt keine eine Datei
        return await im_thread(
            holen, str(besitzer_id), teile[0]["blob_hash"], timeout=EINSTELLUNGEN.io_timeout
        )

    async def datei_stroemen(self, besitzer_id, knoten_id, start: int = 0, laenge: int = -1,
                             stueck: int = 1024 * 1024):
        """Liefert den Inhalt STUECKWEISE als Generator - der Speicherbedarf bleibt
        bei einem Stueck, egal ob die Datei 1 KB oder 10 GB hat.

        Das ist der einzige Weg, auf dem grosse Dateien ausgeliefert werden
        duerfen: ein Vollpuffer wuerde bei jeder Anfrage die ganze Datei in den
        Speicher holen. laenge=-1 heisst "bis zum Ende".
        """
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
                raise FileNotFoundError("Datei nicht gefunden")
            teile = await repo.chunks(knoten["aktuelle_version_id"])
        gesamt = sum(c.get("groesse", 0) for c in teile)
        ende = gesamt if laenge < 0 else min(start + laenge, gesamt)
        pos = 0
        for c in teile:
            cg = c.get("groesse", 0)
            c_start, c_ende = pos, pos + cg
            pos = c_ende
            if c_ende <= start:
                continue  # liegt komplett vor dem Bereich
            if c_start >= ende:
                break  # ab hier liegt alles dahinter
            von = max(0, start - c_start)
            bis = min(cg, ende - c_start)
            # Innerhalb des Blocks in Haeppchen lesen, damit auch ein einzelner
            # grosser Block nie am Stueck im Speicher landet.
            offen = von
            while offen < bis:
                nun = min(stueck, bis - offen)
                yield await self.blob_get_bereich(str(besitzer_id), c["blob_hash"], offen, nun)
                offen += nun

    async def datei_lesen(self, besitzer_id, knoten_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
                raise FileNotFoundError("Datei nicht gefunden")
            teile = await repo.chunks(knoten["aktuelle_version_id"])
        bloecke = [
            await self.blob_get(str(besitzer_id), c["blob_hash"], c.get("groesse", 0))
            for c in teile
        ]
        return b"".join(bloecke)

    async def _datei_groesse(self, knoten):
        g = knoten.get("groesse")
        return g if g is not None else await self.groesse(knoten)

    async def als_zip(self, besitzer_id, ids):
        """Packt die angegebenen Knoten in ein ZIP und liefert die Bytes.
        Dateien direkt, Ordner rekursiv (auch leere als Verzeichniseintrag). Nur
        eigene, nicht geloeschte Knoten. Liefert None, wenn nichts zu packen ist.
        Wirft ArchivZuGross, wenn die Gesamtgroesse die Grenze sprengt (das ZIP
        entsteht im Speicher - Schutz vor OOM/DoS)."""
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

        if not eintraege:
            return None

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

        puffer = io.BytesIO()
        geschrieben = 0
        with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for archivpfad, knoten_id in eintraege:
                if knoten_id is None:
                    zf.writestr(eindeutig(archivpfad), b"")  # (leerer) Ordner
                    geschrieben += 1
                    continue
                try:
                    inhalt = await self.datei_lesen(besitzer_id, knoten_id)
                except FileNotFoundError:
                    continue  # waehrend des Packens entfernt (TOCTOU): ueberspringen
                zf.writestr(eindeutig(archivpfad), inhalt)
                geschrieben += 1
        return puffer.getvalue() if geschrieben else None

    async def kinder(self, besitzer_id, parent_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.kinder(besitzer_id, parent_id)

    async def dateien_nach_endung(self, besitzer_id, endungen):
        """Alle Dateien des Nutzers im ganzen Baum mit vollem Pfad, gefiltert auf
        Namens-Endungen (z.B. ['%.jpg', '%.png']). Fuer baumweite Ansichten."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.alle_dateien(besitzer_id, endungen)

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
        return quelle.auflisten(unterpfad)

    async def externe_datei_lesen(self, besitzer_id, knoten_id, unterpfad):
        quelle = await self._externe_quelle(besitzer_id, knoten_id)
        if quelle is None:
            return None
        return quelle.lesen(unterpfad)

    @staticmethod
    def _basisname(name: str) -> str:
        """Nur den reinen Dateinamen zulassen - keine Pfadanteile, kein '..'."""
        rein = Path(name).name
        if not rein or rein in (".", ".."):
            raise ValueError("Ungueltiger Name")
        return rein

    def _externer_pfad(self, unterpfad: str, name: str) -> str:
        basis = self._basisname(name)
        unter = (unterpfad or "").strip("/")
        return f"{unter}/{basis}" if unter else basis

    async def externe_datei_schreiben(self, besitzer_id, knoten_id, unterpfad, name, daten):
        """Schreibt eine Datei in eine schreibbare externe Quelle. Liefert False,
        wenn der Knoten keine externe Quelle des Nutzers ist (Isolation)."""
        quelle = await self._externe_quelle(besitzer_id, knoten_id)
        if quelle is None:
            return False
        quelle.schreiben(self._externer_pfad(unterpfad, name), daten)
        return True

    async def externe_datei_schreiben_strom(self, besitzer_id, knoten_id, unterpfad, name,
                                            strom, max_bytes: int = 0):
        """Wie externe_datei_schreiben, streamt den Inhalt aber auf die Quelle,
        statt ihn vorher komplett in den Speicher zu laden."""
        quelle = await self._externe_quelle(besitzer_id, knoten_id)
        if quelle is None:
            return False
        await im_thread(
            quelle.schreiben_strom, self._externer_pfad(unterpfad, name), strom, max_bytes,
            timeout=self._io_timeout(max_bytes or EINSTELLUNGEN.max_upload),
        )
        return True

    async def externe_ordner_anlegen(self, besitzer_id, knoten_id, unterpfad, name):
        quelle = await self._externe_quelle(besitzer_id, knoten_id)
        if quelle is None:
            return False
        quelle.ordner_anlegen(self._externer_pfad(unterpfad, name))
        return True

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

    async def umbenennen(self, besitzer_id, knoten_id, neuer_name):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                await repo.knoten_umbenennen(besitzer_id, knoten_id, neuer_name)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "verschoben")
                return await repo.knoten_holen(knoten_id)

    async def verschieben(self, besitzer_id, knoten_id, neuer_parent):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                if neuer_parent is not None:
                    ziel = await repo.knoten_holen(neuer_parent)
                    if (not ziel or ziel["besitzer_id"] != besitzer_id
                            or ziel["geloescht"] or ziel["typ"] not in ("ordner", "extern")):
                        raise ValueError("Ungueltiges Ziel")
                    # Verschieben in sich selbst oder einen eigenen Nachkommen verbieten.
                    if await repo.ist_im_teilbaum(knoten_id, neuer_parent):
                        raise ValueError("Zyklus: Ziel liegt im eigenen Teilbaum")
                await repo.knoten_verschieben(besitzer_id, knoten_id, neuer_parent)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "verschoben")
                return await repo.knoten_holen(knoten_id)

    async def umziehen(self, besitzer_id, knoten_id, neuer_parent, neuer_name):
        """Verschieben und/oder Umbenennen atomar in EINER Transaktion (fuer
        WebDAV-MOVE), damit nie ein halb angewandter Zustand entsteht."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.knoten_holen(knoten_id)
                if not knoten or knoten["besitzer_id"] != besitzer_id:
                    return None
                if neuer_parent is not None:
                    ziel = await repo.knoten_holen(neuer_parent)
                    if (not ziel or ziel["besitzer_id"] != besitzer_id
                            or ziel["geloescht"] or ziel["typ"] not in ("ordner", "extern")):
                        raise ValueError("Ungueltiges Ziel")
                    if await repo.ist_im_teilbaum(knoten_id, neuer_parent):
                        raise ValueError("Zyklus")
                if neuer_name and neuer_name != knoten["name"]:
                    await repo.knoten_umbenennen(besitzer_id, knoten_id, neuer_name)
                if neuer_parent != knoten["parent_id"]:
                    await repo.knoten_verschieben(besitzer_id, knoten_id, neuer_parent)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "verschoben")
                return await repo.knoten_holen(knoten_id)

    async def loeschen(self, besitzer_id, knoten_id):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                await repo.knoten_loeschen(besitzer_id, knoten_id)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "geloescht")

    async def wiederherstellen(self, besitzer_id, knoten_id):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.knoten_holen(knoten_id)
                if not knoten or knoten["besitzer_id"] != besitzer_id or not knoten["geloescht"]:
                    return None
                name = knoten["name"]
                # Bei Namenskollision mit lebendem Geschwister umbenennen.
                if await repo.knoten_finden(besitzer_id, knoten["parent_id"], name):
                    name = f"{name} (wiederhergestellt)"
                await repo.knoten_wiederherstellen(besitzer_id, knoten_id, name)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "erstellt")
                return await repo.knoten_holen(knoten_id)

    async def journal_seit(self, besitzer_id, seit_seq=0):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.journal_seit(besitzer_id, seit_seq)
