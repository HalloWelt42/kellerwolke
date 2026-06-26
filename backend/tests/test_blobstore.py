"""Tests fuer den FilesystemBlobStore: Inhaltsadressierung, Dedup pro Nutzer,
Isolation zwischen Nutzern, Roundtrip."""

from app.adapters.filesystem_blobstore import FilesystemBlobStore


def _dateien(pfad):
    return [p for p in pfad.rglob("*") if p.is_file()]


def test_dedup_innerhalb_eines_nutzers(tmp_path):
    store = FilesystemBlobStore(tmp_path)
    h1 = store.put("nutzer1", b"hallo welt")
    h2 = store.put("nutzer1", b"hallo welt")
    assert h1 == h2
    # Gleicher Inhalt, egal wie oft: nur ein physischer Block im Pool.
    assert len(_dateien(tmp_path / "nutzer1")) == 1


def test_isolation_zwischen_nutzern(tmp_path):
    store = FilesystemBlobStore(tmp_path)
    h1 = store.put("nutzer1", b"geheim")
    h2 = store.put("nutzer2", b"geheim")
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


def test_roundtrip_beliebige_bytes(tmp_path):
    store = FilesystemBlobStore(tmp_path)
    daten = b"beliebige bytes \x00\x01\x02 mit Umlaut \xc3\xa4"
    blob_hash = store.put("u", daten)
    assert store.get("u", blob_hash) == daten


def test_get_fehlt_wirft(tmp_path):
    store = FilesystemBlobStore(tmp_path)
    try:
        store.get("u", "0" * 64)
        assert False, "haette FileNotFoundError werfen muessen"
    except FileNotFoundError:
        pass
