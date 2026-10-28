"""XP-Übersicht für Thea (Level, Sterne, Streak, Auszeichnungen) – die Zahlen kommen aus services/effort_xp.py.

Der Trainingsstand des Lückentext-Trainers (Trefferquoten, „adaptives Niveau“) ist am 28.10.2026 entfallen;
die Tabelle exercise_scores bleibt mit ihren alten Zeilen in der Datenbank.
"""
from typing import Dict, Any, List

from sqlalchemy.orm import Session

LEVELS: List[Dict[str, Any]] = [
    {"level": 1, "title": "Wissens-Entdeckerin", "icon": "🌱", "min_xp": 0, "max_xp": 250},
    {"level": 2, "title": "Rätsel-Meisterin", "icon": "🔍", "min_xp": 250, "max_xp": 600},
    {"level": 3, "title": "Gymnasial-Profi", "icon": "🎯", "min_xp": 600, "max_xp": 1200},
    {"level": 4, "title": "Olympia-Denkerin", "icon": "⚡", "min_xp": 1200, "max_xp": 2500},
    {"level": 5, "title": "GoThea-Meisterin", "icon": "✨", "min_xp": 2500, "max_xp": 999999},
]


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

    # Das Frontend zeigt eigene SVG-Icons; "icon" bleibt nur als API-Feld erhalten
    icon = current["icon"]

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


def get_gamification_overview(db: Session, user_id: str = "usr_thea") -> Dict[str, Any]:
    """Gesamtstand für Thea: XP nur für Einsatz (services/effort_xp.py), Level, Streak, Auszeichnungen.

    Seit 18.10.2026 zählen nur noch Versuche an Übungen aus echten Aufgaben. Die Trefferquoten-XP des
    entfallenen Lückentext-Trainers (exercise_scores) gehen nicht mehr ins Level ein. Sterne = Aufgaben,
    die Thea zu Ende gebracht hat (egal mit wie viel Hilfe).
    """
    from backend.app.services import effort_xp

    effort = effort_xp.summary(db)
    level_info = get_level_info(effort["total_xp"])

    achievements = [
        {
            "id": "first_step",
            "title": "Erster Schritt",
            "description": "Deine erste Aufgabe angepackt",
            "unlocked": effort["attempts"] >= 1,
        },
        {
            "id": "star_collector",
            "title": "Sternensammlerin",
            "description": "10 Aufgaben zu Ende gebracht",
            "unlocked": effort["finished"] >= 10,
        },
        {
            "id": "streak_flame",
            "title": "Fleiß-Serie",
            "description": "An 3 Tagen in Folge geübt",
            "unlocked": effort["streak_days"] >= 3,
        },
        {
            "id": "persistence",
            "title": "Drangeblieben",
            "description": "Nach einem „noch nicht“ weitergemacht",
            "unlocked": effort["persisted"] >= 1,
        },
        {
            "id": "knowledge_master",
            "title": "GoThea-Meisterin",
            "description": "Level 3 erreicht",
            "unlocked": level_info["level"] >= 3,
        },
    ]

    return {
        "user_id": user_id,
        "total_xp": effort["total_xp"],
        "total_stars": effort["finished"],
        "streak_days": effort["streak_days"],
        "today_xp": effort["today_xp"],
        "today_stars": effort["today_finished"],
        "today_exercises": effort["today_attempts"],
        "total_completed": effort["attempts"],
        "level": level_info,
        "achievements": achievements,
    }
