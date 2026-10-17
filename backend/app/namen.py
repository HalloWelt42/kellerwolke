"""Namen in einer Form: Unicode NFC. macOS liefert Dateinamen zerlegt (NFD, "u" und Trema getrennt); ohne Ausgleich
gäbe es zwei gleich aussehende Dateien in einem Ordner, und die Suche nach "grün" fände "grün" in der anderen Form
nicht. Angewandt, wo Namen gespeichert, gesucht oder verglichen werden (Repository, Suche).
"""

import unicodedata


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text) if text else text
