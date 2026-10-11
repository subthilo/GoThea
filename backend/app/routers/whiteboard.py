from datetime import datetime
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.models.whiteboard import TutorSession
from backend.app.models.taxonomy import Subject, Topic
from backend.app.schemas.whiteboard import (
    TutorSessionCreate,
    TutorSessionUpdateState,
    TutorSessionClose,
    TutorSessionResponse,
    TutorAskRequest,
    TutorAskResponse,
)
from backend.app.services.tutor_service import analyze_whiteboard_and_speak

router = APIRouter(prefix="/api/v1/whiteboard", tags=["Whiteboard"])

def _session_to_response(s: TutorSession) -> TutorSessionResponse:
    return TutorSessionResponse(
        id=s.id,
        user_id=s.user_id,
        test_id=s.test_id,
        subject_id=s.subject_id,
        subject_name=s.subject.name if s.subject else None,
        subject_icon=s.subject.icon if s.subject else "🎨",
        subject_color=s.subject.color_code if s.subject else "#3b82f6",
        topic_id=s.topic_id,
        topic_name=s.topic.name if s.topic else None,
        title=s.title,
        grade_level=s.grade_level,
        start_time=s.start_time,
        end_time=s.end_time,
        board_state_json=s.board_state_json,
        snapshot_data_url=s.snapshot_data_url,
        summary_notes=s.summary_notes,
    )

@router.get("/sessions", response_model=List[TutorSessionResponse])
def list_sessions(db: Session = Depends(get_db), limit: int = 20):
    sessions = db.query(TutorSession).order_by(desc(TutorSession.start_time)).limit(limit).all()
    return [_session_to_response(s) for s in sessions]

@router.get("/sessions/active", response_model=Optional[TutorSessionResponse])
def get_active_session(db: Session = Depends(get_db)):
    active = db.query(TutorSession).filter(TutorSession.end_time.is_(None)).order_by(desc(TutorSession.start_time)).first()
    if not active:
        return None
    return _session_to_response(active)

@router.post("/sessions", response_model=TutorSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(payload: TutorSessionCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail=f"Fach '{payload.subject_id}' existiert nicht.")

    if payload.topic_id:
        topic = db.query(Topic).filter(Topic.id == payload.topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail=f"Thema '{payload.topic_id}' existiert nicht.")

    title = payload.title or f"{subject.name} – Tafel"

    session = TutorSession(
        subject_id=payload.subject_id,
        topic_id=payload.topic_id,
        test_id=payload.test_id,
        title=title,
        grade_level=payload.grade_level or 7,
        board_state_json="[]",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_to_response(session)

@router.get("/sessions/{session_id}", response_model=TutorSessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Sitzung '{session_id}' nicht gefunden.")
    return _session_to_response(session)

@router.put("/sessions/{session_id}/state", response_model=TutorSessionResponse)
def update_session_state(session_id: str, payload: TutorSessionUpdateState, db: Session = Depends(get_db)):
    session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Sitzung '{session_id}' nicht gefunden.")

    session.board_state_json = payload.board_state_json
    if payload.snapshot_data_url is not None:
        session.snapshot_data_url = payload.snapshot_data_url
    if payload.summary_notes is not None:
        session.summary_notes = payload.summary_notes

    db.commit()
    db.refresh(session)
    return _session_to_response(session)

@router.post("/sessions/{session_id}/close", response_model=TutorSessionResponse)
def close_session(session_id: str, payload: Optional[TutorSessionClose] = None, db: Session = Depends(get_db)):
    session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Sitzung '{session_id}' nicht gefunden.")

    session.end_time = datetime.utcnow()
    if payload and payload.summary_notes:
        session.summary_notes = payload.summary_notes

    db.commit()
    db.refresh(session)
    return _session_to_response(session)

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Sitzung '{session_id}' nicht gefunden.")
    db.delete(session)
    db.commit()
    return None

@router.post("/sessions/{session_id}/mock-tutor-hint")
def generate_mock_tutor_hint(session_id: str, db: Session = Depends(get_db)):
    session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Sitzung '{session_id}' nicht gefunden.")

    # Simuliert eine didaktische sokratische Rückmeldung des KI-Tutors
    return {
        "status": "success",
        "actions": [
            {
              "action": "highlight_box",
              "coords": {"x": 120, "y": 140, "w": 320, "h": 85},
              "color": "#f59e0b"
            },
            {
              "action": "latex_hint",
              "latex": "💡 Tipp: Achte auf die Vorzeichenregel: -(-a) = +a",
              "coords": {"x": 130, "y": 250}
            }
        ]
    }

@router.post("/sessions/{session_id}/ask-tutor", response_model=TutorAskResponse)
def ask_tutor_endpoint(
    session_id: str,
    payload: TutorAskRequest,
    db: Session = Depends(get_db)
):
    session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Sitzung '{session_id}' nicht gefunden.")

    subject_name = session.subject.name if session.subject else "Mathematik"

    res = analyze_whiteboard_and_speak(
        image_base64=payload.image_base64,
        subject_name=subject_name,
        grade_level=session.grade_level or 7,
        student_question=payload.student_question,
        audio_enabled=payload.audio_enabled
    )

    return TutorAskResponse(**res)


# ==========================================
# WebSocket-Verbindung für interaktive Tafel
# ==========================================

ws_router = APIRouter(tags=["Whiteboard WS"])

@ws_router.websocket("/ws/tutor/{session_id}")
async def tutor_websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    await websocket.send_json({
        "type": "session_connected",
        "session_id": session_id,
        "message": f"Tafel-Sitzung {session_id} verbunden."
    })
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
            except Exception:
                msg = {"type": "raw", "data": raw_data}

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
            elif msg_type == "canvas_update":
                # Empfängt Vektorstriche / Snapshot-Updates
                strokes_count = len(msg.get("strokes", []))
                await websocket.send_json({
                    "type": "canvas_ack",
                    "strokes_count": strokes_count,
                    "timestamp": msg.get("timestamp")
                })
            elif msg_type == "user_interrupt":
                # Schüler setzt Apple Pencil auf während Audio/Tutor spricht -> Barge-In
                await websocket.send_json({
                    "type": "interrupt_ack",
                    "reason": msg.get("reason", "pencil_touch")
                })
            elif msg_type == "request_hint":
                # Schüler bittet um sokratischen Tipp auf der Tafel
                await websocket.send_json({
                    "type": "board_actions",
                    "actions": [
                        {
                            "action": "highlight_box",
                            "coords": {"x": 100, "y": 130, "w": 300, "h": 80},
                            "color": "#f59e0b"
                        },
                        {
                            "action": "latex_hint",
                            "latex": "💡 Was passiert hier mit dem Vorzeichen?",
                            "coords": {"x": 110, "y": 235}
                        }
                    ]
                })
            else:
                await websocket.send_json({"type": "echo", "received": msg})

    except WebSocketDisconnect:
        pass
