"""FastAPI-Einstieg. Bewusst duenn: oeffnet den DB-Pool, bindet Modul-Router ein.

Strikte Trennung: hier entsteht ausschliesslich die REST-API. Die Oberflaeche
(Svelte) ist eine eigenstaendige Anwendung und spricht nur diese API.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import version


@asynccontextmanager
async def lebenszyklus(app: FastAPI):
    await db.starten()
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

    return app


app = app_bauen()
