"""Passwort-Hashing mit PBKDF2-SHA256, ohne externe Abhaengigkeit.

Format: pbkdf2_sha256$<iterationen>$<salt_hex>$<hash_hex>. Vergleich in
konstanter Zeit gegen Timing-Angriffe.
"""

import hashlib
import hmac
import secrets

_ALGO = "pbkdf2_sha256"
_ITERATIONEN = 210_000


def hash_passwort(klartext: str) -> str:
    salt = secrets.token_bytes(16)
    abgeleitet = hashlib.pbkdf2_hmac("sha256", klartext.encode("utf-8"), salt, _ITERATIONEN)
    return f"{_ALGO}${_ITERATIONEN}${salt.hex()}${abgeleitet.hex()}"


def pruefe(klartext: str, gespeichert: str | None) -> bool:
    if not gespeichert:
        return False
    try:
        algo, iter_text, salt_hex, hash_hex = gespeichert.split("$")
        if algo != _ALGO:
            return False
        salt = bytes.fromhex(salt_hex)
        erwartet = bytes.fromhex(hash_hex)
        iterationen = int(iter_text)
    except (ValueError, AttributeError):
        return False
    abgeleitet = hashlib.pbkdf2_hmac("sha256", klartext.encode("utf-8"), salt, iterationen)
    return hmac.compare_digest(abgeleitet, erwartet)
