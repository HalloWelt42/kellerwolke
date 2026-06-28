"""Tests der Plugin-Installation aus ZIP: Manifest-Suche, Zip-Slip-Schutz,
Happy-Path (Dateien landen in den Plugin-Ordnern, Registry-Eintrag inaktiv),
Duplikat-Schutz und sauberes Zuruecksetzen bei Fehlern.

Die Plugin-Zielordner werden per monkeypatch auf tmp_path umgebogen, damit der
echte Projektbaum (backend/plugins, frontend/src/plugins) unberuehrt bleibt.
"""

import io
import json
import zipfile

import pytest

from app import db as dbmod
from app import plugins


def _zip(dateien: dict[str, bytes]) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        for name, inhalt in dateien.items():
            z.writestr(name, inhalt)
    return puffer.getvalue()


def _manifest(pid: str = "testapp", **extra) -> bytes:
    m = {
        "id": pid,
        "name": "Testapp",
        "version": "1.0.0",
        "kategorie": "ansicht-app",
        "icon": "fa-solid fa-flask",
        "backend_entry": "",
        "frontend_entry": "plugin.ts",
        "kern_min": "0.40.0",
    }
    m.update(extra)
    return json.dumps(m).encode("utf-8")


# --- reine Logik (keine DB) -------------------------------------------------


def test_manifest_eintrag_nimmt_aeussersten():
    namen = ["wrap/backend/plugin.json", "plugin.json", "frontend/x.ts"]
    assert plugins._manifest_eintrag(namen) == "plugin.json"


def test_manifest_eintrag_im_wurzelordner():
    namen = ["meinplugin/plugin.json", "meinplugin/backend/api.py"]
    assert plugins._manifest_eintrag(namen) == "meinplugin/plugin.json"


def test_manifest_eintrag_fehlt():
    assert plugins._manifest_eintrag(["readme.txt", "backend/api.py"]) is None


def test_ziel_im_baum_blockt_zip_slip(tmp_path):
    with pytest.raises(ValueError):
        plugins._ziel_im_baum(tmp_path, "../evil.txt")


def test_ziel_im_baum_blockt_absoluten_ausbruch(tmp_path):
    with pytest.raises(ValueError):
        plugins._ziel_im_baum(tmp_path, "a/../../b.txt")


def test_ziel_im_baum_erlaubt_unterordner(tmp_path):
    ziel = plugins._ziel_im_baum(tmp_path, "a/b.txt")
    assert str(ziel).startswith(str(tmp_path.resolve()))


# --- Integration (DB + tmp-Ordner) -----------------------------------------


@pytest.fixture
def plugin_ordner(tmp_path, pool, monkeypatch):
    monkeypatch.setattr(plugins, "PLUGIN_DIR", tmp_path / "backend")
    monkeypatch.setattr(plugins, "FRONTEND_PLUGIN_DIR", tmp_path / "frontend")
    monkeypatch.setattr(dbmod, "_pool", pool)
    return tmp_path


async def test_installation_happy_path(plugin_ordner):
    daten = _zip(
        {
            "plugin.json": _manifest(),
            "backend/api.py": b"# leer\n",
            "backend/schema/001.sql": b"CREATE TABLE IF NOT EXISTS foo (id int);",
            "frontend/plugin.ts": b"export default {}\n",
            "liesmich.txt": b"wird ignoriert",
        }
    )
    info = await plugins.installiere_aus_zip(daten)
    assert info["id"] == "testapp"
    assert info["aktiv"] is False
    assert info["quelle"] == "upload"
    assert info["icon"] == "fa-solid fa-flask"

    assert (plugin_ordner / "backend" / "testapp" / "plugin.json").exists()
    assert (plugin_ordner / "backend" / "testapp" / "api.py").exists()
    assert (plugin_ordner / "backend" / "testapp" / "schema" / "001.sql").exists()
    assert (plugin_ordner / "frontend" / "testapp" / "plugin.ts").exists()
    # Datei neben backend/frontend wird NICHT uebernommen.
    assert not (plugin_ordner / "backend" / "testapp" / "liesmich.txt").exists()

    eintraege = await plugins.alle_aus_db()
    assert any(e["id"] == "testapp" and not e["aktiv"] for e in eintraege)


async def test_installation_mit_wurzelordner(plugin_ordner):
    # Wer den Plugin-Ordner selbst zippt, bekommt einen Praefix - muss trotzdem gehen.
    daten = _zip(
        {
            "testapp/plugin.json": _manifest(),
            "testapp/frontend/plugin.ts": b"x",
        }
    )
    info = await plugins.installiere_aus_zip(daten)
    assert info["id"] == "testapp"
    assert (plugin_ordner / "frontend" / "testapp" / "plugin.ts").exists()


async def test_installation_doppelt_scheitert(plugin_ordner):
    daten = _zip({"plugin.json": _manifest(), "frontend/plugin.ts": b"x"})
    await plugins.installiere_aus_zip(daten)
    with pytest.raises(FileExistsError):
        await plugins.installiere_aus_zip(daten)


async def test_ungueltige_id_scheitert(plugin_ordner):
    daten = _zip({"plugin.json": _manifest(pid="Boese-ID!"), "frontend/plugin.ts": b"x"})
    with pytest.raises(ValueError):
        await plugins.installiere_aus_zip(daten)


async def test_kein_manifest_scheitert(plugin_ordner):
    daten = _zip({"frontend/plugin.ts": b"x"})
    with pytest.raises(ValueError):
        await plugins.installiere_aus_zip(daten)


async def test_zip_slip_wird_abgewiesen(plugin_ordner):
    daten = _zip(
        {
            "plugin.json": _manifest(),
            "backend/../../../evil.txt": b"boom",
        }
    )
    with pytest.raises(ValueError):
        await plugins.installiere_aus_zip(daten)
    # Nichts darf zurueckbleiben: keine Ordner, kein Registry-Eintrag.
    assert not (plugin_ordner / "backend" / "testapp").exists()
    assert not (plugin_ordner / "frontend" / "testapp").exists()
    eintraege = await plugins.alle_aus_db()
    assert not any(e["id"] == "testapp" for e in eintraege)


async def test_defektes_zip_scheitert(plugin_ordner):
    with pytest.raises(ValueError):
        await plugins.installiere_aus_zip(b"das ist kein zip")
