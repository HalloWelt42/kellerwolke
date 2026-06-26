"""Zentrale Konfiguration. Liest .env mit der Rangfolge: Umgebung > .env > Standard."""

import os
from dataclasses import dataclass
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[2]
ENVDATEI = WURZEL / ".env"


def _lade_dotenv():
    if not ENVDATEI.exists():
        return
    for zeile in ENVDATEI.read_text(encoding="utf-8").splitlines():
        z = zeile.strip()
        if not z or z.startswith("#") or "=" not in z:
            continue
        schluessel, _, wert = z.partition("=")
        wert = wert.strip().strip('"').strip("'")
        os.environ.setdefault(schluessel.strip(), wert)


_lade_dotenv()


def _text(schluessel, standard=""):
    return os.environ.get(schluessel, standard)


def _zahl(schluessel, standard):
    try:
        return int(os.environ.get(schluessel, "") or standard)
    except ValueError:
        return standard


@dataclass(frozen=True)
class Einstellungen:
    bind: str = _text("KELLERWOLKE_BIND", "127.0.0.1")
    backend_port: int = _zahl("KELLERWOLKE_BACKEND_PORT", 8460)
    frontend_port: int = _zahl("KELLERWOLKE_FRONTEND_PORT", 5200)
    db_host: str = _text("KELLERWOLKE_DB_HOST", "127.0.0.1")
    db_port: int = _zahl("KELLERWOLKE_DB_PORT", 5460)
    db_name: str = _text("KELLERWOLKE_DB_NAME", "kellerwolke")
    db_user: str = _text("KELLERWOLKE_DB_USER", "kellerwolke")
    db_pass: str = _text("KELLERWOLKE_DB_PASS", "kellerwolke")
    objekt_pfad: str = _text("KELLERWOLKE_OBJEKT_PFAD", str(WURZEL / "data" / "objects"))
    app_secret: str = _text("KELLERWOLKE_APP_SECRET", "entwicklung-unsicher")
    admin_name: str = _text("KELLERWOLKE_ADMIN_NAME", "")
    admin_passwort: str = _text("KELLERWOLKE_ADMIN_PASSWORT", "")

    @property
    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_pass}"
        )


EINSTELLUNGEN = Einstellungen()


def version() -> str:
    datei = WURZEL / "VERSION"
    return datei.read_text(encoding="utf-8").strip() if datei.exists() else "0.0.0"
