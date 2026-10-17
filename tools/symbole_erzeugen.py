"""Erzeugt die App-Symbole aus der Logo-Form (frontend/public/favicon.svg) für alle Geräte: favicon.ico, PNG in 32
und 192, apple-touch-icon in 180 (ohne Transparenz) und die Manifest-Symbole in 192 und 512 (auch zum Zuschneiden).

Die Form besteht nur aus abgerundeten Rechtecken und Kreisen und wird hier mit Pillow nachgezeichnet, mehrfach
überabgetastet für glatte Kanten. Die Ergebnisse liegen im Repo; neu erzeugen nur, wenn sich das Logo ändert:

    backend/.venv/bin/python tools/symbole_erzeugen.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ZIEL = Path(__file__).resolve().parents[1] / "frontend" / "public"
BLAU = (47, 124, 224, 255)  # --akzent hell, wie favicon.svg
WEISS = (255, 255, 255, 255)

# Die Form im Raster 32 x 32 (wie die viewBox des SVG).
RECHTECKE = [(5, 11, 22, 7, 3.5), (9, 21, 14, 2.6, 1.3), (9, 25, 14, 2.6, 1.3), (9, 29, 14, 2.6, 1.3)]
KREISE = [(10, 12.5, 4.5), (16, 8.5, 6), (22, 13, 4)]
UEBER = 8  # Überabtastung


def zeichnen(kante: int, farbe, grund, rand: float = 0.0) -> Image.Image:
    """Logo in kante x kante; rand ist der freie Anteil je Seite (für Symbole mit Hintergrund)."""
    gross = kante * UEBER
    bild = Image.new("RGBA", (gross, gross), grund)
    stift = ImageDraw.Draw(bild)
    nutz = gross * (1 - 2 * rand)
    s = nutz / 32
    versatz = gross * rand
    # Die Form reicht von y=2.5 bis 31.6: senkrecht mittig setzen.
    oben = versatz + (nutz - 29.1 * s) / 2 - 2.5 * s
    for x, y, b, h, r in RECHTECKE:
        stift.rounded_rectangle([versatz + x * s, oben + y * s, versatz + (x + b) * s, oben + (y + h) * s],
                                radius=r * s, fill=farbe)
    for cx, cy, r in KREISE:
        stift.ellipse([versatz + (cx - r) * s, oben + (cy - r) * s, versatz + (cx + r) * s, oben + (cy + r) * s],
                      fill=farbe)
    return bild.resize((kante, kante), Image.LANCZOS)


def main() -> None:
    durchsichtig = (0, 0, 0, 0)
    zeichnen(32, BLAU, durchsichtig).save(ZIEL / "favicon-32.png")
    zeichnen(192, BLAU, durchsichtig).save(ZIEL / "favicon-192.png")
    zeichnen(256, BLAU, durchsichtig).save(ZIEL / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    # Startbildschirm (iOS, Android): voller Hintergrund, Logo mit Rand, keine Transparenz.
    zeichnen(180, WEISS, BLAU, rand=0.16).convert("RGB").save(ZIEL / "apple-touch-icon.png")
    zeichnen(192, WEISS, BLAU, rand=0.16).convert("RGB").save(ZIEL / "symbol-192.png")
    zeichnen(512, WEISS, BLAU, rand=0.16).convert("RGB").save(ZIEL / "symbol-512.png")
    # Zum Zuschneiden (maskable): Logo in der sicheren Mitte.
    zeichnen(512, WEISS, BLAU, rand=0.24).convert("RGB").save(ZIEL / "symbol-maskable-512.png")


if __name__ == "__main__":
    main()
