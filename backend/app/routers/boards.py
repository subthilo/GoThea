"""Tafeln verwalten (Liste pro Fach, öffnen, schließen, umbenennen, archivieren, löschen).

Die Striche speichert die Tafel weiterhin per Auto-Save über PUT /api/v1/whiteboard/sessions/{id}/state.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.taxonomy import Subject
from backend.app.models.whiteboard import TutorSession
from backend.app.schemas.boards import BoardCloseResult, BoardCreate, BoardDetail, BoardRename, BoardSummary
from backend.app.services import boards as svc
from backend.app.services.parent_auth import require_parent

router = APIRouter(prefix="/api/v1/boards", tags=["Tafeln"])


def _summary_fields(b: TutorSession) -> dict:
    return dict(
        id=b.id,
        subject_id=b.subject_id,
        subject_name=b.subject.name if b.subject else None,
        subject_icon=b.subject.icon if b.subject else None,
        title=b.title,
        title_source=b.title_source or "auto",
        created_at=b.start_time,
        updated_at=b.updated_at,
        last_opened_at=b.last_opened_at,
        archived=b.archived_at is not None,
        stroke_count=svc.stroke_count(b),
        has_thumbnail=svc.thumbnail_bytes(b) is not None,
    )


def _summary(b: TutorSession) -> BoardSummary:
    return BoardSummary(**_summary_fields(b))


def _detail(b: TutorSession) -> BoardDetail:
    return BoardDetail(**_summary_fields(b), board_state_json=b.board_state_json)


def _get(db: Session, board_id: str) -> TutorSession:
    board = db.get(TutorSession, board_id)
    if board is None:
        raise HTTPException(status_code=404, detail=f"Tafel '{board_id}' nicht gefunden.")
    return board


@router.get("", response_model=List[BoardSummary])
def list_boards(subject_id: Optional[str] = None, db: Session = Depends(get_db)):
    return [_summary(b) for b in svc.list_boards(db, subject_id)]


@router.get("/archived", response_model=List[BoardSummary], dependencies=[Depends(require_parent)])
def list_archived_boards(subject_id: Optional[str] = None, db: Session = Depends(get_db)):
    return [_summary(b) for b in svc.list_boards(db, subject_id, archived=True)]


@router.get("/last", response_model=Optional[BoardDetail])
def last_board(subject_id: Optional[str] = None, db: Session = Depends(get_db)):
    board = svc.last_opened_board(db, subject_id)
    return _detail(board) if board else None


@router.post("", response_model=BoardDetail, status_code=201)
def create_board(payload: BoardCreate, db: Session = Depends(get_db)):
    subject = db.get(Subject, payload.subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail=f"Fach '{payload.subject_id}' existiert nicht.")
    return _detail(svc.create_board(db, subject))


@router.post("/{board_id}/open", response_model=BoardDetail)
def open_board(board_id: str, db: Session = Depends(get_db)):
    return _detail(svc.open_board(db, _get(db, board_id)))


@router.post("/{board_id}/close", response_model=BoardCloseResult)
def close_board(board_id: str, db: Session = Depends(get_db)):
    board = svc.close_board(db, _get(db, board_id))
    return BoardCloseResult(deleted=board is None, board=_summary(board) if board else None)


@router.patch("/{board_id}", response_model=BoardSummary)
def rename_board(board_id: str, payload: BoardRename, db: Session = Depends(get_db)):
    return _summary(svc.rename_board(db, _get(db, board_id), payload.title))


@router.delete("/{board_id}", status_code=204, dependencies=[Depends(require_parent)])
def delete_board(board_id: str, db: Session = Depends(get_db)):
    svc.delete_board(db, _get(db, board_id))
    return Response(status_code=204)


@router.post("/{board_id}/archive", response_model=BoardSummary)
def archive_board(board_id: str, db: Session = Depends(get_db)):
    return _summary(svc.set_archived(db, _get(db, board_id), True))


@router.post("/{board_id}/unarchive", response_model=BoardSummary, dependencies=[Depends(require_parent)])
def unarchive_board(board_id: str, db: Session = Depends(get_db)):
    return _summary(svc.set_archived(db, _get(db, board_id), False))


@router.get("/{board_id}/thumbnail")
def board_thumbnail(board_id: str, db: Session = Depends(get_db)):
    thumb = svc.thumbnail_bytes(_get(db, board_id))
    if thumb is None:
        raise HTTPException(status_code=404, detail="Kein Vorschaubild.")
    data, mime = thumb
    return Response(content=data, media_type=mime, headers={"Cache-Control": "no-cache"})
