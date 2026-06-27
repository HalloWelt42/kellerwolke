"""Textextraktion fuer die Volltextsuche.

Aus gaengigen Formaten wird Text gewonnen (Klartext/Code direkt, PDF, docx),
Binaerformate liefern leeren Text (dann zaehlt nur der Dateiname). Fehlerhafte
Dateien duerfen die Indexierung nicht zum Absturz bringen - im Zweifel "".

Alle Pfade sind gegen Ressourcen-DoS begrenzt: Eingabegroesse, PDF-Seiten und
docx-Entpackgroesse (Zip-Bombe) werden gedeckelt, bevor teuer geparst wird.
"""

import zipfile
from io import BytesIO

_TEXT_ENDUNGEN = {
    "txt", "md", "markdown", "csv", "tsv", "log", "json", "xml", "yaml", "yml",
    "ini", "cfg", "conf", "toml", "py", "js", "ts", "tsx", "jsx", "svelte", "vue",
    "java", "c", "cpp", "h", "hpp", "go", "rs", "rb", "php", "sh", "sql", "html",
    "css", "scss",
}

_MAX_ZEICHEN = 1_000_000          # so viel Text wird hoechstens indexiert
_MAX_BYTES = 4 * _MAX_ZEICHEN     # so viele Rohbytes werden hoechstens dekodiert
_MAX_DATEI = 100_000_000          # darueber wird der Inhalt gar nicht extrahiert (nur Name)
_MAX_SEITEN = 2000                # PDF-Seiten-Deckel
_MAX_ENTPACKT = 200_000_000       # docx: maximale unkomprimierte Gesamtgroesse
_MAX_RATIO = 100                  # docx: maximales Entpack-Verhaeltnis je Eintrag


def _endung(name: str) -> str:
    return name.lower().rsplit(".", 1)[-1] if "." in name else ""


def _pdf_text(daten: bytes) -> str:
    try:
        from pypdf import PdfReader

        leser = PdfReader(BytesIO(daten))
        teile = []
        gesamt = 0
        for seite in leser.pages[:_MAX_SEITEN]:
            text = seite.extract_text() or ""
            teile.append(text)
            gesamt += len(text)
            if gesamt >= _MAX_ZEICHEN:
                break
        return "\n".join(teile)
    except Exception:
        return ""


def _docx_text(daten: bytes) -> str:
    try:
        # Zip-Bombe abwehren, bevor python-docx den Baum vollstaendig aufbaut.
        with zipfile.ZipFile(BytesIO(daten)) as zf:
            gesamt = 0
            for eintrag in zf.infolist():
                gesamt += eintrag.file_size
                if eintrag.compress_size > 0 and \
                        eintrag.file_size / eintrag.compress_size > _MAX_RATIO:
                    return ""
            if gesamt > _MAX_ENTPACKT:
                return ""

        from docx import Document

        dok = Document(BytesIO(daten))
        teile = []
        gesamt = 0
        for absatz in dok.paragraphs:
            teile.append(absatz.text)
            gesamt += len(absatz.text)
            if gesamt >= _MAX_ZEICHEN:
                break
        return "\n".join(teile)
    except Exception:
        return ""


def text_extrahieren(name: str, daten: bytes) -> str:
    if len(daten) > _MAX_DATEI:
        return ""  # zu gross: nur der Name wird indexiert
    endung = _endung(name)
    if endung in _TEXT_ENDUNGEN:
        text = daten[:_MAX_BYTES].decode("utf-8", errors="ignore")
    elif endung == "pdf":
        text = _pdf_text(daten)
    elif endung == "docx":
        text = _docx_text(daten)
    else:
        text = ""
    # PostgreSQL-Textfelder vertragen keine NUL-Bytes (0x00). Sie tauchen etwa in
    # UTF-16-Texten oder falsch benannten Binaerdateien auf - durch Leerzeichen
    # ersetzen, damit die Indexierung nicht abbricht (Tokens bleiben getrennt).
    return text[:_MAX_ZEICHEN].replace("\x00", " ")
