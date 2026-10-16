from datetime import datetime
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.models.whiteboard import TutorSession, TutorMessage, TutorExercise
from backend.app.models.taxonomy import Subject, Topic
from backend.app.schemas.whiteboard import (
    TutorSessionCreate,
    TutorSessionUpdateState,
    TutorSessionClose,
    TutorSessionResponse,
    TutorAskRequest,
    TutorAskResponse,
    TutorMessageResponse,
    TutorExerciseCreateRequest,
    TutorExercisePositionUpdate,
    TutorExerciseResponse,
    CheckBlanksRequest,
    CheckBlanksResponse,
)
from backend.app.services.tutor_service import (
    analyze_whiteboard_and_speak,
    generate_board_exercise,
    normalize_cloze_content,
    evaluate_cloze_blanks_targeted,
)
from backend.app.services.exercise_pool_service import exercise_pool_manager

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
    session.updated_at = datetime.utcnow()
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
              "latex": "Tipp: Achte auf die Vorzeichenregel: -(-a) = +a",
              "coords": {"x": 130, "y": 250}
            }
        ]
    }

from backend.app.models.material import Material

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

    # 1. Spezifisches Material (falls übergeben oder in Session hinterlegt)
    material_context = None
    mat_id = payload.material_id
    if mat_id:
        mat = db.query(Material).filter(Material.id == mat_id).first()
        if mat:
            material_context = {
                "id": mat.id,
                "title": mat.title,
                "kind": mat.kind,
                "topic": mat.topic.name if mat.topic else None,
                "summary": mat.summary,
                "text_snippet": (mat.extracted_text or "")[:3500]
            }

    # 2. Alle Unterlagen dieses Fachs für didaktischen Überblick
    available_materials = []
    if session.subject_id:
        all_mats = db.query(Material).filter(Material.subject_id == session.subject_id).all()
        for m in all_mats[:15]:
            available_materials.append({
                "id": m.id,
                "title": m.title,
                "kind": m.kind,
                "summary": m.summary
            })

    # 3. Alle Themen des Fachs aus dem Lehrplan
    curriculum_topics = []
    if session.subject_id:
        topics = db.query(Topic).filter(Topic.subject_id == session.subject_id).all()
        curriculum_topics = [t.name for t in topics]

    # 4. Bisheriges Gesprächsgedächtnis (Session Memory) laden
    history_records = db.query(TutorMessage).filter(
        TutorMessage.session_id == session_id
    ).order_by(TutorMessage.created_at.asc()).all()

    dialogue_history = [
        {"role": m.role, "content": m.content}
        for m in history_records[-8:]
    ]

    res = analyze_whiteboard_and_speak(
        image_base64=payload.image_base64,
        subject_name=subject_name,
        grade_level=session.grade_level or 7,
        student_question=payload.student_question,
        audio_enabled=payload.audio_enabled,
        material_context=material_context,
        available_materials=available_materials,
        curriculum_topics=curriculum_topics,
        dialogue_history=dialogue_history
    )

    # 5. Gesprächsverlauf persistieren
    student_text = payload.student_question.strip() if payload.student_question else "Thea zeigt ihr Tafelbild und bittet um Feedback."
    db.add(TutorMessage(
        session_id=session_id,
        role="student",
        content=student_text
    ))

    tutor_text = res.get("tutor_speech", "")
    actions_json = json.dumps(res.get("actions", [])) if res.get("actions") else None
    db.add(TutorMessage(
        session_id=session_id,
        role="tutor",
        content=tutor_text,
        board_action_json=actions_json
    ))
    db.commit()

    return TutorAskResponse(**res)


@router.get("/sessions/{session_id}/messages", response_model=List[TutorMessageResponse])
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Sitzung '{session_id}' nicht gefunden.")
    messages = db.query(TutorMessage).filter(
        TutorMessage.session_id == session_id
    ).order_by(TutorMessage.created_at.asc()).all()
    return messages


# ==========================================
# Interaktive Aufgaben auf dem Whiteboard
# ==========================================

@router.post("/sessions/{session_id}/exercises/generate", response_model=TutorExerciseResponse)
def generate_exercise_for_session(
    session_id: str,
    payload: TutorExerciseCreateRequest,
    db: Session = Depends(get_db)
):
    session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Sitzung '{session_id}' nicht gefunden.")

    subject_name = session.subject.name if session.subject else "Mathematik"

    # Thema ermitteln
    topic_name = payload.topic_name
    if not topic_name and payload.topic_id:
        t = db.query(Topic).filter(Topic.id == payload.topic_id).first()
        if t:
            topic_name = t.name
    elif not topic_name and session.topic_id:
        t = db.query(Topic).filter(Topic.id == session.topic_id).first()
        if t:
            topic_name = t.name

    # Material-Kontext falls vorhanden
    material_context = None
    mat_id = payload.material_id
    if mat_id:
        mat = db.query(Material).filter(Material.id == mat_id).first()
        if mat:
            material_context = {
                "id": mat.id,
                "title": mat.title,
                "kind": mat.kind,
                "topic": mat.topic.name if mat.topic else None,
                "summary": mat.summary,
                "text_snippet": (mat.extracted_text or "")[:2500]
            }

    # 1. Sofortiger Vorratsspeicher-Check (0 ms Latenz): Falls vorab generiert und kein Freitext-Wunsch vorliegt
    generated = None
    if not payload.custom_prompt and not payload.material_id:
        target_type = payload.exercise_type or "auto"
        cached = exercise_pool_manager.get_exercise_from_pool(
            subject_id=session.subject_id or subject_name,
            exercise_type=target_type,
            difficulty=payload.difficulty or "mittel"
        )
        if cached:
            content_json = cached.get("content_json")
            if not isinstance(content_json, str):
                content_json = json.dumps(cached.get("content", {}))
            generated = {
                "exercise_type": cached.get("exercise_type", "math_problem"),
                "title": cached.get("title", f"Übungsaufgabe ({subject_name})"),
                "topic": cached.get("topic") or topic_name or subject_name,
                "content_json": content_json,
                "solution_hint": cached.get("solution_hint"),
                "tutor_speech": cached.get("tutor_speech") or "Hier ist deine Aufgabe!",
                "audio_base64": cached.get("audio_base64")
            }
            # Hintergrund-Auffüllung anstoßen
            exercise_pool_manager.trigger_background_replenish(
                session.subject_id or subject_name,
                exercise_type=generated["exercise_type"]
            )

    # 2. Falls nicht im Vorrat vorhanden (oder benutzerdefinierter Wunsch): Live generieren
    if not generated:
        generated = generate_board_exercise(
            subject_name=subject_name,
            grade_level=session.grade_level or 7,
            topic_name=topic_name,
            exercise_type=payload.exercise_type,
            custom_prompt=payload.custom_prompt,
            difficulty=payload.difficulty or "mittel",
            material_context=material_context,
            audio_enabled=payload.audio_enabled
        )
        # Vorrat im Hintergrund auffüllen
        exercise_pool_manager.trigger_background_replenish(
            session.subject_id or subject_name,
            exercise_type=generated.get("exercise_type", "math_problem")
        )

    exercise = TutorExercise(
        session_id=session_id,
        exercise_type=generated["exercise_type"],
        title=generated["title"],
        topic=generated["topic"],
        content_json=generated["content_json"],
        solution_hint=generated["solution_hint"],
        pos_x=payload.pos_x or 60,
        pos_y=payload.pos_y or 80
    )
    db.add(exercise)

    # In Session-Gedächtnis eintragen
    db.add(TutorMessage(
        session_id=session_id,
        role="tutor",
        content=f"[Aufgabe auf die Tafel gelegt: {generated['title']}] {generated['tutor_speech']}"
    ))

    db.commit()
    db.refresh(exercise)

    res_dict = {
        "id": exercise.id,
        "session_id": exercise.session_id,
        "exercise_type": exercise.exercise_type,
        "title": exercise.title,
        "topic": exercise.topic,
        "content_json": exercise.content_json,
        "solution_hint": exercise.solution_hint,
        "pos_x": exercise.pos_x,
        "pos_y": exercise.pos_y,
        "created_at": exercise.created_at,
        "audio_base64": generated.get("audio_base64"),
        "tutor_speech": generated.get("tutor_speech")
    }
    return TutorExerciseResponse(**res_dict)


@router.get("/sessions/{session_id}/exercises", response_model=List[TutorExerciseResponse])
def get_session_exercises(session_id: str, db: Session = Depends(get_db)):
    session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Sitzung '{session_id}' nicht gefunden.")
    exercises = db.query(TutorExercise).filter(
        TutorExercise.session_id == session_id
    ).order_by(TutorExercise.created_at.asc()).all()
    return exercises


@router.put("/sessions/{session_id}/exercises/{exercise_id}/position", response_model=TutorExerciseResponse)
def update_exercise_position(
    session_id: str,
    exercise_id: str,
    payload: TutorExercisePositionUpdate,
    db: Session = Depends(get_db)
):
    exercise = db.query(TutorExercise).filter(
        TutorExercise.id == exercise_id,
        TutorExercise.session_id == session_id
    ).first()
    if not exercise:
        raise HTTPException(status_code=404, detail=f"Aufgabe '{exercise_id}' nicht gefunden.")

    exercise.pos_x = payload.pos_x
    exercise.pos_y = payload.pos_y
    db.commit()
    db.refresh(exercise)
    return exercise


@router.delete("/sessions/{session_id}/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session_exercise(
    session_id: str,
    exercise_id: str,
    db: Session = Depends(get_db)
):
    exercise = db.query(TutorExercise).filter(
        TutorExercise.id == exercise_id,
        TutorExercise.session_id == session_id
    ).first()
    if not exercise:
        raise HTTPException(status_code=404, detail=f"Aufgabe '{exercise_id}' nicht gefunden.")

    db.delete(exercise)
    db.commit()
    return None


@router.post("/sessions/{session_id}/exercises/{exercise_id}/check-blanks", response_model=CheckBlanksResponse)
def check_exercise_blanks(
    session_id: str,
    exercise_id: str,
    payload: CheckBlanksRequest,
    db: Session = Depends(get_db)
):
    session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Sitzung '{session_id}' nicht gefunden.")

    exercise = db.query(TutorExercise).filter(
        TutorExercise.id == exercise_id,
        TutorExercise.session_id == session_id
    ).first()
    if not exercise:
        raise HTTPException(status_code=404, detail=f"Aufgabe '{exercise_id}' nicht gefunden.")

    content = {}
    try:
        content = json.loads(exercise.content_json) if isinstance(exercise.content_json, str) else (exercise.content_json or {})
    except Exception:
        content = {}

    content = normalize_cloze_content(content)
    blanks_def = content.get("blanks", [])

    eval_res = evaluate_cloze_blanks_targeted(
        exercise_title=exercise.title,
        blanks_definition=blanks_def,
        submitted_items=[item.model_dump() for item in payload.items],
        audio_enabled=payload.audio_enabled
    )

    tutor_speech = eval_res.get("tutor_speech", "")
    if tutor_speech:
        db.add(TutorMessage(
            session_id=session_id,
            role="tutor",
            content=f"[Lückentext '{exercise.title}' geprüft] {tutor_speech}"
        ))
        db.commit()

    results = eval_res.get("results", [])
    solved_count = sum(1 for r in results if r.get("is_correct"))
    total_count = len(blanks_def)
    all_correct = (solved_count == total_count and total_count > 0)

    return CheckBlanksResponse(
        status="success",
        exercise_id=exercise_id,
        results=results,
        tutor_speech=tutor_speech,
        audio_base64=eval_res.get("audio_base64"),
        all_correct=all_correct,
        solved_count=solved_count,
        total_count=total_count
    )




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
                            "latex": "Was passiert hier mit dem Vorzeichen?",
                            "coords": {"x": 110, "y": 235}
                        }
                    ]
                })
            else:
                await websocket.send_json({"type": "echo", "received": msg})

    except WebSocketDisconnect:
        pass
