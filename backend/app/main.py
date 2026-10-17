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
from .adapters.filesystem_blobstore import FilesystemBlobStore
from .config import EINSTELLUNGEN, version
from .melder import JournalMelder
from .ports import SpeicherNichtVerfuegbar
from .validierung import validierung_behandeln
from module.ablage.api import router as ablage_router
from module.ablage.dienst import AblageDienst
from module.anfragen.api import router as anfragen_router
from module.anfragen.api import router_app as anfragen_app_router
from module.anfragen.dienst import AnfragenDienst
from module.admin.api import router as admin_router
from module.appzugang.api import router as appzugang_router
from module.appzugang.dienst import AppZugangDienst
from module.auth.api import router as auth_router
from module.auth.dienst import AuthDienst
from module.inhalt.api import router as inhalt_router
from module.medien.api import router as medien_router
from module.medien.vorschau import VorschauDienst
from module.geraete.api import router as geraete_router
from module.geraete.dienst import GeraeteDienst
from module.uploads.api import router as uploads_router
from module.uploads.dienst import UploadDienst
from module.speicher.api import router as datei_router
from module.speicher.dienst import SpeicherDienst
from module.suche.api import router as suche_router
from module.suche.dienst import SuchDienst
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


async def _taeglich(name: str, arbeit) -> None:
    """Pflege beim Start und dann täglich; ein Fehler wird protokolliert und beim nächsten Mal erneut versucht."""
    log = logging.getLogger("kellerwolke")
    while True:
        try:
            weg = await arbeit()
            if weg:
                log.info("%s: %d aufgeräumt", name, weg)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("%s fehlgeschlagen", name)
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
    app.state.anfragen = AnfragenDienst(pool, app.state.speicher)
    app.state.melder = JournalMelder(EINSTELLUNGEN.dsn)
    app.state.melder.starten()
    app.state.medien = VorschauDienst(pool, app.state.speicher, EINSTELLUNGEN.vorschau_pfad,
                                      EINSTELLUNGEN.vorschau_gleichzeitig, EINSTELLUNGEN.ffmpeg)
    app.state.uploads = UploadDienst(pool, app.state.speicher, EINSTELLUNGEN.teile_pfad, EINSTELLUNGEN.teile_tage)
    app.state.geraete = GeraeteDienst(pool)
    pflege = [
        asyncio.create_task(_taeglich("Journal", lambda: app.state.speicher.journal_aufraeumen(EINSTELLUNGEN.journal_tage)),
                            name="journal-pflege"),
        asyncio.create_task(_taeglich("Vorschauen", app.state.medien.aufraeumen), name="vorschau-pflege"),
        asyncio.create_task(_taeglich("Uploads", app.state.uploads.aufraeumen), name="upload-pflege"),
        asyncio.create_task(_taeglich("Kopplungen", app.state.geraete.aufraeumen), name="kopplung-pflege"),
    ]
    await _admin_seed(app.state.auth)
    try:
        yield
    finally:
        for aufgabe in pflege:
            aufgabe.cancel()
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
    app.include_router(medien_router)
    app.include_router(inhalt_router)
    app.include_router(uploads_router)
    app.include_router(geraete_router)
    app.include_router(appzugang_router)
    app.include_router(ablage_router)
    app.include_router(anfragen_router)
    app.include_router(anfragen_app_router)
    webdav_einbinden(app)
    return app


app = app_bauen()
