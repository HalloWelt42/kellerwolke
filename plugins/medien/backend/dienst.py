"""Medien-Logik: serverseitige Bild-Thumbnails (WebP, plattengecacht),
browser-taugliche Vollbilder und Audio-Auslieferung. Zugriff NUR ueber den
SpeicherDienst aus dem Kontext (Eigentuemerpruefung, ETag bleiben Kern-Sache).
Bildverarbeitung laeuft im Thread, damit der Event-Loop frei bleibt.
"""

import asyncio
import io
import os
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
        k = await self._knoten(benutzer_id, knoten_id, ist_bild)
        if _endung(k["name"]) == "svg":
            daten = await self.kontext.speicher.datei_lesen(benutzer_id, knoten_id)
            return daten, "image/svg+xml"
        etag = str(k.get("etag") or k["id"])
        ziel = self.cache_dir / etag[:2] / f"{etag}_{kante}.webp"
        if ziel.exists():
            return await asyncio.to_thread(ziel.read_bytes), "image/webp"
        daten = await self.kontext.speicher.datei_lesen(benutzer_id, knoten_id)
        thumb = await asyncio.to_thread(_thumb_bytes, daten, kante)
        await asyncio.to_thread(self._cache_schreiben, ziel, thumb)
        return thumb, "image/webp"

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

    async def strom_bereich(self, benutzer_id, knoten_id, start: int, laenge: int) -> bytes:
        """Liefert NUR den angeforderten Ausschnitt. Damit kostet ein Sprung im
        Player genau diesen Ausschnitt statt der ganzen Datei."""
        await self._knoten(benutzer_id, knoten_id, ist_abspielbar)
        return await self.kontext.speicher.datei_bereich_lesen(
            benutzer_id, knoten_id, start, laenge
        )

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
