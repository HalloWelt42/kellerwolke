"""Auth-Router: Anmelden, Abmelden, Status."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.abhaengig import hole_auth
from module.auth.modelle import AuthStatus, BenutzerAus, LoginAntwort, LoginEingabe

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginAntwort)
async def login(eingabe: LoginEingabe, auth=Depends(hole_auth)):
    token = await auth.anmelden(eingabe.kennung, eingabe.passwort)
    if not token:
        raise HTTPException(status_code=401, detail="Anmeldung fehlgeschlagen")
    benutzer = await auth.sitzung_pruefen(token)
    return LoginAntwort(token=token, benutzer=BenutzerAus.model_validate(benutzer))


@router.post("/logout", status_code=204)
async def logout(request: Request, auth=Depends(hole_auth)):
    await auth.abmelden(request.headers.get("x-kellerwolke-sitzung", ""))


@router.get("/status", response_model=AuthStatus)
async def status(request: Request, auth=Depends(hole_auth)):
    benutzer = await auth.sitzung_pruefen(request.headers.get("x-kellerwolke-sitzung", ""))
    if benutzer:
        return AuthStatus(angemeldet=True, benutzer=BenutzerAus.model_validate(benutzer))
    return AuthStatus(angemeldet=False)
