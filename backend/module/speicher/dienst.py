"""SpeicherDienst - die Anwendungslogik des Datei-Kerns.

Orchestriert BlobStore (physische Bloecke) und MetadataRepository (logischer
Baum, Versionen, Journal). REST-API und WebDAV rufen ausschliesslich diesen
Dienst, damit ETags und Journal immer konsistent bleiben.
"""

import asyncio
import os
import shutil
from pathlib import Path

from app.adapters.externe_quelle import DateibaumQuelle
from app.adapters.postgres_metadata import PostgresMetadataRepository


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
        gesamt, frei = self._datentraeger()
        status["gesamt"] = gesamt
        status["frei"] = frei
        status["ort"] = str(getattr(self.blobstore, "wurzel", "")) or None
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
        bloecke = [self.blobstore.get(eigentuemer, c["blob_hash"]) for c in teile]
        return (knoten, b"".join(bloecke))

    # --- Speicherort (Datenablage) -------------------------------------------

    async def aktiver_pfad(self) -> str:
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            row = await repo.speicherort_holen()
            return row["pfad"] if row else str(self.blobstore.wurzel)

    async def aktiver_pfad_initialisieren(self, standard: str) -> str:
        """Beim Start: Speicherort-Zeile anlegen, falls leer; aktiven Pfad
        zurueckgeben (Quelle der Wahrheit fuer die Pool-Wurzel)."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                row = await repo.speicherort_holen()
                if not row:
                    await repo.speicherort_setzen(standard)
                    return standard
                return row["pfad"]

    async def datenablage_verschieben(self, ziel: str) -> None:
        """Verschiebt den Objekt-Pool auf einen anderen Pfad: kopieren, aktiven
        Pfad umstellen, Rest (waehrend des Kopierens Hinzugekommenes) nachziehen,
        Quelle loeschen. Fortschritt steht in self.verschiebung."""
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
            os.makedirs(ziel, exist_ok=True)
            # 1. Bestand kopieren
            await asyncio.to_thread(_kopiere_pool, quelle, ziel, fort)
            # 2. Aktiven Pfad umstellen (neue Uploads landen ab jetzt im Ziel)
            async with self.pool.connection() as conn:
                async with conn.transaction():
                    repo = PostgresMetadataRepository(conn)
                    await repo.speicherort_setzen(ziel)
            self.blobstore.setze_wurzel(ziel)
            # 3. Waehrend des Kopierens Hinzugekommenes nachziehen, dann Quelle weg
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
            self.blobstore.delete(str(besitzer_id), h)
        return anzahl

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
        blob_hash, neu = self.blobstore.put(str(besitzer_id), daten)
        groesse = len(daten)
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
                    self.blobstore.delete(str(besitzer_id), blob_hash)
            raise

    async def datei_lesen(self, besitzer_id, knoten_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
                raise FileNotFoundError("Datei nicht gefunden")
            teile = await repo.chunks(knoten["aktuelle_version_id"])
        bloecke = [self.blobstore.get(str(besitzer_id), c["blob_hash"]) for c in teile]
        return b"".join(bloecke)

    async def kinder(self, besitzer_id, parent_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.kinder(besitzer_id, parent_id)

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
        if not knoten or knoten["typ"] != "extern" or not knoten["extern_pfad"]:
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
