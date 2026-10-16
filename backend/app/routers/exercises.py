"""Übungsergebnisse, Scores und Gamification.

Der automatisch erzeugte Lückentext (Trainer, Vorrat, Phrasen-Audio) ist am 16.10.2026 entfallen:
Übungen entstehen nur noch aus echten Aufgaben (siehe routers/practice.py).
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.database import get_db
from backend.app.services.score_service import (
    record_exercise_result,
    get_subject_scores_summary,
    get_adaptive_difficulty,
    get_gamification_overview
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/exercises", tags=["Exercises & Trainer"])


class SubmitExerciseResultRequest(BaseModel):
    subject_id: str
    exercise_type: str = "cloze"
    total_items: int = 1
    correct_items: int = 0
    mistakes_count: int = 0
    revealed_count: int = 0
    difficulty_level: str = "mittel"
    user_id: str = "usr_thea"


@router.post("/results")
def submit_exercise_result(
    payload: SubmitExerciseResultRequest,
    db: Session = Depends(get_db)
):
    """
    Registriert das Ergebnis einer absolvierten Übung (Lückentext etc.),
    berechnet den Score und passt die adaptive Schwierigkeitsstufe an.
    """
    logger.info(
        f"POST /exercises/results: subject={payload.subject_id}, type={payload.exercise_type}, "
        f"items={payload.correct_items}/{payload.total_items}, mistakes={payload.mistakes_count}, "
        f"reveals={payload.revealed_count}, diff={payload.difficulty_level}"
    )
    res = record_exercise_result(
        db=db,
        subject_id=payload.subject_id,
        exercise_type=payload.exercise_type,
        total_items=payload.total_items,
        correct_items=payload.correct_items,
        mistakes_count=payload.mistakes_count,
        revealed_count=payload.revealed_count,
        difficulty_level=payload.difficulty_level,
        user_id=payload.user_id
    )
    return res


@router.get("/scores/{subject_id}")
def get_subject_exercise_scores(
    subject_id: str,
    db: Session = Depends(get_db)
):
    """
    Liefert den aktuellen Trainingsstand, Erfolgs-Scores und die
    aktuelle adaptive Schwierigkeitsstufe für das Schulfach.
    """
    return get_subject_scores_summary(db=db, subject_id=subject_id)


@router.get("/adaptive-difficulty/{subject_id}")
def get_subject_adaptive_difficulty(
    subject_id: str,
    exercise_type: str = "cloze",
    db: Session = Depends(get_db)
):
    """
    Liefert die empfohlene adaptive Schwierigkeitsstufe für ein Fach.
    """
    return get_adaptive_difficulty(db=db, subject_id=subject_id, exercise_type=exercise_type)


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
