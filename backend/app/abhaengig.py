"""FastAPI-Abhaengigkeiten: Dienste aus app.state ziehen und Auth durchsetzen.

Die Dienste werden im Lebenszyklus (oder im Test) in app.state abgelegt; die
Routen holen sie ueber diese kleinen Funktionen. So bleibt die Verdrahtung
testbar und ohne globale Singletons.
"""

from dataclasses import replace
from uuid import UUID

from fastapi import HTTPException, Request

from module.geraete.dienst import ist_geraeteschluessel

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


def hole_uploads(request: Request):
    return request.app.state.uploads


def hole_geraete(request: Request):
    return request.app.state.geraete


def absender(request: Request) -> str | None:
    """Die Adresse des Absenders (hinter dem Caddy vorne die echte, uvicorn liest dessen Weiterleitungskopf)."""
    return request.client.host if request.client else None


async def benutzer_zum_token(request: Request, token: str) -> dict | None:
    """Wer zu einem Token gehört: eine Sitzung (Anmeldung mit Passwort) oder der Schlüssel eines gekoppelten Geräts.
    Beide kommen im selben Kopf und im selben Lese-Cookie; nur hier wird unterschieden."""
    if ist_geraeteschluessel(token):
        return await request.app.state.geraete.pruefen(token, absender(request))
    return await request.app.state.auth.sitzung_pruefen(token)


async def token_beenden(request: Request, token: str) -> None:
    """Abmelden: die Sitzung endet, ein gekoppeltes Gerät trennt sich."""
    if ist_geraeteschluessel(token):
        await request.app.state.geraete.trennen_per_schluessel(token)
    else:
        await request.app.state.auth.abmelden(token)


async def aktueller_benutzer(request: Request) -> dict:
    token = request.headers.get("x-kellerwolke-sitzung", "")
    benutzer = await benutzer_zum_token(request, token)
    if not benutzer:
        raise HTTPException(status_code=401, detail="Anmeldung erforderlich")
    return benutzer


async def lese_benutzer(request: Request) -> dict:
    """Für Inhaltsadressen (<img>, <audio>, <video>, Download-Links): der Lesezugang als Cookie oder der Sitzungskopf."""
    token = request.headers.get("x-kellerwolke-sitzung") or request.cookies.get(LESEZUGANG_COOKIE, "")
    benutzer = await benutzer_zum_token(request, token)
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
    anfrage_id = request.headers.get("x-kellerwolke-anfrage", "").strip()
    if anfrage_id:
        # Beruft sich die App auf eine Anfrage, gilt sie nur, solange diese offen ist (Recht je Auftrag).
        try:
            anfrage = await request.app.state.anfragen.gueltige(akteur, UUID(anfrage_id))
        except ValueError:
            anfrage = None
        if anfrage is None:
            raise HTTPException(status_code=403, detail="Diese Anfrage ist nicht (mehr) offen")
        akteur = replace(akteur, anfrage=anfrage)
    return akteur


def hole_anfragen(request: Request):
    return request.app.state.anfragen
