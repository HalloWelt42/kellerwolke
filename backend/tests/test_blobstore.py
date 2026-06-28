"""Tests fuer den FilesystemBlobStore: Inhaltsadressierung, Dedup pro Nutzer,
Isolation zwischen Nutzern, Roundtrip."""

import pytest

from app.adapters.filesystem_blobstore import FilesystemBlobStore
from app.ports import SpeicherNichtVerfuegbar


def _dateien(pfad):
    return [p for p in pfad.rglob("*") if p.is_file()]


@pytest.fixture
def store(tmp_path):
    # Verfuegbarer Pool: Marker gesetzt + Marker-Datei geschrieben (wie nach der
    # Erst-Einrichtung). Ohne Marker wuerde jeder Zugriff bewusst abgewiesen.
    s = FilesystemBlobStore(tmp_path)
    s.marker_schreiben("test-marker")
    return s


def test_dedup_innerhalb_eines_nutzers(store, tmp_path):
    h1, neu1 = store.put("nutzer1", b"hallo welt")
    h2, neu2 = store.put("nutzer1", b"hallo welt")
    assert h1 == h2
    assert neu1 is True and neu2 is False  # zweites Mal Dedup, kein Schreiben
    # Gleicher Inhalt, egal wie oft: nur ein physischer Block im Pool.
    assert len(_dateien(tmp_path / "nutzer1")) == 1


def test_isolation_zwischen_nutzern(store, tmp_path):
    h1, _ = store.put("nutzer1", b"geheim")
    h2, _ = store.put("nutzer2", b"geheim")
    assert h1 == h2  # gleicher Hash bei gleichem Inhalt
    assert store.exists("nutzer1", h1)
    assert store.exists("nutzer2", h2)
    # Getrennte Pools: je ein Block, kein gemeinsamer Speicher.
    assert len(_dateien(tmp_path / "nutzer1")) == 1
    assert len(_dateien(tmp_path / "nutzer2")) == 1
    # Loeschen bei einem Nutzer beruehrt den anderen nicht.
    store.delete("nutzer1", h1)
    assert not store.exists("nutzer1", h1)
    assert store.exists("nutzer2", h2)


def test_roundtrip_beliebige_bytes(store):
    daten = b"beliebige bytes \x00\x01\x02 mit Umlaut \xc3\xa4"
    blob_hash, neu = store.put("u", daten)
    assert neu is True
    assert store.get("u", blob_hash) == daten


def test_get_fehlt_wirft(store):
    try:
        store.get("u", "0" * 64)
        assert False, "haette FileNotFoundError werfen muessen"
    except FileNotFoundError:
        pass


def test_abgehaengter_pool_wirft(tmp_path):
    # Marker konfiguriert, aber Datei fehlt (Laufwerk abgehaengt): jeder Zugriff
    # wird abgewiesen, statt still auf die falsche Platte zu schreiben.
    s = FilesystemBlobStore(tmp_path)
    s.marker_schreiben("echt")
    (tmp_path / ".kellerwolke_pool").unlink()  # Mount "verschwindet"
    assert s.verfuegbar() is False
    with pytest.raises(SpeicherNichtVerfuegbar):
        s.put("u", b"daten")
    with pytest.raises(SpeicherNichtVerfuegbar):
        s.get("u", "0" * 64)
    with pytest.raises(SpeicherNichtVerfuegbar):
        s.delete("u", "0" * 64)
