"""Galerie-Logik: serverseitige Thumbnails (WebP, plattengecacht) und
browser-taugliche Vollbilder. Greift NUR ueber den SpeicherDienst aus dem
PluginKontext auf Dateien zu (Eigentuemerpruefung, ETag/Journal bleiben Sache
des Kerns). Bildverarbeitung laeuft im Thread, damit der Event-Loop frei bleibt.
"""

import asyncio
import io
import os
from pathlib import Path

from PIL import Image, ImageOps

# HEIC (iPhone) optional: fehlt das Paket, funktionieren nur die anderen
# Formate - das Plugin laedt trotzdem.
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_DA = True
except Exception:  # noqa: BLE001
    HEIF_DA = False

BILD_ENDUNGEN = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif", ".svg"}
_INLINE_TYP = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
}


def ist_bild(name: str) -> bool:
    punkt = name.rfind(".")
    return punkt != -1 and name[punkt:].lower() in BILD_ENDUNGEN


def _endung(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


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
        # HEIC zeigt kaum ein Browser -> serverseitig nach JPEG wandeln.
        with Image.open(io.BytesIO(daten)) as im:
            im = ImageOps.exif_transpose(im) or im
            im = im.convert("RGB")
            out = io.BytesIO()
            im.save(out, format="JPEG", quality=88)
            return out.getvalue(), "image/jpeg"
    return daten, _INLINE_TYP.get(endung, "application/octet-stream")


class GalerieDienst:
    def __init__(self, kontext) -> None:
        self.kontext = kontext
        wurzel = kontext.plugin_pfad.parents[2]  # backend/plugins/galerie -> Projektwurzel
        self.cache_dir = Path(
            os.environ.get("KELLERWOLKE_GALERIE_CACHE", str(wurzel / "data" / "galerie-thumbs"))
        )

    async def _bild_knoten(self, benutzer_id, knoten_id):
        knoten = await self.kontext.speicher.knoten_des_nutzers(benutzer_id, knoten_id)
        if not knoten or knoten["typ"] != "datei" or knoten["geloescht"] or not ist_bild(knoten["name"]):
            raise FileNotFoundError("Kein Bild")
        return knoten

    def _cache_schreiben(self, ziel: Path, daten: bytes) -> None:
        ziel.parent.mkdir(parents=True, exist_ok=True)
        tmp = ziel.with_name(ziel.name + ".tmp")
        tmp.write_bytes(daten)
        os.replace(tmp, ziel)

    async def thumb(self, benutzer_id, knoten_id, kante: int) -> tuple[bytes, str]:
        knoten = await self._bild_knoten(benutzer_id, knoten_id)
        # SVG skaliert der Browser selbst - direkt ausliefern, kein Raster-Thumb.
        if _endung(knoten["name"]) == "svg":
            daten = await self.kontext.speicher.datei_lesen(benutzer_id, knoten_id)
            return daten, "image/svg+xml"
        # Cache-Schluessel = ETag/Version des Knotens -> neue Version = neues Thumb.
        etag = str(knoten.get("etag") or knoten["id"])
        ziel = self.cache_dir / etag[:2] / f"{etag}_{kante}.webp"
        if ziel.exists():
            return await asyncio.to_thread(ziel.read_bytes), "image/webp"
        daten = await self.kontext.speicher.datei_lesen(benutzer_id, knoten_id)
        thumb = await asyncio.to_thread(_thumb_bytes, daten, kante)
        await asyncio.to_thread(self._cache_schreiben, ziel, thumb)
        return thumb, "image/webp"

    async def inline(self, benutzer_id, knoten_id) -> tuple[bytes, str]:
        knoten = await self._bild_knoten(benutzer_id, knoten_id)
        daten = await self.kontext.speicher.datei_lesen(benutzer_id, knoten_id)
        return await asyncio.to_thread(_inline_bytes, daten, knoten["name"])
