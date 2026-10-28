"""Gamification: Level und XP-Übersicht (Einsatz-XP aus den Übungsversuchen)."""
from backend.app.models.exercise_score import ExerciseScore
from backend.app.models.taxonomy import Subject
from backend.app.services.score_service import get_level_info


def test_level_progression():
    lvl1 = get_level_info(50)
    assert lvl1["level_number"] == 1
    assert "Wissens-Entdeckerin" in lvl1["title"]
    assert lvl1["progress_percent"] == int((50 / 250) * 100)

    lvl2 = get_level_info(300)
    assert lvl2["level_number"] == 2
    assert "Rätsel-Meisterin" in lvl2["title"]


def test_gamification_overview_counts_effort_not_old_accuracy(client, db_session, monkeypatch):
    from backend.app import config
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", True)
    # Alte Trefferquoten-XP (Lückentext-Trainer) zählen nicht mehr
    subj = db_session.query(Subject).first()
    db_session.add(ExerciseScore(subject_id=subj.id, exercise_type="cloze", total_items=3, correct_items=3,
                                 accuracy_percent=100.0))
    db_session.commit()
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
