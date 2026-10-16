"""Übungen aus echten Aufgaben – Probebetrieb (Schalter GOTHEA_EXERCISE_TRIAL, Standard nur Staging).

Noch ohne Freigabe-Ablauf: Die Daten enthalten die Lösungen; Stufe 0 prüft im Browser, die Tafel-Stufen
prüft der Server („Luna liest, der Code rechnet“, services/practice_check.py).
"""
import base64
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app import config
from backend.app.database import get_db
from backend.app.models.whiteboard import TutorSession
from backend.app.services import llm, practice_check, practice_exercises

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/practice", tags=["Übungen"])


class CheckRequest(BaseModel):
    image_base64: str
    stage: int = Field(ge=1, le=4)
    board_id: Optional[str] = None
    attempt: int = Field(default=1, ge=1)
    audio_enabled: bool = False


def _exercise_or_404(exercise_id: str) -> dict:
    ex = practice_exercises.get_exercise(exercise_id) if config.EXERCISE_TRIAL_ENABLED else None
    if ex is None:
        raise HTTPException(status_code=404, detail="Übung nicht gefunden")
    return ex


@router.get("")
def list_practice() -> dict:
    # Ausgeschaltet: leere Liste statt Fehler, das Frontend blendet den Bereich dann aus
    if not config.EXERCISE_TRIAL_ENABLED:
        return {"enabled": False, "exercises": []}
    return {"enabled": True, "exercises": practice_exercises.list_exercises()}


@router.get("/{exercise_id}")
def get_practice(exercise_id: str) -> dict:
    return _exercise_or_404(exercise_id)


@router.post("/{exercise_id}/check")
def check_practice(exercise_id: str, payload: CheckRequest, db: Session = Depends(get_db)) -> dict:
    """Tafel prüfen: Luna liest die Handschrift, das Programm prüft die Mathematik."""
    ex = _exercise_or_404(exercise_id)
    if not llm.is_available():
        raise HTTPException(status_code=503, detail="Luna ist gerade nicht erreichbar.")
    try:
        read = practice_check.read_board(ex, payload.stage, payload.image_base64)
    except llm.LLMError as e:
        logger.warning(f"Übungsprüfung fehlgeschlagen: {e}")
        raise HTTPException(status_code=503, detail="Luna konnte die Tafel gerade nicht lesen.")

    outcome = practice_check.evaluate(ex, payload.stage, read)
    text = practice_check.feedback(ex, outcome, payload.attempt)
    practice_check.log_check(exercise_id, payload.stage, payload.image_base64, read, outcome)

    if outcome["status"] == practice_check.RICHTIG and payload.board_id:
        board = db.get(TutorSession, payload.board_id)
        if board is not None and board.practice_exercise_id == exercise_id:
            board.practice_solved_at = datetime.utcnow()
            db.commit()

    audio = None
    if payload.audio_enabled:
        try:
            audio = base64.b64encode(llm.speech(practice_check.speech_text(text), purpose="Übung prüfen – Stimme")).decode()
        except llm.LLMError as e:
            logger.warning(f"Sprachausgabe der Übungsprüfung fehlgeschlagen: {e}")

    return {
        "status": outcome["status"],
        "text": text,
        "probleme": outcome["probleme"],
        "gelesen": practice_check.describe_read(read, ex),
        "actions": practice_check.marks(read, outcome),
        "audio_base64": audio,
    }
