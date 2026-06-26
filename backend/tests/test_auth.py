"""Tests fuer Passwort-Hashing und den Auth-Dienst: Login-Zyklus, falsches
Passwort, Sitzung pruefen und beenden."""

from module.auth import passwort
from module.auth.dienst import AuthDienst


def test_hash_ist_gesalzen_und_pruefbar():
    h1 = passwort.hash_passwort("geheim123")
    h2 = passwort.hash_passwort("geheim123")
    assert h1 != h2  # zufaelliges Salt
    assert passwort.pruefe("geheim123", h1)
    assert not passwort.pruefe("falsch", h1)
    assert not passwort.pruefe("geheim123", None)
    assert not passwort.pruefe("x", "kaputt$format")


async def test_anmelden_und_sitzung(pool):
    auth = AuthDienst(pool)
    await auth.benutzer_anlegen("marcel", "passwort", rolle="admin")
    token = await auth.anmelden("marcel", "passwort")
    assert token
    benutzer = await auth.sitzung_pruefen(token)
    assert benutzer is not None
    assert benutzer["name"] == "marcel"
    assert benutzer["rolle"] == "admin"


async def test_falsches_passwort_kein_token(pool):
    auth = AuthDienst(pool)
    await auth.benutzer_anlegen("anna", "richtig")
    assert await auth.anmelden("anna", "falsch") is None
    assert await auth.anmelden("gibtsnicht", "egal") is None


async def test_abmelden_macht_sitzung_unwirksam(pool):
    auth = AuthDienst(pool)
    await auth.benutzer_anlegen("toni", "pw")
    token = await auth.anmelden("toni", "pw")
    assert await auth.sitzung_pruefen(token) is not None
    await auth.abmelden(token)
    assert await auth.sitzung_pruefen(token) is None


async def test_ungueltiges_token(pool):
    auth = AuthDienst(pool)
    assert await auth.sitzung_pruefen("") is None
    assert await auth.sitzung_pruefen("voellig-erfunden") is None
