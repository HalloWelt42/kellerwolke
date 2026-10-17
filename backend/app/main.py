"""FastAPI-Einstieg. Bewusst duenn: oeffnet den DB-Pool, legt die Dienste in
app.state ab, bindet die Modul-Router ein.

Strikte Trennung: hier entsteht ausschliesslich die REST-API. Die Oberflaeche
(Svelte) ist eine eigenstaendige Anwendung und spricht nur diese API.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import db
from . import io_pool
from . import plugins as plugin_lader
from .adapters.filesystem_blobstore import FilesystemBlobStore
from .config import EINSTELLUNGEN, version
from .melder import JournalMelder
from .ports import SpeicherNichtVerfuegbar
from .validierung import validierung_behandeln
from module.ablage.api import router as ablage_router
from module.ablage.dienst import AblageDienst
from module.admin.api import router as admin_router
from module.appzugang.api import router as appzugang_router
from module.appzugang.dienst import AppZugangDienst
from module.auth.api import router as auth_router
from module.auth.dienst import AuthDienst
from module.speicher.api import router as datei_router
from module.speicher.dienst import SpeicherDienst
from module.suche.api import router as suche_router
from module.suche.dienst import SuchDienst
from module.plugins.api import router as plugins_router
from module.sync.api import router as sync_router
from module.vorgaenge.api import router as vorgaenge_router
from module.vorgaenge.dienst import VorgangRegistry
from webdav.adapter import webdav_einbinden


async def _admin_seed(auth: AuthDienst) -> None:
    """Legt beim ersten Start ein Admin-Konto an, wenn konfiguriert und noch
    kein Konto existiert (Bootstrap)."""
    if not EINSTELLUNGEN.admin_name or not EINSTELLUNGEN.admin_passwort:
        return
    if await auth.liste_benutzer():
        return
    await auth.benutzer_anlegen(
        EINSTELLUNGEN.admin_name, EINSTELLUNGEN.admin_passwort, rolle="admin"
    )


async def _journal_pflegen(speicher) -> None:
    """Räumt alte Journal-Einträge beim Start und dann täglich auf (Grenze KELLERWOLKE_JOURNAL_TAGE)."""
    while True:
        try:
            weg = await speicher.journal_aufraeumen(EINSTELLUNGEN.journal_tage)
            if weg:
                logging.getLogger("kellerwolke").info("Journal: %d alte Einträge aufgeräumt", weg)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger("kellerwolke").exception("Journal aufräumen fehlgeschlagen")
        await asyncio.sleep(24 * 3600)


@asynccontextmanager
async def lebenszyklus(app: FastAPI):
    await db.starten()
    pool = db.pool()
    app.state.pool = pool
    app.state.auth = AuthDienst(pool)
    app.state.speicher = SpeicherDienst(pool, FilesystemBlobStore(EINSTELLUNGEN.objekt_pfad))
    # Aktiven Pool-Pfad + Volume-Marker aus der DB ziehen (oder beim Erststart mit
    # dem Standard aus .env seeden), BlobStore konfigurieren. So uebersteht ein
    # verschobener Speicherort einen Neustart und ein fehlender Mount fuehrt zu
    # "nicht verfuegbar" statt zum stillen Schreiben auf die Systemplatte.
    await app.state.speicher.speicher_initialisieren(EINSTELLUNGEN.objekt_pfad)
    app.state.suche = SuchDienst(pool)
    app.state.vorgaenge = VorgangRegistry()
    app.state.appzugang = AppZugangDienst(pool, app.state.speicher)
    app.state.ablage = AblageDienst(pool, app.state.speicher, app.state.appzugang)
    app.state.melder = JournalMelder(EINSTELLUNGEN.dsn)
    app.state.melder.starten()
    journal_pflege = asyncio.create_task(_journal_pflegen(app.state.speicher), name="journal-pflege")
    await _admin_seed(app.state.auth)
    # Plugins entdecken + aktive einbinden (jedes isoliert; ein defektes Plugin
    # deaktiviert nur sich selbst, der Kern startet weiter).
    await plugin_lader.plugins_laden(app)
    try:
        yield
    finally:
        await plugin_lader.plugins_stoppen(app)
        journal_pflege.cancel()
        await app.state.melder.stoppen()
        await app.state.vorgaenge.stoppen()
        io_pool.herunterfahren()
        await db.stoppen()


def app_bauen() -> FastAPI:
    app = FastAPI(title="Kellerwolke", version=version(), lifespan=lebenszyklus)

    # Token im Header (kein Cookie) -> keine Credentials noetig.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(RequestValidationError, validierung_behandeln)

    @app.exception_handler(SpeicherNichtVerfuegbar)
    async def _speicher_nicht_verfuegbar(request: Request, exc: SpeicherNichtVerfuegbar):
        # Objekt-Pool gerade nicht erreichbar (Laufwerk abgehaengt): nichts geht
        # verloren, der Aufrufer soll spaeter erneut versuchen.
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "30"},
            content={"detail": "Speicher nicht verfügbar - bitte später erneut versuchen"},
        )

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "dienst": "kellerwolke", "version": version()}

    app.include_router(auth_router)
    app.include_router(datei_router)
    app.include_router(suche_router)
    app.include_router(admin_router)
    app.include_router(sync_router)
    app.include_router(vorgaenge_router)
    app.include_router(plugins_router)
    app.include_router(appzugang_router)
    app.include_router(ablage_router)
    webdav_einbinden(app)
    return app


app = app_bauen()
