"""Dateisystem-Adapter fuer den BlobStore-Port.

Layout: <wurzel>/<benutzer_id>/<hash[:2]>/<hash>. Pool pro Nutzer isoliert
(kein Cross-User-Dedup, kein Info-Leak). Schreiben ist atomar (temp + fsync +
rename), damit ein Absturz nie einen halben Block hinterlaesst.

Volume-Marker: am Pool-Wurzelverzeichnis liegt eine Datei .kellerwolke_pool mit
einer UUID, die zugleich in der DB steht. Vor jedem put/get/delete wird geprueft,
ob diese Datei da ist und passt - nur dann ist BEWIESEN, dass das richtige
Laufwerk gemountet ist. Fehlt der Mount (abgehaengter Mountpoint = leeres
Verzeichnis auf der Systemplatte), schlaegt die Pruefung fehl und es wird gar
nicht geschrieben, statt still auf die falsche Platte auszuweichen.
"""

import hashlib
import os
import tempfile
from pathlib import Path

from app.ports import SpeicherNichtVerfuegbar

MARKER_DATEI = ".kellerwolke_pool"

_UNGESETZT = object()  # Sentinel: "Parameter nicht uebergeben" vs. ausdruecklich None


class FilesystemBlobStore:
    def __init__(self, wurzel, marker=None) -> None:
        self.wurzel = Path(wurzel)
        self._marker = marker

    def setze_wurzel(self, neu, marker=_UNGESETZT) -> None:
        """Wechselt die Pool-Wurzel zur Laufzeit (nach dem Verschieben der
        Datenablage auf ein anderes Laufwerk). Wird marker uebergeben, wird der
        erwartete Marker mitgewechselt; sonst bleibt der bisherige bestehen."""
        self.wurzel = Path(neu)
        if marker is not _UNGESETZT:
            self._marker = marker

    @property
    def marker(self):
        return self._marker

    def _marker_pfad(self) -> Path:
        return self.wurzel / MARKER_DATEI

    def marker_schreiben(self, marker: str) -> None:
        """Legt die Marker-Datei am Pool-Wurzelverzeichnis an (Erst-Einrichtung
        oder Adoption eines bestehenden Pools). Setzt zugleich den erwarteten
        Marker. Nur aufrufen, wenn das richtige Laufwerk gemountet ist."""
        self.wurzel.mkdir(parents=True, exist_ok=True)
        self._marker_pfad().write_text(marker)
        self._marker = marker

    def verfuegbar(self) -> bool:
        """True nur, wenn die Marker-Datei der echten Platte da ist und passt."""
        if not self._marker:
            return False
        try:
            return self._marker_pfad().read_text().strip() == self._marker
        except OSError:
            return False

    def _sichern(self) -> None:
        if not self.verfuegbar():
            raise SpeicherNichtVerfuegbar(
                f"Objekt-Pool nicht erreichbar: {self.wurzel}"
            )

    def _pfad(self, benutzer_id: str, blob_hash: str) -> Path:
        return self.wurzel / benutzer_id / blob_hash[:2] / blob_hash

    def put(self, benutzer_id: str, daten: bytes) -> tuple[str, bool]:
        """Legt die Bytes ab und liefert (hash, neu_geschrieben). neu_geschrieben
        ist False, wenn der Block schon vorhanden war (Dedup)."""
        self._sichern()
        blob_hash = hashlib.sha256(daten).hexdigest()
        ziel = self._pfad(benutzer_id, blob_hash)
        if ziel.exists():
            return blob_hash, False
        ziel.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(ziel.parent))
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(daten)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, ziel)
            self._verzeichnis_fsync(ziel.parent)
        except BaseException:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise
        return blob_hash, True

    @staticmethod
    def _verzeichnis_fsync(ordner: Path) -> None:
        """Macht den Verzeichnis-Eintrag nach dem Rename dauerhaft (Crash-
        Sicherheit). Auf Dateisystemen ohne Verzeichnis-fsync (z.B. exFAT)
        bestmoeglich - Fehler werden ignoriert."""
        try:
            dfd = os.open(str(ordner), os.O_DIRECTORY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass

    def get(self, benutzer_id: str, blob_hash: str) -> bytes:
        self._sichern()
        return self._pfad(benutzer_id, blob_hash).read_bytes()

    def exists(self, benutzer_id: str, blob_hash: str) -> bool:
        return self._pfad(benutzer_id, blob_hash).exists()

    def delete(self, benutzer_id: str, blob_hash: str) -> None:
        self._sichern()
        try:
            self._pfad(benutzer_id, blob_hash).unlink()
        except FileNotFoundError:
            pass
