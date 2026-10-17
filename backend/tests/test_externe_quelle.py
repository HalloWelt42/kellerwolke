"""Tests fuer die externe read-only Quelle: Auflisten, Lesen, Schutz gegen
Pfad-Ausbruch. Laeuft lokal gegen einen Testordner (kein Pi noetig)."""

import pytest

from app.adapters.externe_quelle import DateibaumQuelle


def _baum(wurzel):
    (wurzel / "unterordner").mkdir()
    (wurzel / "datei.txt").write_bytes(b"hallo")
    (wurzel / "unterordner" / "tief.txt").write_bytes(b"tief")


def test_auflisten_ordner_zuerst(tmp_path):
    _baum(tmp_path)
    quelle = DateibaumQuelle(tmp_path)
    eintraege = quelle.auflisten("")
    namen = [e.name for e in eintraege]
    assert namen == ["unterordner", "datei.txt"]
    assert eintraege[0].ist_ordner is True
    assert eintraege[1].groesse == 5


def test_lesen_liefert_bytes(tmp_path):
    _baum(tmp_path)
    quelle = DateibaumQuelle(tmp_path)
    assert quelle.bereich_lesen("datei.txt", 0, 100) == b"hallo"
    assert quelle.bereich_lesen("unterordner/tief.txt", 1, 2) == b"ie"


def test_kein_ausbruch_mit_punkt_punkt(tmp_path):
    wurzel = tmp_path / "quelle"
    wurzel.mkdir()
    (tmp_path / "geheim.txt").write_bytes(b"nicht lesen")
    quelle = DateibaumQuelle(wurzel)
    with pytest.raises(PermissionError):
        quelle.bereich_lesen("../geheim.txt", 0, 10)


def test_info(tmp_path):
    _baum(tmp_path)
    quelle = DateibaumQuelle(tmp_path)
    assert quelle.info("unterordner").ist_ordner is True
    assert quelle.info("datei.txt").groesse == 5
    assert quelle.info("datei.txt").geaendert > 0


def test_nur_lesbar(tmp_path):
    """Externe Quellen werden nur gelesen, nie verändert: es gibt keinen Schreibweg."""
    quelle = DateibaumQuelle(tmp_path)
    for name in ("schreiben", "schreiben_strom", "ordner_anlegen", "loeschen"):
        assert not hasattr(quelle, name)
