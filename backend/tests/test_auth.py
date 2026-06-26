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


async def test_abgelaufene_sitzung_wird_beim_login_entfernt(pool):
    auth = AuthDienst(pool)
    benutzer = await auth.benutzer_anlegen("erna", "pw")
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO sitzung (token_hash, benutzer_id, ablauf) "
                "VALUES (%s,%s, now() - interval '1 day')",
                ("alt-und-abgelaufen", benutzer["id"]),
            )
    await auth.anmelden("erna", "pw")  # raeumt abgelaufene Sitzungen auf
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT count(*) FROM sitzung WHERE token_hash=%s", ("alt-und-abgelaufen",)
            )
            (anzahl,) = await cur.fetchone()
    assert anzahl == 0


async def test_konto_ohne_passwort_kann_sich_nicht_anmelden(pool):
    auth = AuthDienst(pool)
    await auth.benutzer_anlegen("ohnepw")  # kein Passwort gesetzt
    assert await auth.anmelden("ohnepw", "") is None
    assert await auth.anmelden("ohnepw", "irgendwas") is None
