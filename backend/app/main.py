"""FastAPI-Einstieg. Bewusst duenn: oeffnet den DB-Pool, legt die Dienste in
app.state ab, bindet die Modul-Router ein.

Strikte Trennung: hier entsteht ausschliesslich die REST-API. Die Oberflaeche
(Svelte) ist eine eigenstaendige Anwendung und spricht nur diese API.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .adapters.filesystem_blobstore import FilesystemBlobStore
from .config import EINSTELLUNGEN, version
from module.admin.api import router as admin_router
from module.auth.api import router as auth_router
from module.auth.dienst import AuthDienst
from module.speicher.api import router as datei_router
from module.speicher.dienst import SpeicherDienst
from module.suche.api import router as suche_router
from module.suche.dienst import SuchDienst
from module.sync.api import router as sync_router
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


@asynccontextmanager
async def lebenszyklus(app: FastAPI):
    await db.starten()
    pool = db.pool()
    app.state.pool = pool
    app.state.auth = AuthDienst(pool)
    app.state.speicher = SpeicherDienst(pool, FilesystemBlobStore(EINSTELLUNGEN.objekt_pfad))
    # Aktiven Pool-Pfad aus der DB ziehen (oder mit dem Standard aus .env seeden),
    # damit ein verschobener Speicherort einen Neustart uebersteht.
    aktiv = await app.state.speicher.aktiver_pfad_initialisieren(EINSTELLUNGEN.objekt_pfad)
    app.state.speicher.blobstore.setze_wurzel(aktiv)
    app.state.suche = SuchDienst(pool)
    await _admin_seed(app.state.auth)
    try:
        yield
    finally:
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

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "dienst": "kellerwolke", "version": version()}

    app.include_router(auth_router)
    app.include_router(datei_router)
    app.include_router(suche_router)
    app.include_router(admin_router)
    app.include_router(sync_router)
    webdav_einbinden(app)
    return app


app = app_bauen()
