import pytest


def test_submit_exercise_result_and_scores_api(client):
    payload = {
        "subject_id": "sub_english",
        "exercise_type": "cloze",
        "total_items": 5,
        "correct_items": 4,
        "mistakes_count": 1,
        "revealed_count": 0,
        "difficulty_level": "mittel"
    }

    # 1. Ergebnis posten
    post_res = client.post("/api/v1/exercises/results", json=payload)
    assert post_res.status_code == 200
    data = post_res.json()
    assert data["status"] == "success"
    assert data["accuracy_percent"] == 80.0
    assert "adaptive_difficulty" in data
    assert "adaptive_level_code" in data
    assert "adaptive_level_label" in data

    # 2. Fach-Scores abrufen
    get_res = client.get("/api/v1/exercises/scores/sub_english")
    assert get_res.status_code == 200
    scores_data = get_res.json()
    assert scores_data["subject_id"] == "sub_english"
    assert scores_data["total_completed"] >= 1
    assert "cloze" in scores_data["methods"]
    assert scores_data["methods"]["cloze"]["completed_count"] >= 1
    assert scores_data["methods"]["cloze"]["recent_score"] == 80.0

    # 3. Adaptive Schwierigkeit direkt abrufen
    ad_res = client.get("/api/v1/exercises/adaptive-difficulty/sub_english?exercise_type=cloze")
    assert ad_res.status_code == 200
    ad_data = ad_res.json()
    assert "difficulty" in ad_data
    assert "level_code" in ad_data
    assert "level_label" in ad_data

    # 4. Gamification Overview abrufen
    gam_res = client.get("/api/v1/exercises/gamification/overview")
    assert gam_res.status_code == 200
    gam_data = gam_res.json()
    assert "total_xp" in gam_data
    assert "total_stars" in gam_data
    assert "level" in gam_data
    assert "streak_days" in gam_data
    assert "achievements" in gam_data
    assert len(gam_data["achievements"]) >= 4

