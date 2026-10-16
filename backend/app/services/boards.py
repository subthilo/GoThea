"""
Tafel-Verwaltung wie in einer Notizen-App: Jede freie Tafel gehört zu einem Fach, wird beim Wechsel
geschlossen und kann wieder geöffnet werden. Neue Tafeln heißen zunächst "<Fach> – <Datum>"; beim
Schließen schlägt die KI anhand des Vorschaubilds einen Namen vor (nur solange niemand umbenannt hat).
Leere Tafeln werden beim Schließen verworfen. Thea archiviert statt zu löschen; endgültig löschen
können nur die Eltern.

Tafeln auf Dokumenten (Mitschrift, Arbeitsblatt, Buchseite) sind keine Tafeln in diesem Sinn: ihre
Striche liegen pro Material und Seite in page_annotations.
"""
import base64
import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.config import OPENAI_MODEL
from backend.app.models.taxonomy import Subject
from backend.app.models.whiteboard import TutorSession
from backend.app.prompts.boards import BOARD_TITLE_SYSTEM_PROMPT
from backend.app.services import llm

logger = logging.getLogger(__name__)

MONTHS = ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."]
MAX_TITLE_LENGTH = 60


def default_title(subject_name: str, when: datetime) -> str:
    return f"{subject_name} – {when.day}. {MONTHS[when.month - 1]}"


def stroke_count(board: TutorSession) -> int:
    try:
        strokes = json.loads(board.board_state_json or "[]")
    except ValueError:
        return 0
    return len(strokes) if isinstance(strokes, list) else 0


def is_empty(board: TutorSession) -> bool:
    return stroke_count(board) == 0 and not board.exercises and not board.messages


def create_board(db: Session, subject: Subject) -> TutorSession:
    now = datetime.now()
    board = TutorSession(
        subject_id=subject.id,
        title=default_title(subject.name, now),
        title_source="auto",
        board_state_json="[]",
        last_opened_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(board)
    db.commit()
    db.refresh(board)
    return board


def list_boards(db: Session, subject_id: Optional[str] = None, archived: bool = False) -> List[TutorSession]:
    query = db.query(TutorSession)
    query = query.filter(TutorSession.archived_at.isnot(None) if archived else TutorSession.archived_at.is_(None))
    if subject_id:
        query = query.filter(TutorSession.subject_id == subject_id)
    last_change = func.coalesce(TutorSession.updated_at, TutorSession.start_time)
    return query.order_by(last_change.desc()).all()


def last_opened_board(db: Session, subject_id: Optional[str] = None) -> Optional[TutorSession]:
    query = db.query(TutorSession).filter(TutorSession.archived_at.is_(None))
    if subject_id:
        query = query.filter(TutorSession.subject_id == subject_id)
    last_open = func.coalesce(TutorSession.last_opened_at, TutorSession.start_time)
    return query.order_by(last_open.desc()).first()


def open_board(db: Session, board: TutorSession) -> TutorSession:
    board.last_opened_at = datetime.utcnow()
    board.end_time = None
    db.commit()
    db.refresh(board)
    return board


def rename_board(db: Session, board: TutorSession, title: str) -> TutorSession:
    board.title = title.strip()[:MAX_TITLE_LENGTH]
    board.title_source = "user"
    db.commit()
    db.refresh(board)
    return board


def set_archived(db: Session, board: TutorSession, archived: bool) -> TutorSession:
    board.archived_at = datetime.utcnow() if archived else None
    db.commit()
    db.refresh(board)
    return board


def delete_board(db: Session, board: TutorSession) -> None:
    """Löscht die Tafel endgültig samt Strichen, Vorschaubild und Tutor-Verlauf (nur Eltern-Modus)."""
    db.delete(board)
    db.commit()


def close_board(db: Session, board: TutorSession) -> Optional[TutorSession]:
    """Schließt die Tafel; leere Tafeln werden verworfen (Rückgabe None)."""
    if is_empty(board):
        db.delete(board)
        db.commit()
        return None
    board.end_time = datetime.utcnow()
    db.commit()
    if board.title_source == "auto":
        title = suggest_title(board)
        if title:
            board.title = title
            board.title_source = "ai"
            db.commit()
    db.refresh(board)
    return board


def suggest_title(board: TutorSession) -> Optional[str]:
    """Namensvorschlag der KI aus dem Vorschaubild; None ohne KI, ohne Bild oder bei Fehlern."""
    if not llm.is_available() or not (board.snapshot_data_url or "").startswith("data:image/"):
        return None
    subject_name = board.subject.name if board.subject else ""
    try:
        data = llm.chat_json(
            [
                {"role": "system", "content": BOARD_TITLE_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": f"Fach: {subject_name}"},
                    {"type": "image_url", "image_url": {"url": board.snapshot_data_url, "detail": "low"}},
                ]},
            ],
            purpose="Tafel benennen",
            model=OPENAI_MODEL,
        )
    except llm.LLMError as e:
        logger.warning(f"Tafel {board.id}: kein KI-Name ({e})")
        return None
    title = str(data.get("titel") or "").strip().strip('"„“').rstrip(".")
    return title[:MAX_TITLE_LENGTH] or None


def thumbnail_bytes(board: TutorSession) -> Optional[tuple]:
    """(Bytes, MIME-Typ) des gespeicherten Vorschaubilds."""
    url = board.snapshot_data_url or ""
    if not url.startswith("data:image/") or ";base64," not in url:
        return None
    header, payload = url.split(";base64,", 1)
    try:
        return base64.b64decode(payload), header[len("data:"):]
    except ValueError:
        return None
