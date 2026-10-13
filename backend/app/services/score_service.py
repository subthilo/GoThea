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

LEVELS: List[Dict[str, Any]] = [
    {"level": 1, "title": "Wissens-Entdeckerin 🌱", "min_xp": 0, "max_xp": 250},
    {"level": 2, "title": "Rätsel-Meisterin 🔍", "min_xp": 250, "max_xp": 600},
    {"level": 3, "title": "Gymnasial-Profi 🎯", "min_xp": 600, "max_xp": 1200},
    {"level": 4, "title": "Olympia-Denkerin ⚡", "min_xp": 1200, "max_xp": 2500},
    {"level": 5, "title": "GoThea-Meisterin 🦉✨", "min_xp": 2500, "max_xp": 999999},
]


def calculate_exercise_rewards(total_items: int, correct_items: int, accuracy_percent: float) -> Tuple[int, int]:
    """Berechnet verdiente Erfahrungspunkte (XP) und Sterne für eine Übung."""
    base_xp = max(0, int(correct_items or 0)) * 10
    bonus_xp = 25 if accuracy_percent >= 80.0 else (15 if accuracy_percent >= 50.0 else 10)
    xp_earned = base_xp + bonus_xp

    if accuracy_percent >= 90.0:
        stars_earned = 3
    elif accuracy_percent >= 70.0:
        stars_earned = 2
    else:
        stars_earned = 1

    return xp_earned, stars_earned


def get_level_info(total_xp: int) -> Dict[str, Any]:
    """Liefert Level-Nummer, Titel, Fortschrittsbalken und nötige XP zum nächsten Level."""
    current = LEVELS[0]
    next_level = LEVELS[1]
    for i, lvl in enumerate(LEVELS):
        if total_xp >= lvl["min_xp"]:
            current = lvl
            next_level = LEVELS[i + 1] if i + 1 < len(LEVELS) else lvl

    needed_for_level = max(1, next_level["min_xp"] - current["min_xp"])
    current_in_level = max(0, total_xp - current["min_xp"])
    progress = 100 if current["level"] == len(LEVELS) else min(100, int((current_in_level / needed_for_level) * 100))

    # Icon aus dem Titel extrahieren
    title_parts = current["title"].split()
    icon = title_parts[-1] if title_parts else "🌱"

    return {
        "level": current["level"],
        "level_number": current["level"],
        "title": current["title"],
        "icon": icon,
        "total_xp": total_xp,
        "min_xp": current["min_xp"],
        "max_xp": next_level["min_xp"] if current["level"] < len(LEVELS) else None,
        "current_level_xp": current_in_level,
        "needed_level_xp": needed_for_level,
        "needed_xp_for_next": max(0, next_level["min_xp"] - total_xp),
        "progress_percent": progress
    }


def calculate_streak_days(records: List[ExerciseScore]) -> int:
    """Ermittelt die aufeinanderfolgenden Tage, an denen Thea aktiv geübt hat."""
    if not records:
        return 0
    valid_dates = sorted(list({r.completed_at.date() for r in records if r.completed_at}), reverse=True)
    if not valid_dates:
        return 0
    today = datetime.utcnow().date()
    # Streak ist noch aktiv, wenn heute oder gestern geübt wurde
    if valid_dates[0] != today and (today - valid_dates[0]).days > 1:
        return 0
    streak = 1
    current = valid_dates[0]
    for next_date in valid_dates[1:]:
        if (current - next_date).days == 1:
            streak += 1
            current = next_date
        else:
            break
    return streak



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

    # Gamification & Positives Scoring
    xp_earned, stars_earned = calculate_exercise_rewards(total_safe, correct_safe, accuracy)

    user_records = db.query(ExerciseScore).filter(
        ExerciseScore.user_id == user_id
    ).order_by(desc(ExerciseScore.completed_at)).all()

    total_user_xp = sum(calculate_exercise_rewards(r.total_items, r.correct_items, r.accuracy_percent)[0] for r in user_records)
    total_user_stars = sum(calculate_exercise_rewards(r.total_items, r.correct_items, r.accuracy_percent)[1] for r in user_records)

    prev_user_xp = max(0, total_user_xp - xp_earned)
    prev_level = get_level_info(prev_user_xp)["level_number"]
    current_level_info = get_level_info(total_user_xp)
    leveled_up = current_level_info["level_number"] > prev_level
    streak_days = calculate_streak_days(user_records)

    # Ermutigende, rein positive Rückmeldung für Thea (keine Demotivation)
    if accuracy >= 90.0:
        feedback = f"Hervorragend, Thea! {accuracy}% gemeistert – du hast {stars_earned} Sterne und +{xp_earned} XP verdient! 🌟"
    elif accuracy >= 70.0:
        feedback = f"Super gemacht! {accuracy}% richtig gelöst – du hast {stars_earned} Sterne und +{xp_earned} XP gesammelt! ⭐"
    else:
        feedback = f"Klasse Einsatz! Jede Übung macht dich sicherer – du hast {stars_earned} Stern und +{xp_earned} XP gesammelt! 🌱"

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
        "feedback_message": feedback,
        "xp_earned": xp_earned,
        "stars_earned": stars_earned,
        "total_xp": total_user_xp,
        "total_stars": total_user_stars,
        "streak_days": streak_days,
        "level": current_level_info,
        "leveled_up": leveled_up
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

    # Gamification für dieses Fach
    subject_xp = sum(calculate_exercise_rewards(r.total_items, r.correct_items, r.accuracy_percent)[0] for r in records)
    subject_stars = sum(calculate_exercise_rewards(r.total_items, r.correct_items, r.accuracy_percent)[1] for r in records)

    return {
        "subject_id": subject_id,
        "subject_name": subject_name,
        "total_completed": total_completed,
        "overall_score": overall_score,
        "current_difficulty": main_diff,
        "difficulty_level_code": main_code,
        "difficulty_label": main_label,
        "subject_xp": subject_xp,
        "subject_stars": subject_stars,
        "positive_summary": {
            "stars": subject_stars,
            "xp": subject_xp,
            "badge": "Meisterin 🚀" if main_diff == "schwer" else ("Gymnasial-Profi 🎯" if main_diff == "mittel" else "Wissens-Entdeckerin 🌱"),
            "encouragement": f"Schon {subject_stars} Wissens-Sterne in {subject_name} gesammelt!" if subject_stars > 0 else f"Starte deine erste Übung in {subject_name} und sammle Sterne!"
        },
        "methods": methods_summary
    }


def get_gamification_overview(db: Session, user_id: str = "usr_thea") -> Dict[str, Any]:
    """Liefert den Gesamt-Gamification-Stand von Thea (XP, Sterne, Streak, Level, Auszeichnungen)."""
    records = db.query(ExerciseScore).filter(
        ExerciseScore.user_id == user_id
    ).order_by(desc(ExerciseScore.completed_at)).all()

    total_xp = 0
    total_stars = 0
    today_xp = 0
    today_stars = 0
    today_count = 0
    today = datetime.utcnow().date()

    for r in records:
        xp, stars = calculate_exercise_rewards(r.total_items, r.correct_items, r.accuracy_percent)
        total_xp += xp
        total_stars += stars
        if r.completed_at and r.completed_at.date() == today:
            today_xp += xp
            today_stars += stars
            today_count += 1

    level_info = get_level_info(total_xp)
    streak = calculate_streak_days(records)

    achievements = [
        {
            "id": "first_step",
            "icon": "🎯",
            "title": "Erster Schritt",
            "description": "Deine erste Übung erfolgreich gemeistert!",
            "unlocked": len(records) >= 1
        },
        {
            "id": "star_collector",
            "icon": "⭐",
            "title": "Sternensammlerin",
            "description": "Sammle 10 oder mehr Wissens-Sterne!",
            "unlocked": total_stars >= 10
        },
        {
            "id": "streak_flame",
            "icon": "🔥",
            "title": "Fleiß-Serie",
            "description": "Übe mindestens 2 Tage in Folge!",
            "unlocked": streak >= 2
        },
        {
            "id": "perfect_run",
            "icon": "🌟",
            "title": "Volltreffer",
            "description": "Meistere eine Übung mit 100% Perfektion!",
            "unlocked": any(r.accuracy_percent >= 99.0 for r in records)
        },
        {
            "id": "knowledge_master",
            "icon": "🦉",
            "title": "GoThea-Meisterin",
            "description": "Erreiche Level 3 oder höher!",
            "unlocked": level_info["level"] >= 3
        }
    ]

    return {
        "user_id": user_id,
        "total_xp": total_xp,
        "total_stars": total_stars,
        "streak_days": streak,
        "today_xp": today_xp,
        "today_stars": today_stars,
        "today_exercises": today_count,
        "total_completed": len(records),
        "level": level_info,
        "achievements": achievements
    }

