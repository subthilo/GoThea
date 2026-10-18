"""Übungen aus echten Aufgaben – Probebetrieb (Schalter GOTHEA_EXERCISE_TRIAL, Standard nur Staging).

Noch ohne Freigabe-Ablauf: Die Daten enthalten die Lösungen; Stufe 0 prüft im Browser, die Tafel-Stufen
prüft der Server („Luna liest, der Code rechnet“, services/practice_check.py). Jeder Versuch wird
festgehalten (services/practice_attempts.py): Stufe 0 meldet ihre Schritte, Tafel-Prüfungen zählt der Server.
"""
import base64
import json
import logging
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app import config
from backend.app.database import get_db
from backend.app.models.whiteboard import TutorSession
from backend.app.models.practice_attempt import PracticeAttempt
from backend.app.services import llm, practice_attempts, practice_check, practice_exercises, practice_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/practice", tags=["Übungen"])


class CheckRequest(BaseModel):
    image_base64: str
    stage: int = Field(ge=1, le=4)
    board_id: Optional[str] = None
    attempt: int = Field(default=1, ge=1)
    audio_enabled: bool = False


class AttemptStart(BaseModel):
    stage: int = Field(ge=-1, le=4)  # -1 = Gedankengang, 0 = Bausteine, 1–4 = Tafel
    board_id: Optional[str] = None  # Tafel-Stufen: der Versuch gehört zur Übungstafel


class HandwritingSample(BaseModel):
    label: str = Field(pattern=r"^[0-9]$")
    # Striche der Ziffer, auf ihr Kästchen bezogen (längste Seite = 1): [[[x, y], …], …]
    strokes: List[List[List[float]]] = Field(min_length=1, max_length=8)


class HandwritingUpload(BaseModel):
    samples: List[HandwritingSample] = Field(max_length=20)


class AttemptEvent(BaseModel):
    kind: Literal["guess", "hint", "solution", "check"]
    data: dict = Field(default_factory=dict)


def _exercise_or_404(exercise_id: str) -> dict:
    ex = practice_exercises.get_exercise(exercise_id) if config.EXERCISE_TRIAL_ENABLED else None
    if ex is None:
        raise HTTPException(status_code=404, detail="Übung nicht gefunden")
    return ex


@router.get("")
def list_practice(db: Session = Depends(get_db)) -> dict:
    """Aufgaben mit Stand pro Stufe, Wiederholen und Lunas Vorschlag (services/practice_plan.py)."""
    # Ausgeschaltet: leere Liste statt Fehler, das Frontend blendet den Bereich dann aus
    if not config.EXERCISE_TRIAL_ENABLED:
        return {"enabled": False, "exercises": []}
    families = practice_exercises.list_exercises()
    attempts = db.query(PracticeAttempt).all()
    board_ids = {a.board_id for a in attempts if a.board_id}
    open_boards = {b.id for b in db.query(TutorSession.id).filter(TutorSession.id.in_(board_ids),
                                                                     TutorSession.archived_at.is_(None))}
    return {"enabled": True, "exercises": families,
            **practice_plan.plan(families, attempts, open_boards=open_boards)}


@router.get("/progress")
def practice_progress(db: Session = Depends(get_db)) -> dict:
    """Lernstand pro Übung und Stufe (Häkchen, „weiter mit Stufe …“, Wiederholen)."""
    if not config.EXERCISE_TRIAL_ENABLED:
        return {"progress": {}}
    return {"progress": practice_attempts.progress(db)}


# --- Theas Handschrift (Ziffern) aus dem Schreibfeld (js/digit_ink.js) -------------------------------------
# Nur bestätigte Ziffern: die gelesene Zahl war genau die richtige Lösung. Gesammelt zum Messen der Erkennung
# und zum Nachtrainieren des Modells (scripts/train_digit_model.py). Je Ziffer bleiben die neuesten.
SAMPLES_PER_DIGIT = 200


def _handwriting_file():
    return config.DATA_DIR / "handwriting" / "usr_thea.json"


def _load_handwriting() -> list:
    path = _handwriting_file()
    try:
        samples = json.loads(path.read_text(encoding="utf-8")).get("samples", [])
        return [s for s in samples if "strokes" in s]  # frühes Format (Punktwolken) verwerfen
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as e:
        logger.warning(f"Handschrift-Muster nicht lesbar ({path}): {e}")
        return []


@router.get("/handwriting")
def get_handwriting() -> dict:
    if not config.EXERCISE_TRIAL_ENABLED:
        return {"samples": []}
    return {"samples": _load_handwriting()}


@router.post("/handwriting")
def add_handwriting(payload: HandwritingUpload) -> dict:
    if not config.EXERCISE_TRIAL_ENABLED:
        raise HTTPException(status_code=404, detail="Übung nicht gefunden")
    for sample in payload.samples:
        for stroke in sample.strokes:
            if not 1 <= len(stroke) <= 200 or any(len(p) != 2 or not all(-0.1 <= v <= 1.1 for v in p) for p in stroke):
                raise HTTPException(status_code=422, detail="Ungültige Striche")
    samples = _load_handwriting() + [s.model_dump() for s in payload.samples]
    kept = []
    for label in "0123456789":
        kept += [s for s in samples if s["label"] == label][-SAMPLES_PER_DIGIT:]
    path = _handwriting_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"samples": kept}), encoding="utf-8")
    return {"samples": kept}


@router.get("/{exercise_id}")
def get_practice(exercise_id: str) -> dict:
    return _exercise_or_404(exercise_id)


def _practice_board(db: Session, board_id: str, exercise_id: str) -> TutorSession:
    board = db.get(TutorSession, board_id)
    if board is None or board.practice_exercise_id != exercise_id:
        raise HTTPException(status_code=404, detail="Übungstafel nicht gefunden")
    return board


@router.post("/{exercise_id}/attempts", status_code=201)
def start_attempt(exercise_id: str, payload: AttemptStart, db: Session = Depends(get_db)) -> dict:
    """Stufe 0: neuer Versuch beim Öffnen. Übungstafel: deren Versuch (beim Wiederöffnen derselbe)."""
    ex = _exercise_or_404(exercise_id)
    if payload.board_id:
        attempt = practice_attempts.for_board(db, ex, _practice_board(db, payload.board_id, exercise_id))
    else:
        attempt = practice_attempts.start(db, ex, payload.stage)
    return practice_attempts.summary(attempt)


@router.post("/attempts/{attempt_id}/events")
def record_event(attempt_id: str, payload: AttemptEvent, db: Session = Depends(get_db)) -> dict:
    if not config.EXERCISE_TRIAL_ENABLED:
        raise HTTPException(status_code=404, detail="Übung nicht gefunden")
    attempt = db.get(PracticeAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Versuch nicht gefunden")
    # Tafel-Prüfungen zählt der Server selbst (siehe check_practice)
    if payload.kind == "check" and attempt.board_id:
        raise HTTPException(status_code=400, detail="Tafel-Prüfungen werden beim Prüfen gezählt")
    try:
        practice_attempts.record(db, attempt, payload.kind, payload.data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return practice_attempts.summary(attempt)


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

    board = db.get(TutorSession, payload.board_id) if payload.board_id else None
    if board is not None and board.practice_exercise_id == exercise_id:
        attempt = practice_attempts.for_board(db, ex, board)
        practice_attempts.record(db, attempt, "check", {"status": outcome["status"], "probleme": outcome["probleme"]})
        if outcome["status"] == practice_check.RICHTIG:
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
