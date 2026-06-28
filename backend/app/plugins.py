"""Plugin-Lader und -Verwaltung.

Entdeckt backend/plugins/<id>/, gleicht mit der Kern-Tabelle `plugin` ab, wendet
das Plugin-Schema in einem eigenen Postgres-Schema plugin_<id> an und bindet die
Router AKTIVER, fehlerfreier Plugins ein. Jedes Plugin laeuft in eigenem
try/except: ein defektes Plugin deaktiviert nur sich selbst und wird im
Admin-Panel als defekt gemeldet - der Kern startet immer weiter.

Der Kern importiert NIE ein Plugin direkt; der einzige Weg hinein ist dieser
Lader ueber das Manifest. Aktiv/Inaktiv-Wechsel wirken beim naechsten Neustart
(Starlette entfernt Router zur Laufzeit nicht sauber).
"""

import importlib
import traceback
from pathlib import Path

from fastapi import FastAPI

from . import db
from .abhaengig import aktueller_admin, aktueller_benutzer
from .config import version
from .plugin_api import ID_MUSTER, Manifest, PluginBeschreibung, PluginKontext

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins"


def _version_tupel(v: str) -> tuple[int, ...]:
    teile = []
    for t in str(v).split("."):
        try:
            teile.append(int(t))
        except ValueError:
            teile.append(0)
    return tuple(teile)


async def plugins_laden(app: FastAPI) -> None:
    """Beim Start: alle Plugins entdecken, Registry abgleichen, aktive einbinden."""
    app.state.plugins = {}
    if not PLUGIN_DIR.exists():
        return
    for ordner in sorted(
        p for p in PLUGIN_DIR.iterdir()
        if p.is_dir() and not p.name.startswith((".", "_"))
    ):
        try:
            await _ein_plugin_laden(app, ordner)
        except Exception:  # noqa: BLE001 - ein defektes Plugin darf den Start nie verhindern
            await _als_defekt_markieren(ordner.name, traceback.format_exc())


async def _ein_plugin_laden(app: FastAPI, ordner: Path) -> None:
    manifest_pfad = ordner / "plugin.json"
    if not manifest_pfad.exists():
        return
    manifest = Manifest.model_validate_json(manifest_pfad.read_text(encoding="utf-8"))
    if not manifest.id_gueltig() or manifest.id != ordner.name:
        raise ValueError(f"Ungueltige Plugin-id '{manifest.id}' (Ordner '{ordner.name}')")

    # Registry-Eintrag holen/anlegen und Metadaten auffrischen.
    async with db.pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT aktiv FROM plugin WHERE id=%s", (manifest.id,))
            row = await cur.fetchone()
        if row is None:
            await conn.execute(
                "INSERT INTO plugin (id, name, version, kategorie, aktiv, quelle) "
                "VALUES (%s, %s, %s, %s, false, 'repo')",
                (manifest.id, manifest.name, manifest.version, manifest.kategorie),
            )
            aktiv = False
        else:
            aktiv = row[0]
            await conn.execute(
                "UPDATE plugin SET name=%s, version=%s, kategorie=%s, defekt=NULL WHERE id=%s",
                (manifest.name, manifest.version, manifest.kategorie, manifest.id),
            )

    eintrag = {"manifest": manifest, "pfad": ordner, "aktiv": aktiv, "beschreibung": None}
    app.state.plugins[manifest.id] = eintrag
    if not aktiv:
        return

    # Kern-Mindestversion pruefen.
    if _version_tupel(manifest.kern_min) > _version_tupel(version()):
        raise RuntimeError(
            f"Plugin '{manifest.id}' braucht Kern >= {manifest.kern_min}, vorhanden {version()}"
        )

    # Eigenes Schema sicherstellen + Plugin-Migrationen anwenden.
    schema_dir = ordner / "schema"
    if schema_dir.exists():
        async with db.pool().connection() as conn:
            async with conn.transaction():
                await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "plugin_{manifest.id}"')
                await db.schema_aus_ordner_anwenden(
                    conn, schema_dir, search_path=f"plugin_{manifest.id}, public"
                )

    # Backend-Teil laden (optional - reine Frontend-Plugins haben backend_entry="").
    if manifest.backend_entry:
        modulname, _, funktionsname = manifest.backend_entry.partition(":")
        modul = importlib.import_module(f"plugins.{manifest.id}.{modulname or 'api'}")
        register = getattr(modul, funktionsname or "register")
        kontext = PluginKontext(
            manifest=manifest,
            plugin_pfad=ordner,
            speicher=app.state.speicher,
            auth=app.state.auth,
            pool=app.state.pool,
            aktueller_benutzer=aktueller_benutzer,
            aktueller_admin=aktueller_admin,
        )
        beschreibung: PluginBeschreibung = register(kontext)
        if beschreibung and beschreibung.router is not None:
            app.include_router(beschreibung.router)
            app.openapi_schema = None  # OpenAPI neu bauen, damit die Routen erscheinen
        if beschreibung and beschreibung.beim_start is not None:
            await beschreibung.beim_start()
        eintrag["beschreibung"] = beschreibung


async def _als_defekt_markieren(plugin_id: str, fehler: str) -> None:
    try:
        async with db.pool().connection() as conn:
            await conn.execute(
                "UPDATE plugin SET aktiv=false, defekt=%s WHERE id=%s", (fehler[:4000], plugin_id)
            )
    except Exception:  # noqa: BLE001 - selbst das darf den Start nicht stoppen
        pass


async def plugins_stoppen(app: FastAPI) -> None:
    for eintrag in getattr(app.state, "plugins", {}).values():
        beschreibung = eintrag.get("beschreibung")
        if beschreibung and beschreibung.beim_stop is not None:
            try:
                await beschreibung.beim_stop()
            except Exception:  # noqa: BLE001
                pass


# --- Verwaltung (vom Admin-Router genutzt) ----------------------------------

async def alle_aus_db() -> list[dict]:
    async with db.pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, version, kategorie, aktiv, defekt, quelle FROM plugin ORDER BY name"
            )
            spalten = [c.name for c in cur.description]
            return [dict(zip(spalten, r)) for r in await cur.fetchall()]


async def setze_aktiv(plugin_id: str, aktiv: bool) -> None:
    async with db.pool().connection() as conn:
        await conn.execute("UPDATE plugin SET aktiv=%s WHERE id=%s", (aktiv, plugin_id))


async def deinstalliere(plugin_id: str, daten_loeschen: bool) -> None:
    """Entfernt den Registry-Eintrag und - bei daten_loeschen - das gesamte
    Plugin-Schema in EINER Anweisung (DROP SCHEMA CASCADE). Der Ordner bleibt
    bei Repo-Plugins unangetastet (versionierter Code)."""
    if not ID_MUSTER.match(plugin_id):
        raise ValueError("Ungueltige Plugin-id")
    async with db.pool().connection() as conn:
        if daten_loeschen:
            await conn.execute(f'DROP SCHEMA IF EXISTS "plugin_{plugin_id}" CASCADE')
        await conn.execute("DELETE FROM plugin WHERE id=%s", (plugin_id,))
