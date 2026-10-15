"""
Eltern-Modus: PIN-Verwaltung & signierte Freischalt-Tokens.

- Die PIN wird nie im Klartext gespeichert (PBKDF2-SHA256 mit Salt) in DATA_DIR/parent_auth.json.
- Standard-PIN beim ersten Start: Umgebungsvariable GOTHEA_PARENT_PIN oder "1234".
- Tokens sind zustandslos (Ablaufzeit + HMAC-Signatur) und überleben daher Server-Neustarts,
  laufen aber automatisch ab (Standard: 60 Minuten).
- Einfache Brute-Force-Bremse: nach 5 Fehlversuchen 60 Sekunden Sperre.
"""
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Optional, Tuple

from fastapi import Header, HTTPException

from backend.app.config import DATA_DIR

AUTH_FILE: Path = DATA_DIR / "parent_auth.json"
logger = logging.getLogger(__name__)
DEFAULT_PIN = os.getenv("GOTHEA_PARENT_PIN", "1234")
TOKEN_TTL_SECONDS = int(os.getenv("GOTHEA_PARENT_TOKEN_TTL", "3600"))
PBKDF2_ROUNDS = 120_000

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 60
_failed_attempts = 0
_locked_until = 0.0

PARENT_REQUIRED_DETAIL = "Diese Aktion ist nur im Eltern-Modus möglich."


def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ROUNDS).hex()


def _load_store() -> dict:
    if AUTH_FILE.exists():
        try:
            data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
            if all(k in data for k in ("salt", "pin_hash", "secret")):
                return data
            logger.error("Eltern-PIN-Datei unvollständig – PIN wird auf den Standard zurückgesetzt")
        except Exception as e:
            logger.error(f"Eltern-PIN-Datei unlesbar ({e}) – PIN wird auf den Standard zurückgesetzt")
    salt = secrets.token_hex(16)
    data = {
        "salt": salt,
        "pin_hash": _hash_pin(DEFAULT_PIN, salt),
        "secret": secrets.token_hex(32),
        "is_default_pin": True,
    }
    _save_store(data)
    return data


def _save_store(data: dict) -> None:
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(AUTH_FILE, 0o600)
    except Exception:
        pass


def is_default_pin() -> bool:
    return bool(_load_store().get("is_default_pin", False))


def verify_pin(pin: str) -> bool:
    store = _load_store()
    candidate = _hash_pin(str(pin or ""), store["salt"])
    return hmac.compare_digest(candidate, store["pin_hash"])


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_token() -> Tuple[str, int]:
    store = _load_store()
    expires_at = int(time.time()) + TOKEN_TTL_SECONDS
    nonce = secrets.token_hex(8)
    payload = f"{expires_at}.{nonce}"
    return f"{payload}.{_sign(payload, store['secret'])}", expires_at


def validate_token(token: Optional[str]) -> bool:
    if not token:
        return False
    parts = token.split(".")
    if len(parts) != 3:
        return False
    expires_str, nonce, signature = parts
    try:
        expires_at = int(expires_str)
    except ValueError:
        return False
    if expires_at < time.time():
        return False
    store = _load_store()
    expected = _sign(f"{expires_str}.{nonce}", store["secret"])
    return hmac.compare_digest(expected, signature)


def attempt_unlock(pin: str) -> Tuple[str, int]:
    """Prüft die PIN (mit Brute-Force-Bremse) und liefert bei Erfolg ein Token."""
    global _failed_attempts, _locked_until
    now = time.time()
    if now < _locked_until:
        wait = int(_locked_until - now) + 1
        raise HTTPException(status_code=429, detail=f"Zu viele Fehlversuche. Bitte {wait} Sekunden warten.")

    if not verify_pin(pin):
        _failed_attempts += 1
        if _failed_attempts >= MAX_FAILED_ATTEMPTS:
            _failed_attempts = 0
            _locked_until = now + LOCKOUT_SECONDS
            raise HTTPException(status_code=429, detail=f"Zu viele Fehlversuche. Bitte {LOCKOUT_SECONDS} Sekunden warten.")
        raise HTTPException(status_code=401, detail="Falsche PIN.")

    _failed_attempts = 0
    return issue_token()


def change_pin(current_pin: str, new_pin: str) -> None:
    if not verify_pin(current_pin):
        raise HTTPException(status_code=401, detail="Die aktuelle PIN ist falsch.")
    new_pin = str(new_pin or "").strip()
    if not new_pin.isdigit() or not (4 <= len(new_pin) <= 8):
        raise HTTPException(status_code=400, detail="Die neue PIN muss aus 4 bis 8 Ziffern bestehen.")
    store = _load_store()
    salt = secrets.token_hex(16)
    store.update({
        "salt": salt,
        "pin_hash": _hash_pin(new_pin, salt),
        # Neues Secret: alle bisher ausgegebenen Tokens werden ungültig
        "secret": secrets.token_hex(32),
        "is_default_pin": False,
    })
    _save_store(store)


def reset_lockout_state() -> None:
    """Nur für Tests."""
    global _failed_attempts, _locked_until
    _failed_attempts = 0
    _locked_until = 0.0


def require_parent(x_parent_token: Optional[str] = Header(None)) -> bool:
    """FastAPI-Dependency: Bricht mit 403 ab, wenn kein gültiges Eltern-Token mitgeschickt wurde."""
    if not validate_token(x_parent_token):
        raise HTTPException(status_code=403, detail=PARENT_REQUIRED_DETAIL)
    return True
