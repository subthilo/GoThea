"""
Speichert Themen-Pläne (Katalog-Aufbau, Zusammenführung) aus der Vorschau, damit beim Anwenden
genau der gezeigte Plan umgesetzt wird. Ein Fingerabdruck erkennt, ob sich die Daten seitdem geändert haben.
"""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from backend.app.config import DATA_DIR

PLANS_DIR = DATA_DIR / "plans"


def fingerprint(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def plan_path(kind: str, subject_id: str) -> Path:
    return PLANS_DIR / f"{kind}_{subject_id}.json"


def save_plan(kind: str, subject_id: str, plan, data_fingerprint: str) -> Path:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    path = plan_path(kind, subject_id)
    path.write_text(json.dumps({"fingerprint": data_fingerprint, "plan": asdict(plan)}, ensure_ascii=False, indent=1))
    return path


def load_plan(kind: str, subject_id: str, current_fingerprint: str) -> Optional[dict]:
    """Gespeicherten Plan laden; Fehler, wenn er fehlt oder sich die Daten seit der Vorschau geändert haben."""
    path = plan_path(kind, subject_id)
    if not path.exists():
        raise FileNotFoundError("Keine gespeicherte Vorschau. Bitte erst ohne --apply ausführen.")
    stored = json.loads(path.read_text())
    if stored["fingerprint"] != current_fingerprint:
        raise ValueError("Die Daten haben sich seit der Vorschau geändert. Bitte die Vorschau neu erstellen.")
    return stored["plan"]


def discard_plan(kind: str, subject_id: str) -> None:
    plan_path(kind, subject_id).unlink(missing_ok=True)
