"""Textextraktion fuer die Volltextsuche.

Aus gaengigen Formaten wird Text gewonnen (Klartext/Code direkt, PDF, docx),
Binaerformate liefern leeren Text (dann zaehlt nur der Dateiname). Fehlerhafte
Dateien duerfen die Indexierung nicht zum Absturz bringen - im Zweifel "".
"""

from io import BytesIO

_TEXT_ENDUNGEN = {
    "txt", "md", "markdown", "csv", "tsv", "log", "json", "xml", "yaml", "yml",
    "ini", "cfg", "conf", "toml", "py", "js", "ts", "tsx", "jsx", "svelte", "vue",
    "java", "c", "cpp", "h", "hpp", "go", "rs", "rb", "php", "sh", "sql", "html",
    "css", "scss",
}

_MAX_ZEICHEN = 1_000_000


def _endung(name: str) -> str:
    return name.lower().rsplit(".", 1)[-1] if "." in name else ""


def _pdf_text(daten: bytes) -> str:
    try:
        from pypdf import PdfReader

        leser = PdfReader(BytesIO(daten))
        return "\n".join((seite.extract_text() or "") for seite in leser.pages)
    except Exception:
        return ""


def _docx_text(daten: bytes) -> str:
    try:
        from docx import Document

        dok = Document(BytesIO(daten))
        return "\n".join(absatz.text for absatz in dok.paragraphs)
    except Exception:
        return ""


def text_extrahieren(name: str, daten: bytes) -> str:
    endung = _endung(name)
    if endung in _TEXT_ENDUNGEN:
        text = daten.decode("utf-8", errors="ignore")
    elif endung == "pdf":
        text = _pdf_text(daten)
    elif endung == "docx":
        text = _docx_text(daten)
    else:
        text = ""
    return text[:_MAX_ZEICHEN]
