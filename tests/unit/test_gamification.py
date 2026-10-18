"""Unit- & Integrationstests für Gamification (Sterne, XP, Level, Streaks)."""
from datetime import datetime, timedelta
from backend.app.models.exercise_score import ExerciseScore
from backend.app.models.taxonomy import Subject
from backend.app.services.score_service import (
    calculate_exercise_rewards,
    get_level_info,
    calculate_streak_days,
    record_exercise_result
)


def test_calculate_exercise_rewards():
    # 100% -> 3 Sterne, voller Bonus
    xp, stars = calculate_exercise_rewards(5, 5, 100.0)
    assert stars == 3
    assert xp == 5 * 10 + 25

    # 75% -> 2 Sterne
    xp_75, stars_75 = calculate_exercise_rewards(4, 3, 75.0)
    assert stars_75 == 2
    assert xp_75 == 3 * 10 + 15

    # 40% -> 1 Stern, Basispunkte
    xp_40, stars_40 = calculate_exercise_rewards(5, 2, 40.0)
    assert stars_40 == 1
    assert xp_40 == 2 * 10 + 10


def test_level_progression():
    lvl1 = get_level_info(50)
    assert lvl1["level_number"] == 1
    assert "Wissens-Entdeckerin" in lvl1["title"]
    assert lvl1["progress_percent"] == int((50 / 250) * 100)

    lvl2 = get_level_info(300)
    assert lvl2["level_number"] == 2
    assert "Rätsel-Meisterin" in lvl2["title"]


def test_streak_calculation():
    today = datetime.utcnow()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    r1 = ExerciseScore(completed_at=today)
    r2 = ExerciseScore(completed_at=yesterday)
    r3 = ExerciseScore(completed_at=two_days_ago)

    assert calculate_streak_days([r1, r2, r3]) == 3
    # Lücke von 3 Tagen
    old = today - timedelta(days=5)
    r_old = ExerciseScore(completed_at=old)
    assert calculate_streak_days([r_old]) == 0


def test_gamification_overview_counts_effort_not_old_accuracy(client, db_session, monkeypatch):
    from backend.app import config
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", True)
    # Alte Trefferquoten-XP (Lückentext-Trainer) zählen nicht mehr
    subj = db_session.query(Subject).first()
    record_exercise_result(db=db_session, subject_id=subj.id, exercise_type="cloze",
                           total_items=3, correct_items=3, mistakes_count=0, revealed_count=0)
    data = client.get("/api/v1/exercises/gamification/overview").json()
    assert data["total_xp"] == 0 and data["total_stars"] == 0 and data["streak_days"] == 0

    # Ein Übungsversuch mit Fehler, Korrektur und Lösung bringt Einsatz-XP und einen Stern
    attempt = client.post("/api/v1/practice/sa-gummibaerchen/attempts", json={"stage": 0}).json()
    for status in ("noch_nicht", "richtig"):
        client.post(f"/api/v1/practice/attempts/{attempt['id']}/events", json={"kind": "check", "data": {"status": status}})
    data = client.get("/api/v1/exercises/gamification/overview").json()
    assert data["total_xp"] == 10 + 5 + 5 + 5 + 10  # versucht, drangeblieben, neue Stufe, zu Ende, erster des Tages
    assert data["total_stars"] == 1 and data["today_xp"] == data["total_xp"] and data["streak_days"] == 1
    unlocked = {a["id"] for a in data["achievements"] if a["unlocked"]}
    assert {"first_step", "persistence"} <= unlocked
