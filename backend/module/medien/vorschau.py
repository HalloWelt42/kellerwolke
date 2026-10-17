"""Vorschaubilder und Vollbilder für Medien, abgelegt je Version auf der Platte.

Eine Datei wird genau einmal dekodiert und ergibt beide Stufen. Gelesen wird aus dem Pfad des Blocks (JPEG dekodiert
dabei gleich verkleinert), nicht aus einer Kopie im Speicher; Videos liefern ein Standbild über ffmpeg, das selbst an
die Stelle springt. Gleichzeitig laufen nur wenige Erzeugungen (der Pi hat wenig Speicher), und dieselbe Version
wird nie doppelt erzeugt. Abgelegt wird unter der Versionskennung: eine neue Version hat eine neue Vorschau, die
alte räumt das tägliche Aufräumen weg.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import shutil
import time
from enum import Enum
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from module.medien.arten import UMWANDELN, endung, medienart

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:  # noqa: BLE001 - ohne HEIC läuft der Rest weiter
    pass

_LOG = logging.getLogger("kellerwolke.medien")

# Obergrenze für Bilder, die nicht als ein Block auf der Platte liegen und deshalb gelesen werden müssen.
_MAX_GELESEN = 256 * 1024 * 1024
_VOLL_KANTE = 4096


class Stufe(str, Enum):
    klein = "klein"  # Listenzeilen
    gross = "gross"  # Kacheln, Detail, Medienansicht


_KANTE = {Stufe.klein: 160, Stufe.gross: 480}


class KeinBild(Exception):
    """Der Inhalt lässt sich nicht als Bild lesen (415)."""


class KeinStandbild(Exception):
    """Für dieses Video gibt es kein Standbild (ffmpeg fehlt, kein Pfad, Format unlesbar)."""


def _als_bild(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im) or im
    return im.convert("RGBA" if im.mode in ("RGBA", "LA", "P", "PA") else "RGB")


def _stufen(quelle) -> dict[Stufe, bytes]:
    """Beide Stufen aus einem Dekodiervorgang; quelle ist ein Pfad oder ein Datei-Objekt."""
    try:
        with Image.open(quelle) as roh:
            roh.draft("RGB", (_KANTE[Stufe.gross] * 2, _KANTE[Stufe.gross] * 2))
            im = _als_bild(roh)
            im.thumbnail((_KANTE[Stufe.gross], _KANTE[Stufe.gross]))
            ergebnis = {}
            for stufe in (Stufe.gross, Stufe.klein):
                im.thumbnail((_KANTE[stufe], _KANTE[stufe]))
                aus = io.BytesIO()
                im.save(aus, format="WEBP", quality=82, method=4)
                ergebnis[stufe] = aus.getvalue()
            return ergebnis
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as f:
        raise KeinBild(str(f)) from f


def _voll_jpeg(quelle) -> bytes:
    try:
        with Image.open(quelle) as roh:
            im = _als_bild(roh).convert("RGB")
            im.thumbnail((_VOLL_KANTE, _VOLL_KANTE))
            aus = io.BytesIO()
            im.save(aus, format="JPEG", quality=88)
            return aus.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as f:
        raise KeinBild(str(f)) from f


def _ablegen(ziel: Path, daten: bytes) -> None:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp = ziel.with_name(ziel.name + ".tmp")
    tmp.write_bytes(daten)
    os.replace(tmp, ziel)


class VorschauDienst:
    def __init__(self, pool, speicher, wurzel, gleichzeitig: int = 2, ffmpeg: str = "") -> None:
        self.pool = pool
        self.speicher = speicher
        self.wurzel = Path(wurzel)
        self.ffmpeg = ffmpeg or shutil.which("ffmpeg") or ""
        self._gleichzeitig = asyncio.Semaphore(max(1, gleichzeitig))
        self._je_version: dict[str, asyncio.Lock] = {}

    def _datei(self, etag: str, zusatz: str) -> Path:
        return self.wurzel / etag[:2] / f"{etag}{zusatz}"

    async def _einmal(self, etag: str, ziel: Path, erzeugen) -> Path:
        """Erzeugt höchstens einmal je Version gleichzeitig; wer wartet, bekommt das Ergebnis des Ersten."""
        if ziel.exists():
            return ziel
        sperre = self._je_version.setdefault(etag, asyncio.Lock())
        try:
            async with sperre:
                if not ziel.exists():
                    async with self._gleichzeitig:
                        await erzeugen()
        finally:
            if not sperre.locked():
                self._je_version.pop(etag, None)
        return ziel

    async def _quelle(self, stand):
        """Pfad des Blocks, sonst der Inhalt im Speicher (nur bis zur Grenze)."""
        pfad = await self.speicher.stand_pfad(stand)
        if pfad:
            return pfad
        if stand.groesse > _MAX_GELESEN:
            raise KeinBild("Bild zu groß für eine Vorschau")
        return io.BytesIO(b"".join([b async for b in self.speicher.stand_stroemen(stand)]))

    async def vorschau(self, stand, stufe: Stufe) -> Path:
        """WebP-Vorschau eines Bildes oder Videos in der verlangten Stufe."""
        ziel = self._datei(stand.etag, f"_{stufe.value}.webp")

        async def erzeugen():
            if medienart(stand.knoten["name"]) == "video":
                quelle = io.BytesIO(await self._standbild(stand))
            else:
                quelle = await self._quelle(stand)
            stufen = await asyncio.to_thread(_stufen, quelle)
            for s, daten in stufen.items():
                await asyncio.to_thread(_ablegen, self._datei(stand.etag, f"_{s.value}.webp"), daten)

        return await self._einmal(stand.etag, ziel, erzeugen)

    async def voll_umgewandelt(self, stand) -> Path:
        """JPEG für Bilder, die der Browser nicht zeigt (HEIC); einmal je Version."""
        if endung(stand.knoten["name"]) not in UMWANDELN:
            raise KeinBild("Keine Umwandlung nötig")
        ziel = self._datei(stand.etag, "_voll.jpg")

        async def erzeugen():
            daten = await asyncio.to_thread(_voll_jpeg, await self._quelle(stand))
            await asyncio.to_thread(_ablegen, ziel, daten)

        return await self._einmal(stand.etag + "_voll", ziel, erzeugen)

    async def _standbild(self, stand) -> bytes:
        pfad = await self.speicher.stand_pfad(stand) if self.ffmpeg else None
        if not pfad:
            raise KeinStandbild("Kein ffmpeg oder kein Pfad")
        # Erst ein Stück hinein (das erste Bild ist oft schwarz), bei kurzen Videos vom Anfang.
        for sekunde in (3.0, 0.0):
            bild = await self._ffmpeg_bild(Path(pfad), sekunde)
            if bild:
                return bild
        raise KeinStandbild("Format nicht lesbar")

    async def _ffmpeg_bild(self, quelle: Path, sekunde: float) -> bytes | None:
        """Ein Bild als JPEG; -ss vor -i springt, ohne alles zu dekodieren. JPEG statt WebP, weil dessen Encoder
        nicht in jedem ffmpeg steckt."""
        befehl = [self.ffmpeg, "-nostdin", "-loglevel", "error", "-ss", f"{sekunde}", "-i", str(quelle),
                  "-frames:v", "1", "-f", "image2pipe", "-c:v", "mjpeg", "-q:v", "3", "-"]
        try:
            p = await asyncio.create_subprocess_exec(*befehl, stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.PIPE)
        except OSError:
            return None
        try:
            aus, _ = await asyncio.wait_for(p.communicate(), timeout=30)
        except asyncio.TimeoutError:
            p.kill()
            await p.wait()
            return None
        return aus if p.returncode == 0 and aus else None

    # --- Aufräumen ----------------------------------------------------------------------------------------------

    async def aufraeumen(self) -> int:
        """Entfernt Abgelegtes, dessen Version nicht mehr der aktuelle Stand einer lebenden Datei ist, und liegen
        gebliebene Zwischendateien. Liefert die Zahl entfernter Dateien."""
        dateien = await asyncio.to_thread(lambda: [p for p in self.wurzel.rglob("*") if p.is_file()]
                                          if self.wurzel.is_dir() else [])
        weg, jetzt = 0, time.time()
        je_etag: dict[str, list[Path]] = {}
        for p in dateien:
            if p.name.endswith(".tmp"):
                if jetzt - p.stat().st_mtime > 3600:
                    p.unlink(missing_ok=True)
                    weg += 1
                continue
            je_etag.setdefault(p.name.split("_", 1)[0], []).append(p)
        etags = list(je_etag)
        for i in range(0, len(etags), 1000):
            teil = etags[i:i + 1000]
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT etag FROM knoten WHERE etag = ANY(%s) AND NOT geloescht", (teil,))
                    lebend = {z[0] for z in await cur.fetchall()}
            for etag in teil:
                if etag not in lebend:
                    for p in je_etag[etag]:
                        p.unlink(missing_ok=True)
                        weg += 1
        return weg
