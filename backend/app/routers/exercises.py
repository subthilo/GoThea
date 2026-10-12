from datetime import datetime
import json
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from backend.app.database import get_db
from backend.app.models.taxonomy import Subject, Topic
from backend.app.models.material import Material
from backend.app.services.phrase_pool_service import phrase_pool_manager
from backend.app.services.cloze_pool_service import cloze_pool_manager
from backend.app.services.tutor_service import (
    generate_board_exercise,
    normalize_cloze_content,
    evaluate_cloze_blanks_targeted
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/exercises", tags=["Exercises & Trainer"])


class PhraseResponse(BaseModel):
    id: str
    category: str
    text: str
    audio_base64: Optional[str] = None


class ClozeExerciseGenerateRequest(BaseModel):
    subject_id: Optional[str] = None
    topic_id: Optional[str] = None
    material_id: Optional[str] = None
    custom_prompt: Optional[str] = None
    difficulty: Optional[str] = "mittel"
    audio_enabled: bool = True


class CheckSingleBlankRequest(BaseModel):
    blank_id: int
    crop_image_base64: str
    exercise_title: str = "Lückentext"
    expected_answer: str
    alternatives: List[str] = []
    hint: Optional[str] = None


class CheckSingleBlankResponse(BaseModel):
    blank_id: int
    recognized_text: Optional[str] = None
    is_correct: bool
    unclear_handwriting: bool = False
    feedback: str
    hint: Optional[str] = None


@router.get("/cloze/pool-status")
def get_cloze_exercise_pool_status():
    """
    Liefert den aktuellen Füllstand des Offline-Vorratsspeichers für alle Schulfächer.
    """
    return {
        "status": "success",
        "pool_counts": cloze_pool_manager.get_pool_status()
    }


@router.get("/phrases/{category}", response_model=PhraseResponse)
def get_instant_audio_phrase(category: str):
    """
    Liefert sofort (0 ms) eine Audio-Phrase aus dem Phrasen-Pool
    (z. B. 'error_interjections', 'correction_success', 'praise').
    Verhindert Wiederholungen über Shuffle-/LRU-Puffer.
    """
    valid_categories = ["error_interjections", "correction_success", "praise"]
    if category not in valid_categories:
        category = "error_interjections"

    phrase = phrase_pool_manager.get_phrase(category)
    return PhraseResponse(**phrase)


@router.post("/cloze/generate")
def generate_cloze_trainer_exercise(
    payload: ClozeExerciseGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Generiert eine Lückentext-Übung für das eigenständige Übungsfenster.
    Prüft zuerst den Offline-Vorratsspeicher (0 ms Latenz).
    Stößt im Hintergrund die automatische Nachproduktion an.
    """
    # 1. Schneller Vorratsspeicher-Check (0 ms): Falls vorab generiert, sofort liefern!
    if not payload.custom_prompt and not payload.material_id:
        cached_exercise = cloze_pool_manager.get_exercise_from_pool(payload.subject_id)
        if cached_exercise:
            # Im Hintergrund Nachschub produzieren
            cloze_pool_manager.trigger_background_replenish(payload.subject_id)
            return cached_exercise

    subject_name = "Englisch" if "english" in (payload.subject_id or "").lower() else "Mathematik"
    if payload.subject_id:
        subj = db.query(Subject).filter(Subject.id == payload.subject_id).first()
        if subj:
            subject_name = subj.name
        elif "english" in payload.subject_id.lower():
            subject_name = "Englisch"
        elif "math" in payload.subject_id.lower():
            subject_name = "Mathematik"
        elif "physic" in payload.subject_id.lower():
            subject_name = "Physik"
        elif "bio" in payload.subject_id.lower():
            subject_name = "Biologie"
        elif "german" in payload.subject_id.lower() or "deutsch" in payload.subject_id.lower():
            subject_name = "Deutsch"

    logger.info(f"POST /cloze/generate: payload.subject_id={payload.subject_id} -> resolved subject_name='{subject_name}', material_id={payload.material_id}")

    topic_name = None
    if payload.topic_id:
        topic = db.query(Topic).filter(Topic.id == payload.topic_id).first()
        if topic:
            topic_name = topic.name

    material_context = None
    source_title = None
    if payload.material_id:
        mat = db.query(Material).filter(Material.id == payload.material_id).first()
        if mat:
            source_title = mat.title
            material_context = {
                "id": mat.id,
                "title": mat.title,
                "kind": mat.kind,
                "topic": mat.topic.name if mat.topic else None,
                "summary": mat.summary,
                "text_snippet": (mat.extracted_text or "")[:3500]
            }
    elif payload.subject_id:
        # Neuestes Material des Fachs als Basis vorschlagen
        mats = db.query(Material).filter(Material.subject_id == payload.subject_id).all()
        if mats:
            latest = mats[-1]
            source_title = latest.title
            material_context = {
                "id": latest.id,
                "title": latest.title,
                "kind": latest.kind,
                "topic": latest.topic.name if latest.topic else None,
                "summary": latest.summary,
                "text_snippet": (latest.extracted_text or "")[:3000]
            }

    # Übung generieren
    res = generate_board_exercise(
        subject_name=subject_name,
        grade_level=7,
        topic_name=topic_name,
        exercise_type="fill_in_the_blank",
        custom_prompt=payload.custom_prompt,
        difficulty=payload.difficulty or "mittel",
        material_context=material_context,
        audio_enabled=payload.audio_enabled
    )

    try:
        content = json.loads(res["content_json"])
    except Exception:
        content = {}

    # Standardisierung mit Satz-Audio durchführen
    content = normalize_cloze_content(content, generate_sentence_audio=payload.audio_enabled)

    # Im Hintergrund den Vorratsspeicher auffüllen
    cloze_pool_manager.trigger_background_replenish(payload.subject_id)

    return {
        "status": "success",
        "exercise_type": "fill_in_the_blank",
        "title": res.get("title", f"Lückentext: {subject_name}"),
        "topic": res.get("topic") or topic_name or subject_name,
        "instructions": res.get("instructions") or "Fülle die Lücken mit den passenden Fachbegriffen aus.",
        "source_material_title": source_title,
        "content": content,
        "tutor_speech": res.get("tutor_speech")
    }


@router.post("/cloze/check-single-blank", response_model=CheckSingleBlankResponse)
def check_single_cloze_blank(
    payload: CheckSingleBlankRequest
):
    """
    Wird vom 3-Sekunden-Timer im Hintergrund aufgerufen, sobald Thea
    eine Lücke ausgefüllt und kurz abgesetzt hat.
    Überprüft nur den kleinen Mini-Crop (< 0,8 s) und liefert das Zwischenergebnis.
    """
    logger.info(f"POST /cloze/check-single-blank: blank_id={payload.blank_id}, expected='{payload.expected_answer}', alts={payload.alternatives}")
    b_def = {
        "id": payload.blank_id,
        "expected_answer": payload.expected_answer,
        "alternatives": payload.alternatives,
        "hint": payload.hint
    }

    eval_res = evaluate_cloze_blanks_targeted(
        exercise_title=payload.exercise_title,
        blanks_definition=[b_def],
        submitted_items=[{
            "blank_id": payload.blank_id,
            "crop_image_base64": payload.crop_image_base64
        }],
        audio_enabled=False # Audio wird erst bei der Auswertung/Korrektur abgespielt
    )

    if isinstance(eval_res, list):
        results = eval_res
    elif isinstance(eval_res, dict):
        results = eval_res.get("results", [])
    else:
        results = []
    if results:
        r = results[0]
        logger.info(f"check_single_blank result: blank_id={payload.blank_id}, recognized='{r.get('recognized_text')}', is_correct={r.get('is_correct')}")
        return CheckSingleBlankResponse(
            blank_id=payload.blank_id,
            recognized_text=r.get("recognized_text"),
            is_correct=bool(r.get("is_correct")),
            feedback=r.get("feedback", ""),
            hint=r.get("hint") or payload.hint
        )

    return CheckSingleBlankResponse(
        blank_id=payload.blank_id,
        recognized_text=None,
        is_correct=False,
        feedback="Konnte nicht geprüft werden.",
        hint=payload.hint
    )
