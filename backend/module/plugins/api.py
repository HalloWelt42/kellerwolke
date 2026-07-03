"""Plugin-Verwaltung: App-Leiste (Nutzer) + Aktivieren/Deinstallieren (Admin).

Aktiv/Inaktiv-Aenderungen wirken beim naechsten Neustart (Starlette entfernt
Router zur Laufzeit nicht sauber) - die Antworten sagen das ehrlich.
"""

import asyncio
import os
import sys

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from app import plugins as plugin_lader
from app.abhaengig import aktueller_admin, aktueller_benutzer
from module.plugins.modelle import AppAus, PluginAus

router = APIRouter(prefix="/api/v1", tags=["plugins"])

# Obergrenze fuer das hochgeladene Archiv (komprimiert).
MAX_UPLOAD = 40 * 1024 * 1024


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
async def liste(request: Request, admin=Depends(aktueller_admin)):
    """Alle entdeckten Plugins mit Status, behandelten Medientypen und
    Konflikten (andere aktive Plugins, die dieselben Typen behandeln)."""
    zeilen = await plugin_lader.alle_aus_db()
    geladen = getattr(request.app.state, "plugins", {})

    def behandelt_von(pid: str) -> list[str]:
        e = geladen.get(pid)
        return list(getattr(e["manifest"], "behandelt", []) or []) if e else []

    aktive = [(z["id"], z["name"], set(behandelt_von(z["id"]))) for z in zeilen if z["aktiv"]]
    ergebnis = []
    for z in zeilen:
        beh = behandelt_von(z["id"])
        konflikt = []
        if z["aktiv"] and beh:
            meine = set(beh)
            konflikt = [name for oid, name, typen in aktive if oid != z["id"] and (meine & typen)]
        ergebnis.append(PluginAus(**z, behandelt=beh, konflikt=konflikt))
    return ergebnis


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


@router.post("/admin/plugins/upload", response_model=PluginAus, status_code=201)
async def hochladen(archiv: UploadFile = File(...), admin=Depends(aktueller_admin)):
    """Installiert ein Plugin aus einem ZIP-Archiv (inaktiv). Aktivierung und
    Neustart bleiben ein bewusster Admin-Schritt."""
    daten = await archiv.read()
    if len(daten) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="Archiv zu gross (max. 40 MB)")
    try:
        info = await plugin_lader.installiere_aus_zip(daten)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PluginAus(**info)


@router.post("/admin/neustart", status_code=202)
async def neustart(admin=Depends(aktueller_admin)):
    """Startet den Backend-Prozess neu (execv), damit Plugin-Aenderungen sofort
    wirken. Antwortet zuerst; der eigentliche Neustart folgt eine halbe Sekunde
    spaeter, damit die Antwort noch rausgeht. Die Oberflaeche wartet dann auf die
    Gesundheitspruefung und laedt neu."""
    async def _tue_es():
        await asyncio.sleep(0.5)
        os.execv(sys.executable, [sys.executable, "-m", "uvicorn", *sys.argv[1:]])

    asyncio.create_task(_tue_es())
    return {"status": "neustart"}
