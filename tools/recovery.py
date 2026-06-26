#!/usr/bin/env python3
"""Standalone-Wiederherstellung: baut den logischen Dateibaum eines Nutzers aus
PostgreSQL (read-only) und dem Objekt-Pool wieder auf - ganz ohne die laufende
App. Schutz gegen Lock-in, weil die Objekte unter ihrem Hash abgelegt und nicht
direkt browsebar sind.

Beispiel:
  python3 tools/recovery.py --ausgabe /tmp/wiederhergestellt

Liest Verbindungs- und Pfadangaben aus der Projekt-.env, sofern nicht per
Argument ueberschrieben. Externe (read-only eingehaengte) Quellen werden
uebersprungen - die liegen nicht im Objekt-Pool, sondern auf ihrem Datentraeger.
"""

import argparse
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def lade_env(wurzel: Path) -> dict:
    env = {}
    datei = wurzel / ".env"
    if datei.exists():
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            z = zeile.strip()
            if z and not z.startswith("#") and "=" in z:
                schluessel, _, wert = z.partition("=")
                env[schluessel.strip()] = wert.strip().strip('"').strip("'")
    return env


def dsn_aus_env(env: dict) -> str:
    return (f"host={env.get('KELLERWOLKE_DB_HOST', '127.0.0.1')} "
            f"port={env.get('KELLERWOLKE_DB_PORT', '5460')} "
            f"dbname={env.get('KELLERWOLKE_DB_NAME', 'kellerwolke')} "
            f"user={env.get('KELLERWOLKE_DB_USER', 'kellerwolke')} "
            f"password={env.get('KELLERWOLKE_DB_PASS', 'kellerwolke')}")


def _blob_pfad(pool_wurzel, besitzer_id, blob_hash: str) -> Path:
    return Path(pool_wurzel) / str(besitzer_id) / blob_hash[:2] / blob_hash


def _sicherer_name(name: str) -> str:
    name = name.replace("/", "_").replace("\\", "_").replace("\x00", "").strip()
    if name in ("", ".", ".."):
        return "_"
    return name


def _schreibe_datei(conn, pool_wurzel, besitzer_id, knoten, pfad: Path, statistik: dict) -> bool:
    version_id = knoten["aktuelle_version_id"]
    if not version_id:
        return False
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM chunk WHERE version_id=%s ORDER BY reihenfolge", (version_id,))
        chunks = cur.fetchall()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "wb") as aus:
        for chunk in chunks:
            quelle = _blob_pfad(pool_wurzel, besitzer_id, chunk["blob_hash"])
            if not quelle.exists():
                statistik["fehlend"] += 1
                return False
            aus.write(quelle.read_bytes())
    return True


def rekonstruiere_nutzer(conn, pool_wurzel, ausgabe_wurzel, benutzer) -> dict:
    besitzer_id = benutzer["id"]
    wurzel = (Path(ausgabe_wurzel) / _sicherer_name(benutzer["name"])).resolve()
    wurzel.mkdir(parents=True, exist_ok=True)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM knoten WHERE besitzer_id=%s AND NOT geloescht", (besitzer_id,))
        alle = cur.fetchall()

    kinder = {}
    for k in alle:
        kinder.setdefault(k["parent_id"], []).append(k)

    statistik = {"ordner": 0, "dateien": 0, "fehlend": 0, "extern": 0}

    def gehe(parent_id, ziel: Path):
        for k in sorted(kinder.get(parent_id, []), key=lambda x: x["name"].lower()):
            pfad = (ziel / _sicherer_name(k["name"])).resolve()
            # Sicherheit: niemals aus dem Ausgabebaum ausbrechen.
            if pfad != wurzel and wurzel not in pfad.parents:
                continue
            if k["typ"] == "ordner":
                pfad.mkdir(parents=True, exist_ok=True)
                statistik["ordner"] += 1
                gehe(k["id"], pfad)
            elif k["typ"] == "extern":
                statistik["extern"] += 1
            else:
                if _schreibe_datei(conn, pool_wurzel, besitzer_id, k, pfad, statistik):
                    statistik["dateien"] += 1

    gehe(None, wurzel)
    return statistik


def rekonstruiere_alle(conn, pool_wurzel, ausgabe_wurzel) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, name FROM benutzer ORDER BY lower(name)")
        benutzer = cur.fetchall()
    return {b["name"]: rekonstruiere_nutzer(conn, pool_wurzel, ausgabe_wurzel, b) for b in benutzer}


def main() -> None:
    wurzel = Path(__file__).resolve().parents[1]
    env = lade_env(wurzel)
    parser = argparse.ArgumentParser(description="Kellerwolke read-only Wiederherstellung")
    parser.add_argument("--ausgabe", required=True, help="Zielverzeichnis fuer den Baum")
    parser.add_argument("--objekte",
                        default=env.get("KELLERWOLKE_OBJEKT_PFAD", str(wurzel / "data" / "objects")),
                        help="Pfad zum Objekt-Pool")
    parser.add_argument("--dsn", default=dsn_aus_env(env), help="PostgreSQL-DSN")
    args = parser.parse_args()

    with psycopg.connect(args.dsn) as conn:
        ergebnis = rekonstruiere_alle(conn, args.objekte, args.ausgabe)

    for name, st in ergebnis.items():
        print(f"{name}: {st['dateien']} Dateien, {st['ordner']} Ordner, "
              f"{st['fehlend']} fehlende Bloecke, {st['extern']} externe uebersprungen")


if __name__ == "__main__":
    main()
