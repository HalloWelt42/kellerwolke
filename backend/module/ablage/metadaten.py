"""Metadaten je Datei (Inhaltstyp, App, freie Felder) und Herkunft zwischen Dateien; SQL an einer Stelle.

Alle Funktionen arbeiten auf einer übergebenen Verbindung; Rechte prüft der Aufrufer (AblageDienst).
"""

from __future__ import annotations

import json

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

FELDER_MAX_BYTES = 64 * 1024


async def meta_holen(conn, ids: list) -> dict:
    if not ids:
        return {}
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT knoten_id, inhaltstyp, app, felder FROM datei_meta WHERE knoten_id = ANY(%s)", (list(ids),))
        return {z["knoten_id"]: z for z in await cur.fetchall()}


async def meta_schreiben(conn, knoten_id, inhaltstyp: str, app: str) -> None:
    await conn.execute(
        "INSERT INTO datei_meta (knoten_id, inhaltstyp, app) VALUES (%s,%s,%s) "
        "ON CONFLICT (knoten_id) DO UPDATE SET inhaltstyp=EXCLUDED.inhaltstyp, app=EXCLUDED.app, geaendert_am=now()",
        (knoten_id, inhaltstyp, app))


async def felder_mischen(conn, knoten_id, aenderung: dict, app: str) -> dict:
    """Mischt Felder ein; ein Feld mit null wird entfernt. Grenze 64 KB für alle Felder einer Datei."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "INSERT INTO datei_meta (knoten_id, app, felder) VALUES (%s,%s,jsonb_strip_nulls(%s)) "
            "ON CONFLICT (knoten_id) DO UPDATE SET felder = jsonb_strip_nulls(datei_meta.felder || %s), "
            "geaendert_am = now() RETURNING felder",
            (knoten_id, app, Jsonb(aenderung), Jsonb(aenderung)))
        felder = (await cur.fetchone())["felder"]
    if len(json.dumps(felder).encode("utf-8")) > FELDER_MAX_BYTES:
        raise ValueError("Felder zu groß (höchstens 64 KB je Datei)")
    return felder


async def herkunft_setzen(conn, von_id, zu_id, art: str, app: str) -> None:
    await conn.execute("INSERT INTO herkunft (von_id, zu_id, art, app) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                       (von_id, zu_id, art, app))


async def herkunft_entfernen(conn, von_id, zu_id, art: str) -> bool:
    cur = await conn.execute("DELETE FROM herkunft WHERE von_id=%s AND zu_id=%s AND art=%s", (von_id, zu_id, art))
    return cur.rowcount == 1


async def herkunft_von(conn, knoten_id) -> list[dict]:
    """Bezüge eines Knotens in beide Richtungen; nur lebende Knoten."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT h.von_id, h.zu_id, h.art, h.app, h.erstellt_am FROM herkunft h "
            "JOIN knoten a ON a.id = h.von_id AND NOT a.geloescht JOIN knoten b ON b.id = h.zu_id AND NOT b.geloescht "
            "WHERE h.von_id=%s OR h.zu_id=%s ORDER BY h.erstellt_am", (knoten_id, knoten_id))
        return await cur.fetchall()


async def suche_felder(conn, besitzer_id, bedingung: dict, anzahl: int) -> list:
    """Lebende Dateien des Kontos, deren Felder die Bedingung enthalten (jsonb @>), neueste zuerst."""
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT k.id FROM datei_meta m JOIN knoten k ON k.id = m.knoten_id "
            "WHERE k.besitzer_id=%s AND NOT k.geloescht AND m.felder @> %s ORDER BY m.geaendert_am DESC LIMIT %s",
            (besitzer_id, Jsonb(bedingung), anzahl))
        return [z[0] for z in await cur.fetchall()]
