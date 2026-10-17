"""Fortsetzbare Uploads in Teilen.

Ein Telefon verliert die Verbindung, wechselt das Netz oder legt die App schlafen. Damit eine große Datei dann nicht
von vorn beginnt, wird sie in Teilen gesendet: der Upload kennt Ziel, Name und Gesamtgröße, jedes Teil kommt mit
seinem Versatz und wird an eine Datei außerhalb des Blob-Pools angehängt. Wie viel angekommen ist, sagt die Größe
dieser Datei - das gilt auch nach einem Abbruch mitten im Teil oder einem Neustart. Mit dem letzten Byte wird die
Datei wie jeder Upload eingetragen (neue Version bei gleichem Namen), auf Wunsch nur bei passender Prüfsumme.
Ruhende Uploads räumt die tägliche Pflege nach einigen Tagen weg.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from psycopg.rows import dict_row

from app.adapters.postgres_metadata import PostgresMetadataRepository
from module.speicher.dienst import ZielUngueltig


class UploadNichtGefunden(Exception):
    """Gibt es nicht (mehr) oder gehört einem anderen Konto."""


class FalscherVersatz(Exception):
    """Das Teil setzt nicht dort an, wo der Upload steht; `empfangen` sagt, wo es weitergeht."""

    def __init__(self, empfangen: int) -> None:
        super().__init__(f"Weiter ab Byte {empfangen}")
        self.empfangen = empfangen


class UploadLaeuft(Exception):
    """An diesem Upload wird gerade ein anderes Teil angehängt."""


class ZuViel(Exception):
    """Das Teil ginge über die angekündigte Größe hinaus."""


@dataclass(frozen=True)
class Upload:
    id: UUID
    name: str
    parent_id: UUID | None
    groesse: int
    empfangen: int
    pruefsumme: str | None
    erstellt_am: datetime
    zuletzt_am: datetime


class UploadDienst:
    def __init__(self, pool, speicher, wurzel, tage: int = 7) -> None:
        self.pool = pool
        self.speicher = speicher
        self.wurzel = Path(wurzel)
        self.tage = tage
        self._laufend: set[str] = set()

    def _datei(self, besitzer_id, upload_id) -> Path:
        return self.wurzel / str(besitzer_id) / str(upload_id)

    def _empfangen(self, besitzer_id, upload_id) -> int:
        try:
            return self._datei(besitzer_id, upload_id).stat().st_size
        except FileNotFoundError:
            return 0

    def _als_upload(self, zeile: dict) -> Upload:
        return Upload(id=zeile["id"], name=zeile["name"], parent_id=zeile["parent_id"], groesse=zeile["groesse"],
                      empfangen=min(self._empfangen(zeile["besitzer_id"], zeile["id"]), zeile["groesse"]),
                      pruefsumme=zeile["pruefsumme"], erstellt_am=zeile["erstellt_am"], zuletzt_am=zeile["zuletzt_am"])

    async def _zeile(self, besitzer_id, upload_id) -> dict:
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM upload WHERE id=%s AND besitzer_id=%s", (upload_id, besitzer_id))
                zeile = await cur.fetchone()
        if not zeile:
            raise UploadNichtGefunden("Upload nicht gefunden")
        return zeile

    async def anlegen(self, besitzer_id, parent_id, name: str, groesse: int, pruefsumme: str | None) -> Upload:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                if not await PostgresMetadataRepository(conn).ordner_lebt(besitzer_id, parent_id):
                    raise ZielUngueltig("Zielordner nicht gefunden")
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "INSERT INTO upload (besitzer_id, parent_id, name, groesse, pruefsumme) "
                        "VALUES (%s,%s,%s,%s,%s) RETURNING *", (besitzer_id, parent_id, name, groesse, pruefsumme))
                    zeile = await cur.fetchone()
        datei = self._datei(besitzer_id, zeile["id"])
        await asyncio.to_thread(lambda: (datei.parent.mkdir(parents=True, exist_ok=True), datei.touch()))
        return self._als_upload(zeile)

    async def holen(self, besitzer_id, upload_id) -> Upload:
        return self._als_upload(await self._zeile(besitzer_id, upload_id))

    async def liste(self, besitzer_id) -> list[Upload]:
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM upload WHERE besitzer_id=%s ORDER BY erstellt_am", (besitzer_id,))
                return [self._als_upload(z) for z in await cur.fetchall()]

    async def anhaengen(self, besitzer_id, upload_id, versatz: int, strom: AsyncIterator[bytes], max_bytes: int):
        """Hängt ein Teil an. Liefert (Upload, None) oder, mit dem letzten Byte, (Upload, eingetragener Knoten)."""
        schluessel = str(upload_id)
        if schluessel in self._laufend:
            raise UploadLaeuft("An diesem Upload wird gerade ein Teil angehängt")
        self._laufend.add(schluessel)
        try:
            zeile = await self._zeile(besitzer_id, upload_id)
            empfangen = self._empfangen(besitzer_id, upload_id)
            if versatz != empfangen:
                raise FalscherVersatz(empfangen)
            datei = self._datei(besitzer_id, upload_id)
            ziel = await asyncio.to_thread(open, datei, "ab")
            try:
                async for stueck in strom:
                    if empfangen + len(stueck) > zeile["groesse"]:
                        raise ZuViel("Mehr als angekündigt")
                    await asyncio.to_thread(ziel.write, stueck)
                    empfangen += len(stueck)
            except ZuViel:
                # Das ganze Teil verwerfen: der Upload steht wieder dort, wo das Teil ansetzte.
                await asyncio.to_thread(ziel.truncate, versatz)
                raise
            finally:
                await asyncio.to_thread(lambda: (ziel.flush(), os.fsync(ziel.fileno()), ziel.close()))
            async with self.pool.connection() as conn:
                await conn.execute("UPDATE upload SET zuletzt_am=now() WHERE id=%s", (upload_id,))
            if empfangen < zeile["groesse"]:
                return self._als_upload({**zeile}), None
            return self._als_upload({**zeile}), await self._fertigstellen(zeile, max_bytes)
        finally:
            self._laufend.discard(schluessel)

    async def _fertigstellen(self, zeile: dict, max_bytes: int) -> dict:
        """Trägt die vollständige Datei ein; danach gibt es den Upload nicht mehr. Scheitert das Eintragen (Ziel weg,
        Name ist ein Ordner, Prüfsumme falsch), bleibt er liegen, bis er abgebrochen oder weggeräumt wird."""
        datei = self._datei(zeile["besitzer_id"], zeile["id"])
        quelle = await asyncio.to_thread(open, datei, "rb")
        try:
            knoten, _, _ = await self.speicher.datei_hochladen_strom(
                zeile["besitzer_id"], zeile["parent_id"], zeile["name"], quelle, max_bytes,
                pruefsumme=zeile["pruefsumme"])
        finally:
            await asyncio.to_thread(quelle.close)
        await self._entfernen(zeile["besitzer_id"], zeile["id"])
        return knoten

    async def _entfernen(self, besitzer_id, upload_id) -> None:
        async with self.pool.connection() as conn:
            await conn.execute("DELETE FROM upload WHERE id=%s", (upload_id,))
        await asyncio.to_thread(self._datei(besitzer_id, upload_id).unlink, True)

    async def abbrechen(self, besitzer_id, upload_id) -> None:
        if str(upload_id) in self._laufend:
            raise UploadLaeuft("An diesem Upload wird gerade ein Teil angehängt")
        await self._zeile(besitzer_id, upload_id)
        await self._entfernen(besitzer_id, upload_id)

    async def aufraeumen(self) -> int:
        """Ruhende Uploads nach `tage` Tagen weg, dazu Teildateien ohne Upload (etwa nach einem Absturz beim Anlegen).
        Liefert die Zahl entfernter Uploads und Dateien."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "DELETE FROM upload WHERE zuletzt_am < now() - make_interval(days => %s) RETURNING besitzer_id, id",
                    (self.tage,))
                alt = await cur.fetchall()
                await cur.execute("SELECT id FROM upload")
                bekannt = {str(z["id"]) for z in await cur.fetchall()}
        for z in alt:
            await asyncio.to_thread(self._datei(z["besitzer_id"], z["id"]).unlink, True)

        def verwaiste() -> int:
            weg, grenze = 0, time.time() - 3600
            for datei in self.wurzel.glob("*/*") if self.wurzel.is_dir() else []:
                if datei.is_file() and datei.name not in bekannt and datei.stat().st_mtime < grenze:
                    datei.unlink(missing_ok=True)
                    weg += 1
            return weg

        return len(alt) + await asyncio.to_thread(verwaiste)
