"""Plugin-Verwaltung: App-Leiste (Nutzer) + Aktivieren/Deinstallieren (Admin).

Aktiv/Inaktiv-Aenderungen wirken beim naechsten Neustart (Starlette entfernt
Router zur Laufzeit nicht sauber) - die Antworten sagen das ehrlich.
"""

from fastapi import APIRouter, Depends, Query, Request

from app import plugins as plugin_lader
from app.abhaengig import aktueller_admin, aktueller_benutzer
from module.plugins.modelle import AppAus, PluginAus

router = APIRouter(prefix="/api/v1", tags=["plugins"])


@router.get("/plugins", response_model=list[AppAus])
async def app_leiste(request: Request, benutzer=Depends(aktueller_benutzer)):
    """Aktive Ansichts-Apps fuer die App-Leiste unter dem Suchfeld."""
    eintraege = getattr(request.app.state, "plugins", {}).values()
    return [
        AppAus(
            id=e["manifest"].id,
            name=e["manifest"].name,
            icon=e["manifest"].icon,
            kategorie=e["manifest"].kategorie,
        )
        for e in eintraege
        if e["aktiv"] and e["manifest"].kategorie == "ansicht-app"
    ]


@router.get("/admin/plugins", response_model=list[PluginAus])
async def liste(admin=Depends(aktueller_admin)):
    """Alle entdeckten Plugins mit Status (auch inaktive/defekte)."""
    return [PluginAus(**r) for r in await plugin_lader.alle_aus_db()]


@router.patch("/admin/plugins/{plugin_id}", status_code=204)
async def aktiv_setzen(plugin_id: str, eingabe: dict, admin=Depends(aktueller_admin)):
    # Bewusst schlicht: nur das aktiv-Flag. Wirkt beim naechsten Neustart.
    await plugin_lader.setze_aktiv(plugin_id, bool(eingabe.get("aktiv", False)))


@router.delete("/admin/plugins/{plugin_id}", status_code=204)
async def deinstallieren(
    plugin_id: str,
    daten: str = Query("behalten", pattern="^(loeschen|behalten)$"),
    admin=Depends(aktueller_admin),
):
    # daten=loeschen -> DROP SCHEMA plugin_<id> CASCADE; sonst Daten behalten.
    await plugin_lader.deinstalliere(plugin_id, daten_loeschen=(daten == "loeschen"))
