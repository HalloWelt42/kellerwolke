"""Gemeinsame Pruefregeln fuer Git-Hooks und CI-Backstop.

Alle Sperren sind hier gebuendelt, damit lokale Hooks und der CI-Lauf
exakt dieselbe Logik verwenden. Datenlisten (Marken, KI-Begriffe,
Umlaut-Woerter) liegen als Textdateien daneben und sind leicht erweiterbar.
"""

import re
import fnmatch
from pathlib import Path

HIER = Path(__file__).resolve().parent


def _lade_liste(name):
    pfad = HIER / name
    eintraege = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        z = zeile.strip()
        if z and not z.startswith("#"):
            eintraege.append(z)
    return eintraege


MARKEN = _lade_liste("denylist-marken.txt")
KI_BEGRIFFE = _lade_liste("denylist-ki.txt")
UMLAUT_WOERTER = _lade_liste("umlaut-wortliste.txt")

# Verbotene typografische Sonderzeichen (nur gerade Zeichen erlaubt).
# Schluessel als Unicode-Escape, damit diese Datei selbst sauber bleibt.
TYPO_VERBOTEN = {
    chr(0x2010): "Bindestrich (typografisch)",
    chr(0x2011): "geschuetzter Bindestrich",
    chr(0x2012): "Ziffernstrich",
    chr(0x2013): "En-Dash",
    chr(0x2014): "Em-Dash",
    chr(0x2015): "Horizontalstrich",
    chr(0x2018): "Hochkomma links",
    chr(0x2019): "Hochkomma rechts",
    chr(0x201A): "Komma unten",
    chr(0x201C): "Anfuehrungszeichen links",
    chr(0x201D): "Anfuehrungszeichen rechts",
    chr(0x201E): "Anfuehrungszeichen unten",
    chr(0x00AB): "Guillemet links",
    chr(0x00BB): "Guillemet rechts",
    chr(0x2026): "Auslassungspunkte",
    chr(0x2212): "Minuszeichen",
}

# Nur die eindeutigen Git-Konflikt-Marker (<<<<<<< / >>>>>>>); die '======='-
# Variante entfaellt, weil sie mit Setext-Ueberschriften kollidiert - ein echter
# Konflikt enthaelt ohnehin immer auch die spitzen Marker.
KONFLIKT = re.compile(r"^(<{7,}|>{7,})(\s|$)")
AGPL = re.compile(r"GNU\s+AFFERO|AGPL-3|Affero General Public", re.IGNORECASE)

# Eindeutige Geheimnis-Muster (sehr geringe Fehlalarmquote).
GEHEIMNIS = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"
    r"|AKIA[0-9A-Z]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{36,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AIza[0-9A-Za-z_-]{35}"
)

# Strukturzeilen (Trennlinie, Tabellen-Trenner, Setext) - kein Fliesstext.
STRUKTURZEILE = re.compile(r"^[|:\-\s]+$|^=+$")

_WORT_RAND = r"[\wäöüßÄÖÜ]"


def _regex_ganzwoerter(woerter):
    if not woerter:
        return None
    teile = "|".join(re.escape(w) for w in woerter)
    return re.compile(r"(?<!" + _WORT_RAND + r")(" + teile + r")(?!" + _WORT_RAND + r")",
                      re.IGNORECASE)


def _regex_teilwoerter(woerter):
    if not woerter:
        return None
    return re.compile("|".join(re.escape(w) for w in woerter), re.IGNORECASE)


MARKEN_RE = _regex_ganzwoerter(MARKEN)
# Umlaut-Formen treffen als Teilstring, damit auch Komposita erkannt werden.
UMLAUT_RE = _regex_teilwoerter(UMLAUT_WOERTER)
KI_RE = re.compile("|".join(KI_BEGRIFFE), re.IGNORECASE) if KI_BEGRIFFE else None

PROSA_ENDUNGEN = {".md", ".markdown", ".txt"}

# Pfad-Regeln: was niemals eingecheckt werden darf.
SECRET_GLOBS = ["*.key", "*.pem", "*.p12", "*.pfx", "id_rsa", "id_ed25519"]
SECRET_AUSNAHME = {".env.muster", ".env.beispiel"}
NUTZDATEN_DIRS = {"objects", "data", "node_modules", ".venv", "dist", "build", "__pycache__"}
NUTZDATEN_GLOBS = ["*.db", "*.sqlite", "*.sqlite3", "*.pyc"]


def _ausgenommen_begriffe(pfad):
    """Die Pruefskripte selbst enthalten die Sperrbegriffe - sie sind
    von den Begriffs- und Umlautpruefungen ausgenommen (Typografie bleibt)."""
    p = pfad.replace("\\", "/")
    return p.startswith("tools/checks/") or "/tools/checks/" in p


def ist_prosa(pfad):
    p = pfad.replace("\\", "/").lower()
    return Path(p).suffix in PROSA_ENDUNGEN or "/docs/" in p or p.startswith("docs/")


def _prosa_zeilen(text):
    """Markdown-Codebloecke (``` und ~~~) und Inline-Code ausblenden, damit die
    Prosa-Pruefungen nur echten Fliesstext treffen (Code-Identifier sind erlaubt)."""
    ergebnis = []
    fence = None  # offenes Fence-Zeichen ('`' oder '~') oder None
    for zeile in text.split("\n"):
        marke = re.match(r"\s*(```+|~~~+)", zeile)
        if marke:
            zeichen = marke.group(1)[0]
            if fence is None:
                fence = zeichen
            elif fence == zeichen:
                fence = None
            ergebnis.append("")
            continue
        if fence is not None:
            ergebnis.append("")
            continue
        ergebnis.append(re.sub(r"`[^`]*`", " ", zeile))
    return ergebnis


def pruefe_datei(pfad, text):
    """Liefert eine Liste (zeile, art, detail) aller Verstoesse."""
    verstoesse = []
    ausgenommen = _ausgenommen_begriffe(pfad)
    zeilen = text.split("\n")

    for i, zeile in enumerate(zeilen, start=1):
        for ch in zeile:
            if ch in TYPO_VERBOTEN:
                verstoesse.append((i, "Typografie",
                                   "%s (U+%04X)" % (TYPO_VERBOTEN[ch], ord(ch))))
        if KONFLIKT.match(zeile):
            verstoesse.append((i, "Merge-Konflikt", zeile[:7]))
        if not ausgenommen:
            if KI_RE:
                m = KI_RE.search(zeile)
                if m:
                    verstoesse.append((i, "KI-Erwaehnung", m.group(0)))
            if MARKEN_RE:
                m = MARKEN_RE.search(zeile)
                if m:
                    verstoesse.append((i, "Fremde Marke", m.group(0)))
            m = AGPL.search(zeile)
            if m:
                verstoesse.append((i, "Fremdlizenz", m.group(0)))
            g = GEHEIMNIS.search(zeile)
            if g:
                verstoesse.append((i, "Geheimnis", g.group(0)[:24]))

    if not ausgenommen and ist_prosa(pfad):
        for i, zeile in enumerate(_prosa_zeilen(text), start=1):
            if UMLAUT_RE:
                m = UMLAUT_RE.search(zeile)
                if m:
                    verstoesse.append((i, "ASCII-Umlaut", m.group(0)))
            # Doppelter Bindestrich in Fliesstext (Strukturzeilen ausgenommen).
            if "--" in zeile and not STRUKTURZEILE.match(zeile.strip()):
                verstoesse.append((i, "Doppelter Bindestrich", "--"))

    return verstoesse


def pfad_verstoss(pfad):
    """Pfad-basierte Sperren (Secrets, Nutzdaten). None wenn sauber."""
    p = pfad.replace("\\", "/")
    teile = [t for t in p.split("/") if t]
    name = teile[-1] if teile else p

    if name == ".env" or name.startswith(".env."):
        if name not in SECRET_AUSNAHME:
            return "Geheimnis (.env) darf nicht eingecheckt werden"
    for glob in SECRET_GLOBS:
        if fnmatch.fnmatch(name, glob):
            return "Geheimnis/Schluessel darf nicht eingecheckt werden"
    if set(teile) & NUTZDATEN_DIRS:
        return "Nutzdaten/Artefakt darf nicht eingecheckt werden"
    for glob in NUTZDATEN_GLOBS:
        if fnmatch.fnmatch(name, glob):
            return "Nutzdaten/Artefakt darf nicht eingecheckt werden"
    return None
