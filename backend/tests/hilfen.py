"""Gemeinsame Test-Hilfen."""

from app.adapters.filesystem_blobstore import FilesystemBlobStore


def markierter_blobstore(pfad):
    """BlobStore mit gesetztem Volume-Marker - in Tests immer 'verfuegbar', wie
    nach der Erst-Einrichtung. Ohne Marker wuerde jeder Zugriff bewusst
    abgewiesen (Schutz vor Schreiben auf eine abgehaengte Platte)."""
    s = FilesystemBlobStore(pfad)
    s.marker_schreiben("test-marker")
    return s
