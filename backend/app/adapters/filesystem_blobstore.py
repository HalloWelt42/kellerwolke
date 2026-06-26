"""Dateisystem-Adapter fuer den BlobStore-Port.

Layout: <wurzel>/<benutzer_id>/<hash[:2]>/<hash>. Pool pro Nutzer isoliert
(kein Cross-User-Dedup, kein Info-Leak). Schreiben ist atomar (temp + fsync +
rename), damit ein Absturz nie einen halben Block hinterlaesst.
"""

import hashlib
import os
import tempfile
from pathlib import Path


class FilesystemBlobStore:
    def __init__(self, wurzel) -> None:
        self.wurzel = Path(wurzel)

    def _pfad(self, benutzer_id: str, blob_hash: str) -> Path:
        return self.wurzel / benutzer_id / blob_hash[:2] / blob_hash

    def put(self, benutzer_id: str, daten: bytes) -> tuple[str, bool]:
        """Legt die Bytes ab und liefert (hash, neu_geschrieben). neu_geschrieben
        ist False, wenn der Block schon vorhanden war (Dedup)."""
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
        except BaseException:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise
        return blob_hash, True

    def get(self, benutzer_id: str, blob_hash: str) -> bytes:
        return self._pfad(benutzer_id, blob_hash).read_bytes()

    def exists(self, benutzer_id: str, blob_hash: str) -> bool:
        return self._pfad(benutzer_id, blob_hash).exists()

    def delete(self, benutzer_id: str, blob_hash: str) -> None:
        try:
            self._pfad(benutzer_id, blob_hash).unlink()
        except FileNotFoundError:
            pass
