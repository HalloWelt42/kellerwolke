"""Tests fuer die verschaerften Repo-Barrieren in tools/checks/regeln.py:
Doppelbindestrich, Umlaut-Komposita, Geheimnis-Muster, Tilde-Fences,
entschaerfter Konflikt-Marker."""

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WURZEL / "tools" / "checks"))

import regeln  # noqa: E402


def _arten(pfad, text):
    return {art for _, art, _ in regeln.pruefe_datei(pfad, text)}


def test_doppelbindestrich_in_prosa():
    assert "Doppelter Bindestrich" in _arten("a.md", "Das ist gut -- oder?")


def test_doppelbindestrich_nicht_in_codeblock():
    assert "Doppelter Bindestrich" not in _arten("a.md", "```\nx --flag\n```\n")


def test_doppelbindestrich_nicht_in_struktur():
    assert "Doppelter Bindestrich" not in _arten("a.md", "---\n")
    assert "Doppelter Bindestrich" not in _arten("a.md", "| a | b |\n| --- | --- |\n")


def test_umlaut_kompositum_wird_erkannt():
    assert "ASCII-Umlaut" in _arten("a.md", "Die Ueberweisung steht aus.")
    assert "ASCII-Umlaut" in _arten("a.md", "Eine Liste der Beschaeftigten.")


def test_echte_umlaute_sind_ok():
    assert "ASCII-Umlaut" not in _arten("a.md", "Die Überweisung an die Beschäftigten.")


def test_geheimnis_privater_schluessel():
    # Marker zusammensetzen, damit das Literal nicht im Quelltext steht
    # (sonst wuerde die eigene Geheimnis-Barriere diese Testdatei blocken).
    marker = "-----BEGIN " + "PRIVATE KEY-----"
    assert "Geheimnis" in _arten("x.py", marker)


def test_geheimnis_kein_fehlalarm_auf_platzhalter():
    assert "Geheimnis" not in _arten(".env.muster", 'SECRET="entwicklung-unsicher"')


def test_setext_ueberschrift_ist_kein_konflikt():
    assert "Merge-Konflikt" not in _arten("a.md", "Titel\n=======\nText")


def test_echter_konflikt_wird_erkannt():
    assert "Merge-Konflikt" in _arten("a.py", "<<<<<<< HEAD\n")


def test_tilde_fence_blendet_code_aus():
    assert "ASCII-Umlaut" not in _arten("a.md", "~~~\nfuer x in y\n~~~\n")
