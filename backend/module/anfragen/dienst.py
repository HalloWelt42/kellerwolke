"""Aktionen der Apps und Anfragen an sie (Entscheidung 17.10.2026).

Eine App meldet ihre Aktionen (was sie mit welchen Inhaltstypen kann) und holt offene Anfragen selbst ab; wer eben
abgeholt hat, gilt als erreichbar. Das Konto stellt Anfragen aus dem Dateimenü, eine App kann eine Anfrage an eine
andere weitergeben. Eine Anfrage, die nicht abgeholt wird, wartet, bis die App wieder läuft; nichts geht verloren.

Solange eine Anfrage offen ist (wartet oder läuft, nicht abgelaufen), darf die angefragte App genau diese Datei lesen
und ihre Begleiter schreiben. Das prüft AppZugangDienst.recht an einer Stelle; hier steht nur, welche Anfrage gilt.
"""

from __future__ import annotations

import asyncio
import time
from datetime import timedelta

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.adapters.postgres_metadata import PostgresMetadataRepository

OFFEN = ("wartet", "laeuft")
GUELTIG = {"hintergrund": timedelta(hours=24), "oeffnen": timedelta(hours=12)}
ERREICHBAR_S = 90          # so lange nach dem letzten Abholen gilt eine App als erreichbar
WARTEN_MAX_S = 30          # längste Wartezeit beim Abholen
NACHSEHEN_S = 5            # auch ohne Wecken so oft nachsehen (mehrere Prozesse, verpasstes Wecken)


class AnfrageUngueltig(Exception):
    """Die Anfrage gibt es für diese App nicht, oder sie ist nicht mehr offen."""


class AktionPasstNicht(ValueError):
    """Die Aktion gibt es nicht oder sie passt nicht zu der Datei."""


class OhneAdresse(Exception):
    """Die App hat keine Adresse ihrer Oberfläche gemeldet; Öffnen geht nicht."""


def typ_passt(typ: str | None, muster: list[str]) -> bool:
    typ = (typ or "").lower()
    return any(m == typ or (m.endswith("/*") and typ.startswith(m[:-1])) for m in muster)


_AUSWAHL = (
    "SELECT a.*, z.app, coalesce(z.gemeldet_am > now() - make_interval(secs => %s), false) AS erreichbar, "
    "coalesce(ak.titel, a.aktion) AS titel, coalesce(ak.symbol, 'fa-wand-magic-sparkles') AS symbol, "
    "k.name AS knoten_name, e.name AS ergebnis_name "
    "FROM anfrage a JOIN app_zugang z ON z.id = a.zugang_id "
    "LEFT JOIN app_aktion ak ON ak.zugang_id = a.zugang_id AND ak.kennung = a.aktion "
    "JOIN knoten k ON k.id = a.knoten_id LEFT JOIN knoten e ON e.id = a.ergebnis_id "
)


class AnfragenDienst:
    def __init__(self, pool, speicher) -> None:
        self.pool = pool
        self.speicher = speicher
        self._wecker: dict[str, asyncio.Event] = {}

    # --- intern -----------------------------------------------------------------------------------------------

    def _wecken(self, zugang_id) -> None:
        wecker = self._wecker.get(str(zugang_id))
        if wecker:
            wecker.set()

    @staticmethod
    async def _ablauf(conn) -> None:
        """Offene Anfragen, deren Frist um ist, schließen (das Recht der App endet ohnehin mit der Frist)."""
        await conn.execute("UPDATE anfrage SET zustand='fehler', meldung='abgelaufen', geaendert_am=now() "
                           "WHERE zustand = ANY(%s) AND gueltig_bis < now()", (list(OFFEN),))

    @staticmethod
    async def _liste(conn, bedingung: str, werte: tuple, rest: str = "") -> list[dict]:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(_AUSWAHL + "WHERE " + bedingung + " " + rest, (ERREICHBAR_S, *werte))
            return await cur.fetchall()

    async def _eine(self, conn, anfrage_id) -> dict | None:
        liste = await self._liste(conn, "a.id=%s", (anfrage_id,))
        return liste[0] if liste else None

    # --- Apps -------------------------------------------------------------------------------------------------

    async def aktionen_melden(self, akteur, adresse: str | None, aktionen: list[dict]) -> list[dict]:
        """Ersetzt die Aktionen der App ganz; Adresse der Oberfläche und Lebenszeichen gleich mit."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("UPDATE app_zugang SET adresse=%s, gemeldet_am=now() WHERE id=%s",
                                   (adresse, akteur.zugang_id))
                await conn.execute("DELETE FROM app_aktion WHERE zugang_id=%s", (akteur.zugang_id,))
                async with conn.cursor() as cur:
                    await cur.executemany(
                        "INSERT INTO app_aktion (zugang_id, kennung, titel, titel_erneut, symbol, typen, art, rolle, "
                        "reihenfolge) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        [(akteur.zugang_id, a["kennung"], a["titel"], a.get("titel_erneut"), a["symbol"], a["typen"],
                          a["art"], a.get("rolle"), i) for i, a in enumerate(aktionen)])
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM app_aktion WHERE zugang_id=%s ORDER BY reihenfolge", (akteur.zugang_id,))
                return await cur.fetchall()

    async def offene_holen(self, akteur, warten_s: float = 0) -> list[dict]:
        """Wartende Anfragen der App (älteste zuerst); ohne Anfrage wartet es bis zu warten_s Sekunden auf eine neue.
        Jeder Aufruf ist ein Lebenszeichen der App."""
        ende = time.monotonic() + max(0.0, min(warten_s, WARTEN_MAX_S))
        wecker = self._wecker.setdefault(akteur.zugang_id, asyncio.Event())
        while True:
            wecker.clear()
            async with self.pool.connection() as conn:
                await conn.execute("UPDATE app_zugang SET gemeldet_am=now() WHERE id=%s", (akteur.zugang_id,))
                await self._ablauf(conn)
                liste = await self._liste(conn, "a.zugang_id=%s AND a.zustand='wartet' AND a.art='hintergrund'",
                                          (akteur.zugang_id,), "ORDER BY a.erstellt_am LIMIT 50")
            rest = ende - time.monotonic()
            if liste or rest <= 0:
                return liste
            try:
                await asyncio.wait_for(wecker.wait(), timeout=min(rest, NACHSEHEN_S))
            except TimeoutError:
                pass

    async def anfrage_der_app(self, akteur, anfrage_id) -> dict:
        async with self.pool.connection() as conn:
            await self._ablauf(conn)
            a = await self._eine(conn, anfrage_id)
        if not a or str(a["zugang_id"]) != str(akteur.zugang_id):
            raise AnfrageUngueltig("Anfrage nicht gefunden")
        return a

    async def annehmen(self, akteur, anfrage_id) -> dict:
        """Wartet sie noch, läuft sie ab jetzt. Eine Anfrage zum Öffnen nimmt die App an, wenn der Browser kommt."""
        async with self.pool.connection() as conn:
            await self._ablauf(conn)
            cur = await conn.execute("UPDATE anfrage SET zustand='laeuft', geaendert_am=now() "
                                     "WHERE id=%s AND zugang_id=%s AND zustand='wartet'", (anfrage_id, akteur.zugang_id))
            angenommen = cur.rowcount == 1
        a = await self.anfrage_der_app(akteur, anfrage_id)
        if not angenommen and a["zustand"] != "laeuft":
            raise AnfrageUngueltig(f"Die Anfrage ist {a['zustand']}")
        return a

    async def stand_setzen(self, akteur, anfrage_id, zustand: str | None = None, fortschritt: float | None = None,
                           meldung: str | None = None, ergebnis_id=None) -> dict:
        """Die App meldet Fortschritt und Ende. Ist die Anfrage nicht mehr offen (abgebrochen, abgelaufen), wird
        abgewiesen: dann hört die App auf."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await self._ablauf(conn)
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute("SELECT * FROM anfrage WHERE id=%s AND zugang_id=%s FOR UPDATE",
                                      (anfrage_id, akteur.zugang_id))
                    zeile = await cur.fetchone()
                if not zeile:
                    raise AnfrageUngueltig("Anfrage nicht gefunden")
                if zeile["zustand"] not in OFFEN:
                    raise AnfrageUngueltig(f"Die Anfrage ist {zeile['zustand']}")
                if ergebnis_id is not None:
                    ergebnis = await PostgresMetadataRepository(conn).knoten_holen(ergebnis_id)
                    if not ergebnis or ergebnis["besitzer_id"] != zeile["benutzer_id"] or ergebnis["geloescht"]:
                        raise ValueError("Ergebnis nicht gefunden")
                neu = zustand or ("laeuft" if zeile["zustand"] == "wartet" and fortschritt is not None else zeile["zustand"])
                await conn.execute(
                    "UPDATE anfrage SET zustand=%s, fortschritt=coalesce(%s, fortschritt), meldung=coalesce(%s, meldung), "
                    "ergebnis_id=coalesce(%s, ergebnis_id), geaendert_am=now() WHERE id=%s",
                    (neu, fortschritt, meldung, ergebnis_id, anfrage_id))
        return await self.anfrage_der_app(akteur, anfrage_id)

    async def gueltige(self, akteur, anfrage_id) -> dict | None:
        """Die offene, nicht abgelaufene Anfrage der App, auf die sie sich beruft; sonst None. Grundlage des Rechts."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT id, knoten_id, aktion, art FROM anfrage WHERE id=%s AND zugang_id=%s "
                                  "AND zustand = ANY(%s) AND gueltig_bis > now()",
                                  (anfrage_id, akteur.zugang_id, list(OFFEN)))
                return await cur.fetchone()

    # --- Konto ------------------------------------------------------------------------------------------------

    async def aktionen_fuer(self, benutzer_id, knoten_id) -> list[dict]:
        """Aktionen aller aktiven Apps des Kontos, die zu der Datei passen: nach Inhaltstyp, und bei einem Begleiter
        die Aktionen zum Öffnen seiner Rolle (sie gelten dann für die Hauptdatei)."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["besitzer_id"] != benutzer_id or knoten["geloescht"] or knoten["typ"] != "datei":
                return []
            eintrag = await repo.begleiter_eintrag(knoten_id)
            haupt = await repo.knoten_holen(eintrag["haupt_id"]) if eintrag else None
            if haupt and haupt["geloescht"]:
                haupt = None
            typ = await self.speicher.inhaltstyp(knoten)
            rollen = {str(k["id"]): {b["rolle"] for b in await repo.begleiter_der_haupt(k["id"])}
                      for k in (knoten, haupt) if k}
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT a.*, z.app, z.adresse, coalesce(z.gemeldet_am > now() - make_interval(secs => %s), false) "
                    "AS erreichbar FROM app_aktion a JOIN app_zugang z ON z.id = a.zugang_id "
                    "WHERE z.benutzer_id=%s AND z.aktiv ORDER BY lower(z.app), a.reihenfolge",
                    (ERREICHBAR_S, benutzer_id))
                aktionen = await cur.fetchall()
        aus = []
        for a in aktionen:
            if a["art"] == "oeffnen" and not a["adresse"]:
                continue
            if typ_passt(typ, a["typen"]):
                ziel = knoten
            elif haupt and a["art"] == "oeffnen" and a["rolle"] and eintrag["rolle"] == a["rolle"]:
                ziel = haupt
            else:
                continue
            erneut = bool(a["rolle"]) and a["rolle"] in rollen.get(str(ziel["id"]), set())
            aus.append({**a, "knoten_id": ziel["id"], "erneut": erneut,
                        "titel": (a["titel_erneut"] or a["titel"]) if erneut else a["titel"]})
        return aus

    async def stellen(self, benutzer_id, zugang_id, aktion: str, knoten_id, von: str = "konto",
                      optionen: dict | None = None) -> tuple[dict, str | None]:
        """Neue Anfrage; liefert sie und bei Aktionen zum Öffnen die Adresse in der App. Optionen reicht die
        Kellerwolke unverändert an die angefragte App."""
        passend = [a for a in await self.aktionen_fuer(benutzer_id, knoten_id)
                   if str(a["zugang_id"]) == str(zugang_id) and a["kennung"] == aktion]
        if not passend:
            raise AktionPasstNicht("Diese Aktion gibt es nicht oder sie passt nicht zu der Datei")
        a = passend[0]
        if a["art"] == "oeffnen" and not a["adresse"]:
            raise OhneAdresse(f"{a['app']} hat keine Adresse gemeldet")
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO anfrage (benutzer_id, zugang_id, aktion, knoten_id, von, art, optionen, "
                        "gueltig_bis) VALUES (%s,%s,%s,%s,%s,%s,%s, now() + %s) RETURNING id",
                        (benutzer_id, zugang_id, aktion, a["knoten_id"], von, a["art"], Jsonb(optionen or {}),
                         GUELTIG[a["art"]]))
                    anfrage_id = (await cur.fetchone())[0]
            anfrage = await self._eine(conn, anfrage_id)
        self._wecken(zugang_id)
        ziel = f"{a['adresse'].rstrip('/')}/anfrage/{anfrage_id}" if a["art"] == "oeffnen" else None
        return anfrage, ziel

    async def zugang_der_app(self, benutzer_id, app: str):
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT id FROM app_zugang WHERE benutzer_id=%s AND lower(app)=lower(%s) AND aktiv",
                                  (benutzer_id, app))
                zeile = await cur.fetchone()
        return zeile[0] if zeile else None

    async def liste_konto(self, benutzer_id) -> list[dict]:
        """Anfragen im Hintergrund: offene und die der letzten 24 Stunden, neueste zuerst."""
        async with self.pool.connection() as conn:
            await self._ablauf(conn)
            return await self._liste(
                conn, "a.benutzer_id=%s AND a.art='hintergrund' AND (a.zustand = ANY(%s) "
                "OR a.geaendert_am > now() - interval '24 hours')", (benutzer_id, list(OFFEN)),
                "ORDER BY a.erstellt_am DESC LIMIT 100")

    async def abbrechen(self, benutzer_id, anfrage_id) -> bool:
        async with self.pool.connection() as conn:
            cur = await conn.execute("UPDATE anfrage SET zustand='abgebrochen', geaendert_am=now() "
                                     "WHERE id=%s AND benutzer_id=%s AND zustand = ANY(%s)",
                                     (anfrage_id, benutzer_id, list(OFFEN)))
            return cur.rowcount == 1

    async def aufraeumen(self, benutzer_id) -> int:
        async with self.pool.connection() as conn:
            cur = await conn.execute("DELETE FROM anfrage WHERE benutzer_id=%s AND NOT (zustand = ANY(%s))",
                                     (benutzer_id, list(OFFEN)))
            return cur.rowcount
