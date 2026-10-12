import pytest
from datetime import datetime, timedelta
from backend.app.models.exercise_score import ExerciseScore
from backend.app.services.score_service import (
    calculate_adaptive_difficulty,
    record_exercise_result,
    get_adaptive_difficulty,
    get_subject_scores_summary
)


def test_default_adaptive_difficulty_is_mittel():
    diff, code, label = calculate_adaptive_difficulty([])
    assert diff == "mittel"
    assert code == 2
    assert "Mittel" in label


def test_adaptive_downgrade_when_struggling():
    # Wenn viele Fehler gemacht werden oder aufgedeckt wird, soll es leichter werden
    struggling_record = ExerciseScore(
        subject_id="sub_math",
        exercise_type="cloze",
        total_items=5,
        correct_items=1,
        mistakes_count=4,
        revealed_count=2,
        accuracy_percent=20.0,
        difficulty_level="mittel",
        completed_at=datetime.utcnow()
    )
    diff, code, label = calculate_adaptive_difficulty([struggling_record])
    assert diff == "leicht"
    assert code == 1
    assert "Leicht" in label


def test_adaptive_upgrade_when_excelling():
    # Wenn konstant >= 85% ohne Aufdeckungen erzielt wird, steigt das Niveau
    records = [
        ExerciseScore(
            subject_id="sub_english",
            exercise_type="cloze",
            total_items=5,
            correct_items=5,
            mistakes_count=0,
            revealed_count=0,
            accuracy_percent=100.0,
            difficulty_level="mittel",
            completed_at=datetime.utcnow()
        ),
        ExerciseScore(
            subject_id="sub_english",
            exercise_type="cloze",
            total_items=4,
            correct_items=4,
            mistakes_count=1,
            revealed_count=0,
            accuracy_percent=100.0,
            difficulty_level="mittel",
            completed_at=datetime.utcnow() - timedelta(minutes=10)
        )
    ]
    diff, code, label = calculate_adaptive_difficulty(records)
    assert diff == "schwer"
    assert code == 3
    assert "Anspruchsvoll" in label


def test_record_exercise_result_and_summary_lifecycle(db_session):
    res = record_exercise_result(
        db=db_session,
        subject_id="sub_math",
        exercise_type="cloze",
        total_items=5,
        correct_items=5,
        mistakes_count=0,
        revealed_count=0,
        difficulty_level="mittel"
    )
    assert res["status"] == "success"
    assert res["accuracy_percent"] == 100.0
    assert res["total_completed"] == 1

    summary = get_subject_scores_summary(db=db_session, subject_id="sub_math")
    assert summary["subject_id"] == "sub_math"
    assert summary["total_completed"] >= 1
    assert "cloze" in summary["methods"]
    assert summary["methods"]["cloze"]["completed_count"] >= 1
    assert summary["methods"]["cloze"]["average_score"] == 100.0
