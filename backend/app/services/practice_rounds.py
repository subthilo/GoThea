"""Gestartete Runden festhalten: welchen Akku Thea wählt (für die Eltern) und was „fast leer“ zuletzt brachte
(für den Wechsel sicher/leicht in practice_due.build_round)."""
from datetime import datetime, timedelta
from typing import List, Optional

from backend.app.models.practice_round import PracticeRound
from backend.app.services.practice_due import AKKU

SUMMARY_DAYS = 14  # Zeitraum der Akku-Zähler im Eltern-Modus


def record(db, akku: str, fach: Optional[str], items: List[dict]) -> None:
    db.add(PracticeRound(akku=akku, fach=fach, art=items[0]["art"] if items else None, aufgaben=len(items)))
    db.commit()


def last_low_art(db) -> Optional[str]:
    """Art der Aufgabe aus der letzten Runde mit „fast leer“, in der etwas dran war."""
    row = (db.query(PracticeRound.art).filter(PracticeRound.akku == "fast_leer", PracticeRound.art.isnot(None))
           .order_by(PracticeRound.created_at.desc()).first())
    return row[0] if row else None


def summary(db, now: Optional[datetime] = None) -> dict:
    """Wie oft Thea in den letzten SUMMARY_DAYS Tagen welchen Akku gewählt hat."""
    since = (now or datetime.utcnow()) - timedelta(days=SUMMARY_DAYS)
    out = {a: 0 for a in AKKU}
    for (akku,) in db.query(PracticeRound.akku).filter(PracticeRound.created_at >= since):
        if akku in out:
            out[akku] += 1
    return {"tage": SUMMARY_DAYS, "runden": out}
