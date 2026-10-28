"""Gamification: XP, Level, Sterne, Streak (services/score_service.py).

Der automatisch erzeugte Lückentext (Trainer, Vorrat, Phrasen-Audio) ist am 16.10.2026 entfallen, sein
Trainingsstand auf der Fachseite (Ergebnisse, Scores, adaptives Niveau) am 28.10.2026: Übungen entstehen nur
noch aus echten Aufgaben (siehe routers/practice.py).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.services.score_service import get_gamification_overview

router = APIRouter(prefix="/api/v1/exercises", tags=["Exercises & Trainer"])


@router.get("/gamification/overview")
def get_thea_gamification_overview(
    user_id: str = "usr_thea",
    db: Session = Depends(get_db)
):
    """
    Liefert den aktuellen Gesamtstand von Thea:
    Gesammelte Sterne, XP, Level-Status, Streak und freigeschaltete Abzeichen.
    """
    return get_gamification_overview(db=db, user_id=user_id)
