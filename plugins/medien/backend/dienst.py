"""Medien-Logik: serverseitige Bild-Thumbnails (WebP, plattengecacht),
browser-taugliche Vollbilder und Audio-Auslieferung. Zugriff NUR ueber den
SpeicherDienst aus dem Kontext (Eigentuemerpruefung, ETag bleiben Kern-Sache).
Bildverarbeitung laeuft im Thread, damit der Event-Loop frei bleibt.
"""

import asyncio
import io
import os
import shutil
from pathlib import Path

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:  # noqa: BLE001 - ohne HEIC laeuft der Rest weiter
    pass

BILD_ENDUNGEN = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif", ".svg"}
AUDIO_ENDUNGEN = {".mp3", ".wav", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".flac"}
# Video laeuft ueber denselben Range-Weg wie Audio - der Browser spielt es
# direkt, sofern er den Codec kann (mp4/H.264 und webm sind der sichere Fall).
VIDEO_ENDUNGEN = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".ogv"}

_BILD_TYP = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
             "webp": "image/webp", "bmp": "image/bmp"}
_AUDIO_TYP = {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg", "oga": "audio/ogg",
              "opus": "audio/ogg", "m4a": "audio/mp4", "aac": "audio/aac", "flac": "audio/flac"}
_VIDEO_TYP = {"mp4": "video/mp4", "m4v": "video/mp4", "mov": "video/quicktime",
              "webm": "video/webm", "mkv": "video/x-matroska", "ogv": "video/ogg"}


def _endung(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def ist_bild(name: str) -> bool:
    p = name.rfind(".")
    return p != -1 and name[p:].lower() in BILD_ENDUNGEN


def ist_audio(name: str) -> bool:
    p = name.rfind(".")
    return p != -1 and name[p:].lower() in AUDIO_ENDUNGEN


def ist_video(name: str) -> bool:
    p = name.rfind(".")
    return p != -1 and name[p:].lower() in VIDEO_ENDUNGEN


def ist_abspielbar(name: str) -> bool:
    """Alles, was ueber den Stream-Endpunkt laeuft (Audio wie Video)."""
    return ist_audio(name) or ist_video(name)


def strom_typ(name: str) -> str:
    e = _endung(name)
    return _AUDIO_TYP.get(e) or _VIDEO_TYP.get(e) or "application/octet-stream"


def ffmpeg_pfad() -> str | None:
    """Wo liegt ffmpeg - oder None, wenn es nicht installiert ist.

    ffmpeg ist AUSDRUECKLICH optional: fehlt es, entfallen nur die Standbilder
    von Videos (dann bleibt das Film-Symbol), alles andere laeuft normal weiter.
    """
    return os.environ.get("KELLERWOLKE_FFMPEG") or shutil.which("ffmpeg")


async def _video_standbild(quelle: Path, sekunde: float) -> bytes | None:
    """Holt EIN Bild aus dem Video - ffmpeg springt selbst an die Stelle und
    liest nur dort, die Datei wandert also nicht in den Speicher.

    Geliefert wird ein roher JPEG-Frame; verkleinert wird anschliessend mit
    Pillow, also auf demselben Weg wie bei Bildern. Bewusst kein WebP direkt aus
    ffmpeg: ob dessen WebP-Encoder einkompiliert ist, unterscheidet sich je nach
    Build (auf dem Mac fehlt er) - mjpeg ist ueberall vorhanden.

    Liefert None, wenn ffmpeg fehlt, das Format nicht mag oder zu lange braucht.
    """
    werkzeug = ffmpeg_pfad()
    if not werkzeug:
        return None
    befehl = [
        werkzeug, "-nostdin", "-loglevel", "error",
        "-ss", f"{sekunde}",           # VOR -i: schneller Sprung, ohne alles zu dekodieren
        "-i", str(quelle),
        "-frames:v", "1",
        "-f", "image2pipe", "-c:v", "mjpeg", "-q:v", "3",
        "-",
    ]
    try:
        p = await asyncio.create_subprocess_exec(
            *befehl, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except OSError:
        return None
    try:
        aus, _ = await asyncio.wait_for(p.communicate(), timeout=30)
    except asyncio.TimeoutError:
        p.kill()
        await p.wait()
        return None
    return aus if p.returncode == 0 and aus else None


def _thumb_bytes(daten: bytes, kante: int) -> bytes:
    with Image.open(io.BytesIO(daten)) as im:
        im = ImageOps.exif_transpose(im) or im
        im.thumbnail((kante, kante))
        im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
        out = io.BytesIO()
        im.save(out, format="WEBP", quality=82, method=4)
        return out.getvalue()


def _inline_bytes(daten: bytes, name: str) -> tuple[bytes, str]:
    endung = _endung(name)
    if endung == "svg":
        return daten, "image/svg+xml"
    if endung in ("heic", "heif"):
        with Image.open(io.BytesIO(daten)) as im:
            im = ImageOps.exif_transpose(im) or im
            im = im.convert("RGB")
            out = io.BytesIO()
            im.save(out, format="JPEG", quality=88)
            return out.getvalue(), "image/jpeg"
    return daten, _BILD_TYP.get(endung, "application/octet-stream")


class MedienDienst:
    def __init__(self, kontext) -> None:
        self.kontext = kontext
        wurzel = kontext.plugin_pfad.parents[2]
        self.cache_dir = Path(
            os.environ.get("KELLERWOLKE_MEDIEN_CACHE", str(wurzel / "data" / "medien-thumbs"))
        )

    async def _knoten(self, benutzer_id, knoten_id, pruef):
        k = await self.kontext.speicher.knoten_des_nutzers(benutzer_id, knoten_id)
        if not k or k["typ"] != "datei" or k["geloescht"] or not pruef(k["name"]):
            raise FileNotFoundError("nicht vorhanden")
        return k

    def _cache_schreiben(self, ziel: Path, daten: bytes) -> None:
        ziel.parent.mkdir(parents=True, exist_ok=True)
        tmp = ziel.with_name(ziel.name + ".tmp")
        tmp.write_bytes(daten)
        os.replace(tmp, ziel)

    async def thumb(self, benutzer_id, knoten_id, kante: int) -> tuple[bytes, str]:
        # Bild ODER Video: Videos bekommen ein Standbild als Vorschau.
        k = await self._knoten(benutzer_id, knoten_id, lambda n: ist_bild(n) or ist_video(n))
        if _endung(k["name"]) == "svg":
            daten = await self.kontext.speicher.datei_lesen(benutzer_id, knoten_id)
            return daten, "image/svg+xml"
        etag = str(k.get("etag") or k["id"])
        ziel = self.cache_dir / etag[:2] / f"{etag}_{kante}.webp"
        if ziel.exists():
            return await asyncio.to_thread(ziel.read_bytes), "image/webp"

        if ist_video(k["name"]):
            thumb = await self._video_thumb(benutzer_id, knoten_id, kante)
            if thumb is None:
                # Kein ffmpeg oder Format nicht lesbar: ehrlich melden, damit die
                # Oberflaeche auf ihr Film-Symbol zurueckfaellt.
                raise FileNotFoundError("Kein Standbild moeglich")
        else:
            daten = await self.kontext.speicher.datei_lesen(benutzer_id, knoten_id)
            thumb = await asyncio.to_thread(_thumb_bytes, daten, kante)
        await asyncio.to_thread(self._cache_schreiben, ziel, thumb)
        return thumb, "image/webp"

    async def _video_thumb(self, benutzer_id, knoten_id, kante: int) -> bytes | None:
        """Standbild eines Videos ueber ffmpeg - ohne die Datei zu lesen.

        Dafuer wird der lokale Pfad des Blocks gebraucht; gibt es keinen (etwa
        bei einem entfernten Speicher), entfaellt das Standbild.
        """
        quelle = await self.kontext.speicher.datei_pfad(benutzer_id, knoten_id)
        if not quelle:
            return None
        # Erst ein Stueck hineinspringen - der allererste Frame ist oft schwarz.
        # Ist das Video kuerzer, liefert ffmpeg nichts; dann vom Anfang nehmen.
        for sekunde in (3.0, 0.0):
            frame = await _video_standbild(Path(quelle), sekunde)
            if frame:
                # Verkleinern wie bei Bildern - gleiche Kette, gleiches Ergebnis.
                return await asyncio.to_thread(_thumb_bytes, frame, kante)
        return None

    async def inline(self, benutzer_id, knoten_id) -> tuple[bytes, str]:
        k = await self._knoten(benutzer_id, knoten_id, ist_bild)
        daten = await self.kontext.speicher.datei_lesen(benutzer_id, knoten_id)
        return await asyncio.to_thread(_inline_bytes, daten, k["name"])

    async def strom_kopf(self, benutzer_id, knoten_id) -> tuple[int, str]:
        """Groesse und MIME-Typ, OHNE die Datei zu lesen. Der Range-Kopf braucht
        nur diese beiden Angaben - eine 1-GB-Datei darf dafuer nicht angefasst
        werden."""
        k = await self._knoten(benutzer_id, knoten_id, ist_abspielbar)
        groesse = await self.kontext.speicher.datei_groesse(benutzer_id, knoten_id)
        return groesse, strom_typ(k["name"])

    async def strom_stroemen(self, benutzer_id, knoten_id, start: int, laenge: int):
        """Liefert NUR den angeforderten Ausschnitt, und den stueckweise. Damit
        kostet ein Sprung im Player genau diesen Ausschnitt statt der ganzen
        Datei - und selbst ein grosser Bereich landet nie am Stueck im Speicher."""
        await self._knoten(benutzer_id, knoten_id, ist_abspielbar)
        async for brocken in self.kontext.speicher.datei_stroemen(
            benutzer_id, knoten_id, start, laenge
        ):
            yield brocken

    async def alle_medien(self, benutzer_id) -> list[dict]:
        muster = [f"%{e}" for e in sorted(BILD_ENDUNGEN | AUDIO_ENDUNGEN | VIDEO_ENDUNGEN)]
        zeilen = await self.kontext.speicher.dateien_nach_endung(benutzer_id, muster)
        ergebnis = []
        for z in zeilen:
            ergebnis.append({
                "id": str(z["id"]),
                "name": z["name"],
                "groesse": z.get("groesse"),
                "pfad": z["pfad"],
                "typ": "bild" if ist_bild(z["name"]) else "video" if ist_video(z["name"]) else "audio",
            })
        return ergebnis
