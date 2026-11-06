"""Erzeugt das Logo der Kellerwolke und alle App-Symbole aus EINER Form (KW-7): eine blaue Wolke mit Verlauf, aus der
drei bunte Dateien regnen (Entwurf mockups/logo-entwuerfe.html: Wolke aus F ohne Glanz, Dateien aus C).

Geschrieben werden frontend/public/favicon.svg (zeigt auch die App selbst, lib/Logo.svelte), favicon.ico, PNG in 32
und 192, apple-touch-icon in 180 und die Manifest-Symbole in 192 und 512 (auch zum Zuschneiden), diese auf weißer
Kachel ohne Transparenz. Die PNG zeichnet Pillow aus derselben Form nach, mehrfach überabgetastet für glatte Kanten.
Die Ergebnisse liegen im Repo; neu erzeugen nur, wenn sich das Logo ändert:

    backend/.venv/bin/python tools/symbole_erzeugen.py
"""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

ZIEL = Path(__file__).resolve().parents[1] / "frontend" / "public"
UEBER = 8  # Überabtastung
RASTER = 64  # Kantenlänge des Rasters, in dem die Form steht (viewBox des SVG)

# --- Die Form: eine Stelle für SVG und PNG -------------------------------------------------------------------------

WOLKE_OBEN, WOLKE_UNTEN = "#5aa2f5", "#1f5fb8"  # senkrechter Verlauf der Wolke
WEISS = (255, 255, 255, 255)


@dataclass(frozen=True)
class Kreis:
    cx: float
    cy: float
    r: float


@dataclass(frozen=True)
class Sockel:  # gerundetes Rechteck unter den Kreisen
    x: float
    y: float
    b: float
    h: float
    r: float


@dataclass(frozen=True)
class Datei:  # Rechteck mit umgeknickter Ecke oben rechts
    x: float
    y: float
    b: float
    h: float
    farbe: str

    @property
    def ecke(self) -> float:
        return min(self.b, self.h) * 0.38


def _wolke(cx: float, cy: float, breite: float) -> tuple[Sockel, list[Kreis]]:
    s = breite / 48
    return (Sockel(cx - 22 * s, cy - 2 * s, 44 * s, 14 * s, 7 * s),
            [Kreis(cx - 12 * s, cy, 9 * s), Kreis(cx + 1 * s, cy - 6 * s, 12 * s), Kreis(cx + 13 * s, cy + 2 * s, 8 * s)])


VERSATZ = 2.75  # senkrecht mittig: die Form reicht im Entwurf von 1,5 bis 57
SOCKEL, KREISE = _wolke(32, 21 + VERSATZ, 52)
DATEIEN = [Datei(13, 41 + VERSATZ, 9, 12, "#ef5350"), Datei(27.5, 45 + VERSATZ, 9, 12, "#ffb300"),
           Datei(42, 41 + VERSATZ, 9, 12, "#43a047")]
VERLAUF_Y = (6 + VERSATZ, 35 + VERSATZ)


def _datei_umriss(d: Datei) -> list[tuple[float, float]]:
    e = d.ecke
    return [(d.x, d.y), (d.x + d.b - e, d.y), (d.x + d.b, d.y + e), (d.x + d.b, d.y + d.h), (d.x, d.y + d.h)]


def _ecke(d: Datei) -> list[tuple[float, float]]:
    e = d.ecke
    return [(d.x + d.b - e, d.y), (d.x + d.b - e, d.y + e), (d.x + d.b, d.y + e)]


# --- SVG ------------------------------------------------------------------------------------------------------------

def _z(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def svg() -> str:
    def punkte(p: list[tuple[float, float]]) -> str:
        return " ".join(f"{_z(x)},{_z(y)}" for x, y in p)

    teile = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {RASTER} {RASTER}">',
        f'  <defs><linearGradient id="kw-wolke" gradientUnits="userSpaceOnUse" x1="0" y1="{_z(VERLAUF_Y[0])}" '
        f'x2="0" y2="{_z(VERLAUF_Y[1])}"><stop offset="0" stop-color="{WOLKE_OBEN}"/>'
        f'<stop offset="1" stop-color="{WOLKE_UNTEN}"/></linearGradient></defs>',
        '  <g fill="url(#kw-wolke)">',
        f'    <rect x="{_z(SOCKEL.x)}" y="{_z(SOCKEL.y)}" width="{_z(SOCKEL.b)}" height="{_z(SOCKEL.h)}" '
        f'rx="{_z(SOCKEL.r)}"/>',
        *[f'    <circle cx="{_z(k.cx)}" cy="{_z(k.cy)}" r="{_z(k.r)}"/>' for k in KREISE],
        "  </g>",
    ]
    for d in DATEIEN:
        teile.append(f'  <polygon points="{punkte(_datei_umriss(d))}" fill="{d.farbe}" stroke="{d.farbe}" '
                     f'stroke-width="1" stroke-linejoin="round"/>')
        teile.append(f'  <polygon points="{punkte(_ecke(d))}" fill="#fff" fill-opacity="0.55"/>')
    teile.append("</svg>\n")
    return "\n".join(teile)


# --- PNG ------------------------------------------------------------------------------------------------------------

def _farbe(hexwert: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = hexwert.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha


def zeichnen(kante: int, grund=(0, 0, 0, 0), rand: float = 0.0) -> Image.Image:
    """Logo in kante x kante; rand ist der freie Anteil je Seite (für Symbole mit Grund)."""
    gross = kante * UEBER
    s = gross * (1 - 2 * rand) / RASTER
    v = gross * rand

    def p(x: float, y: float) -> tuple[float, float]:
        return v + x * s, v + y * s

    bild = Image.new("RGBA", (gross, gross), grund)

    # Wolke: Form als Maske, gefüllt mit dem senkrechten Verlauf
    maske = Image.new("L", (gross, gross), 0)
    m = ImageDraw.Draw(maske)
    m.rounded_rectangle([*p(SOCKEL.x, SOCKEL.y), *p(SOCKEL.x + SOCKEL.b, SOCKEL.y + SOCKEL.h)], radius=SOCKEL.r * s, fill=255)
    for k in KREISE:
        m.ellipse([*p(k.cx - k.r, k.cy - k.r), *p(k.cx + k.r, k.cy + k.r)], fill=255)
    oben, unten = _farbe(WOLKE_OBEN), _farbe(WOLKE_UNTEN)
    verlauf = Image.new("RGBA", (1, gross))
    y0, y1 = p(0, VERLAUF_Y[0])[1], p(0, VERLAUF_Y[1])[1]
    for y in range(gross):
        t = min(1.0, max(0.0, (y - y0) / (y1 - y0)))
        verlauf.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(oben, unten)))
    bild.paste(verlauf.resize((gross, gross)), (0, 0), maske)

    # Dateien mit umgeknickter Ecke
    stift = ImageDraw.Draw(bild, "RGBA")
    for d in DATEIEN:
        stift.polygon([p(x, y) for x, y in _datei_umriss(d)], fill=_farbe(d.farbe))
        stift.line([p(x, y) for x, y in _datei_umriss(d)] + [p(d.x, d.y)], fill=_farbe(d.farbe), width=round(s), joint="curve")
        stift.polygon([p(x, y) for x, y in _ecke(d)], fill=(255, 255, 255, 140))
    return bild.resize((kante, kante), Image.LANCZOS)


def main() -> None:
    (ZIEL / "favicon.svg").write_text(svg(), encoding="utf-8")
    zeichnen(32).save(ZIEL / "favicon-32.png")
    zeichnen(192).save(ZIEL / "favicon-192.png")
    zeichnen(256).save(ZIEL / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    # Startbildschirm (iOS, Android): weiße Kachel, Logo mit Rand, keine Transparenz.
    zeichnen(180, WEISS, rand=0.1).convert("RGB").save(ZIEL / "apple-touch-icon.png")
    zeichnen(192, WEISS, rand=0.1).convert("RGB").save(ZIEL / "symbol-192.png")
    zeichnen(512, WEISS, rand=0.1).convert("RGB").save(ZIEL / "symbol-512.png")
    # Zum Zuschneiden (maskable): Logo in der sicheren Mitte.
    zeichnen(512, WEISS, rand=0.2).convert("RGB").save(ZIEL / "symbol-maskable-512.png")


if __name__ == "__main__":
    main()
