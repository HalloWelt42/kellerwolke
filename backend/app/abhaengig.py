"""FastAPI-Abhaengigkeiten: Dienste aus app.state ziehen und Auth durchsetzen.

Die Dienste werden im Lebenszyklus (oder im Test) in app.state abgelegt; die
Routen holen sie ueber diese kleinen Funktionen. So bleibt die Verdrahtung
testbar und ohne globale Singletons.
"""

from fastapi import HTTPException, Request

# Cookie des Lesezugangs für Inhaltsadressen (gesetzt von module/inhalt/api.py, nur für deren Pfad).
LESEZUGANG_COOKIE = "kw_inhalt"


def hole_auth(request: Request):
    return request.app.state.auth


def hole_speicher(request: Request):
    return request.app.state.speicher


def hole_suche(request: Request):
    return request.app.state.suche


def hole_vorgaenge(request: Request):
    return request.app.state.vorgaenge


def hole_appzugang(request: Request):
    return request.app.state.appzugang


def hole_ablage(request: Request):
    return request.app.state.ablage


def hole_melder(request: Request):
    return request.app.state.melder


def hole_medien(request: Request):
    return request.app.state.medien


async def aktueller_benutzer(request: Request) -> dict:
    token = request.headers.get("x-kellerwolke-sitzung", "")
    benutzer = await request.app.state.auth.sitzung_pruefen(token)
    if not benutzer:
        raise HTTPException(status_code=401, detail="Anmeldung erforderlich")
    return benutzer


async def lese_benutzer(request: Request) -> dict:
    """Für Inhaltsadressen (<img>, <audio>, <video>, Download-Links): der Lesezugang als Cookie oder der Sitzungskopf."""
    token = request.headers.get("x-kellerwolke-sitzung") or request.cookies.get(LESEZUGANG_COOKIE, "")
    benutzer = await request.app.state.auth.sitzung_pruefen(token)
    if not benutzer:
        raise HTTPException(status_code=401, detail="Anmeldung erforderlich")
    return benutzer


async def aktueller_admin(request: Request) -> dict:
    benutzer = await aktueller_benutzer(request)
    if benutzer["rolle"] != "admin":
        raise HTTPException(status_code=403, detail="Nur für Admins")
    return benutzer


async def aktuelle_app(request: Request):
    """Eine eigene App mit ihrem Schlüssel (`Authorization: Bearer kw_app_...`); nur für die Ablage-Schnittstelle."""
    kopf = request.headers.get("authorization", "")
    schluessel = kopf[7:].strip() if kopf.lower().startswith("bearer ") else ""
    akteur = await request.app.state.appzugang.pruefen(schluessel)
    if akteur is None:
        raise HTTPException(status_code=401, detail="App-Schlüssel fehlt, ist unbekannt oder gesperrt")
    return akteur
