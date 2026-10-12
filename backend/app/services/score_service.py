import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.models.exercise_score import ExerciseScore
from backend.app.models.taxonomy import Subject

logger = logging.getLogger(__name__)

DIFFICULTY_CONFIG: Dict[str, Dict[str, Any]] = {
    "leicht": {
        "level_code": 1,
        "label": "Stufe 1 (Grundwissen & Leicht) 🌱",
        "description": "Fokus auf Erfolgserlebnisse und Festigung der Grundlagen."
    },
    "mittel": {
        "level_code": 2,
        "label": "Stufe 2 (Mittel - Ausgewogen) 🎯",
        "description": "Ausgewogener Gymnasial-Standard für Klasse 7."
    },
    "schwer": {
        "level_code": 3,
        "label": "Stufe 3 (Anspruchsvoll & Vertiefung) 🚀",
        "description": "Herausfordernde Aufgaben für höchste Denkschärfe."
    }
}

METHOD_META: Dict[str, Dict[str, str]] = {
    "cloze": {"name": "Lückentexte", "icon": "🧩"},
    "fill_in_the_blank": {"name": "Lückentexte", "icon": "🧩"},
    "math_problem": {"name": "Rechenaufgaben", "icon": "📐"},
    "math_example": {"name": "Musterbeispiele", "icon": "✏️"},
    "physics_diagram": {"name": "Physik-Diagramme", "icon": "⚡"},
    "formula_derivation": {"name": "Formel-Herleitungen", "icon": "🔬"},
    "text_question": {"name": "Textverständnis", "icon": "📖"}
}


def normalize_exercise_type(exercise_type: str) -> str:
    et = (exercise_type or "cloze").strip().lower()
    if et in ("fill_in_the_blank", "cloze"):
        return "cloze"
    return et


def calculate_adaptive_difficulty(records: List[ExerciseScore]) -> Tuple[str, int, str]:
    """
    Berechnet die dynamisch angepasste Schwierigkeitsstufe für Thea:
    - Es soll leichter werden, wenn viele Fehler gemacht werden,
      damit Thea stets Erfolgserlebnisse hat und das meiste richtig ist (~75-85% Trefferquote).
    - Es wird anspruchsvoller, wenn Thea souverän und fehlerfrei meistert.
    """
    if not records:
        return "mittel", 2, DIFFICULTY_CONFIG["mittel"]["label"]

    latest = records[0]
    latest_diff = latest.difficulty_level.lower() if latest.difficulty_level else "mittel"
    if latest_diff not in DIFFICULTY_CONFIG:
        latest_diff = "mittel"

    # 1. Schnelle Schutz-Regel: Bei akuten Schwierigkeiten in der letzten Übung sofort erleichtern
    if latest.accuracy_percent < 60.0 or latest.revealed_count >= 2:
        if latest_diff == "schwer":
            new_diff = "mittel"
        else:
            new_diff = "leicht"
        cfg = DIFFICULTY_CONFIG[new_diff]
        return new_diff, cfg["level_code"], cfg["label"]

    # 2. Trend der letzten bis zu 3 Übungen betrachten
    recent_3 = records[:3]
    avg_score = sum(r.accuracy_percent for r in recent_3) / len(recent_3)

    if avg_score < 70.0:
        new_diff = "leicht"
    elif len(recent_3) >= 2 and all(r.accuracy_percent >= 85.0 and r.revealed_count == 0 for r in recent_3):
        # Souveräne Serie ohne Aufdeckungen -> Aufstieg
        if latest_diff == "leicht":
            new_diff = "mittel"
        else:
            new_diff = "schwer"
    else:
        # Im gesunden Wohlfühlbereich (70% - 85% richtig) -> Stufe beibehalten
        new_diff = latest_diff

    cfg = DIFFICULTY_CONFIG[new_diff]
    return new_diff, cfg["level_code"], cfg["label"]


def record_exercise_result(
    db: Session,
    subject_id: str,
    exercise_type: str,
    total_items: int,
    correct_items: int,
    mistakes_count: int,
    revealed_count: int,
    difficulty_level: str = "mittel",
    user_id: str = "usr_thea"
) -> Dict[str, Any]:
    """
    Speichert den Score einer abgeschlossenen Übung in der Datenbank
    und passt das adaptive Niveau des Fachs automatisch an.
    """
    norm_type = normalize_exercise_type(exercise_type)
    total_safe = max(int(total_items or 1), 1)
    correct_safe = max(0, min(int(correct_items or 0), total_safe))
    accuracy = round((correct_safe / float(total_safe)) * 100.0, 1)

    diff_str = (difficulty_level or "mittel").strip().lower()
    if diff_str not in DIFFICULTY_CONFIG:
        diff_str = "mittel"

    score_record = ExerciseScore(
        user_id=user_id,
        subject_id=subject_id,
        exercise_type=norm_type,
        total_items=total_safe,
        correct_items=correct_safe,
        mistakes_count=max(0, int(mistakes_count or 0)),
        revealed_count=max(0, int(revealed_count or 0)),
        accuracy_percent=accuracy,
        difficulty_level=diff_str,
        completed_at=datetime.utcnow()
    )
    db.add(score_record)
    db.commit()
    db.refresh(score_record)

    # Neues adaptives Niveau berechnen
    all_records = db.query(ExerciseScore).filter(
        ExerciseScore.subject_id == subject_id,
        ExerciseScore.exercise_type == norm_type
    ).order_by(desc(ExerciseScore.completed_at)).all()

    new_diff, level_code, level_label = calculate_adaptive_difficulty(all_records)

    total_completed = len(all_records)
    avg_accuracy = round(sum(r.accuracy_percent for r in all_records) / float(total_completed), 1)

    # Ermutigende Rückmeldung generieren
    if accuracy >= 90.0:
        feedback = f"Hervorragend! {accuracy}% richtig gelöst. Du hast das Thema voll im Griff."
    elif accuracy >= 70.0:
        feedback = f"Sehr gut gemacht! {accuracy}% richtig gelöst. Weiter so!"
    else:
        feedback = f"Gut gekämpft! {accuracy}% erreicht. Luna hat das Niveau für die nächste Übung sanft angepasst."

    return {
        "status": "success",
        "record_id": score_record.id,
        "accuracy_percent": accuracy,
        "total_items": total_safe,
        "correct_items": correct_safe,
        "mistakes_count": score_record.mistakes_count,
        "revealed_count": score_record.revealed_count,
        "total_completed": total_completed,
        "average_score": avg_accuracy,
        "adaptive_difficulty": new_diff,
        "adaptive_level_code": level_code,
        "adaptive_level_label": level_label,
        "feedback_message": feedback
    }


def get_adaptive_difficulty(db: Session, subject_id: str, exercise_type: str = "cloze") -> Dict[str, Any]:
    """Liefert die aktuelle adaptive Schwierigkeitsstufe für ein Fach und einen Aufgabentyp."""
    norm_type = normalize_exercise_type(exercise_type)
    records = db.query(ExerciseScore).filter(
        ExerciseScore.subject_id == subject_id,
        ExerciseScore.exercise_type == norm_type
    ).order_by(desc(ExerciseScore.completed_at)).all()

    diff_str, level_code, level_label = calculate_adaptive_difficulty(records)
    return {
        "difficulty": diff_str,
        "level_code": level_code,
        "level_label": level_label,
        "description": DIFFICULTY_CONFIG[diff_str]["description"]
    }


def get_subject_scores_summary(db: Session, subject_id: str) -> Dict[str, Any]:
    """
    Gibt die Scores aller Übungsmethoden für ein Schulfach zurück:
    - Gesamtdurchschnitt & Gesamtzahl Übungen
    - Aufgeschlüsselt nach Übungsmethode (Lückentext, etc.)
    - Aktuelle adaptive Schwierigkeitsstufe mit Label
    """
    subj = db.query(Subject).filter(Subject.id == subject_id).first()
    subject_name = subj.name if subj else subject_id

    records = db.query(ExerciseScore).filter(
        ExerciseScore.subject_id == subject_id
    ).order_by(desc(ExerciseScore.completed_at)).all()

    if not records:
        main_diff, level_code, level_label = "mittel", 2, DIFFICULTY_CONFIG["mittel"]["label"]
        return {
            "subject_id": subject_id,
            "subject_name": subject_name,
            "total_completed": 0,
            "overall_score": 0.0,
            "current_difficulty": main_diff,
            "difficulty_level_code": level_code,
            "difficulty_label": level_label,
            "methods": {
                "cloze": {
                    "method_key": "cloze",
                    "name": "Lückentexte",
                    "icon": "🧩",
                    "completed_count": 0,
                    "average_score": 0.0,
                    "recent_score": None,
                    "current_difficulty": main_diff,
                    "difficulty_label": level_label,
                    "recent_history": []
                }
            }
        }

    # Nach Methode gruppieren
    by_method: Dict[str, List[ExerciseScore]] = {}
    for r in records:
        by_method.setdefault(r.exercise_type, []).append(r)

    # Immer mindestens "cloze" anbieten
    if "cloze" not in by_method:
        by_method["cloze"] = []

    methods_summary: Dict[str, Any] = {}
    for m_key, m_records in by_method.items():
        meta = METHOD_META.get(m_key, {"name": m_key.replace("_", " ").title(), "icon": "📝"})
        m_diff, m_code, m_label = calculate_adaptive_difficulty(m_records)
        completed_count = len(m_records)
        avg_score = round(sum(r.accuracy_percent for r in m_records) / float(completed_count), 1) if completed_count > 0 else 0.0
        recent_score = m_records[0].accuracy_percent if completed_count > 0 else None

        recent_history = [
            {
                "id": r.id,
                "score": r.accuracy_percent,
                "difficulty": r.difficulty_level,
                "completed_at": r.completed_at.strftime("%d.%m.%Y %H:%M") if r.completed_at else ""
            }
            for r in m_records[:5]
        ]

        methods_summary[m_key] = {
            "method_key": m_key,
            "name": meta["name"],
            "icon": meta["icon"],
            "completed_count": completed_count,
            "average_score": avg_score,
            "recent_score": recent_score,
            "current_difficulty": m_diff,
            "difficulty_level_code": m_code,
            "difficulty_label": m_label,
            "recent_history": recent_history
        }

    # Gesamt-Fach-Status
    total_completed = len(records)
    overall_score = round(sum(r.accuracy_percent for r in records) / float(total_completed), 1) if total_completed > 0 else 0.0
    main_diff, main_code, main_label = calculate_adaptive_difficulty(records)

    return {
        "subject_id": subject_id,
        "subject_name": subject_name,
        "total_completed": total_completed,
        "overall_score": overall_score,
        "current_difficulty": main_diff,
        "difficulty_level_code": main_code,
        "difficulty_label": main_label,
        "methods": methods_summary
    }
