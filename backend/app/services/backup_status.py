"""Stand der nächtlichen Sicherung (scripts/backup_to_nas.py schreibt SHARED_DATA_DIR/backup_status.json).

Der Eltern-Modus warnt, wenn der letzte Lauf scheiterte oder der letzte Erfolg älter als STALE_AFTER ist.
Ohne Datei (Mac, Tests, vor dem ersten Lauf) gibt es keine Warnung.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.app import config

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(hours=48)


def status_file():
    return config.SHARED_DATA_DIR / "backup_status.json"


def backup_status(now: Optional[datetime] = None) -> dict:
    """{"state": "none" | "ok" | "stale" | "error", "last_success", "error"}"""
    path = status_file()
    if not path.exists():
        return {"state": "none", "last_success": None, "error": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("Sicherungsstatus unlesbar: %s", exc)
        return {"state": "error", "last_success": None, "error": "Statusdatei unlesbar"}

    now = now or datetime.now(timezone.utc)
    last_success = data.get("last_success")
    if not data.get("ok"):
        state = "error"
    elif not last_success or now - datetime.fromisoformat(last_success) > STALE_AFTER:
        state = "stale"
    else:
        state = "ok"
    return {"state": state, "last_success": last_success, "error": data.get("error")}
