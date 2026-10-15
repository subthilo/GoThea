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


def test_gamification_overview_api(client, db_session):
    # Fach anlegen
    subj = db_session.query(Subject).first()
    if not subj:
        subj = Subject(id="sub_test", name="Testfach", color_code="#3b82f6")
        db_session.add(subj)
        db_session.commit()

    record_exercise_result(
        db=db_session,
        subject_id=subj.id,
        exercise_type="cloze",
        total_items=3,
        correct_items=3,
        mistakes_count=0,
        revealed_count=0
    )

    res = client.get("/api/v1/exercises/gamification/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["total_xp"] > 0
    assert data["total_stars"] == 3
    assert data["streak_days"] == 1
    assert len(data["achievements"]) >= 1
