import json
import pytest
from unittest.mock import patch, MagicMock

def test_phrase_pool_api(client):
    res = client.get("/api/v1/exercises/phrases/error_interjections")
    assert res.status_code == 200
    data = res.json()
    assert "text" in data
    assert "category" in data
    assert data["category"] == "error_interjections"
    assert len(data["text"]) > 0

    res2 = client.get("/api/v1/exercises/phrases/praise")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["category"] == "praise"
    assert len(data2["text"]) > 0

def test_check_single_blank_api(client):
    payload = {
        "blank_id": 1,
        "crop_image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "expected_answer": "Sauerstoff",
        "exercise_title": "Photosynthese",
        "hint": "Ein Gas zum Atmen"
    }
    mock_result = {
        "blank_id": 1,
        "recognized_text": "Sauerstoff",
        "is_correct": True,
        "feedback": "Klasse, genau richtig!",
        "hint": None
    }
    with patch("backend.app.routers.exercises.evaluate_cloze_blanks_targeted", return_value=[mock_result]):
        res = client.post("/api/v1/exercises/cloze/check-single-blank", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["blank_id"] == 1
        assert data["is_correct"] is True
        assert data["recognized_text"] == "Sauerstoff"

def test_cloze_generate_fallback_api(client):
    payload = {
        "subject_id": "sub_math"
    }
    mock_cloze = {
        "exercise_type": "cloze",
        "title": "Übung: Satz des Pythagoras",
        "text": "In einem rechtwinkligen Dreieck gilt: a² + b² = [c²].",
        "blanks": [{"id": 1, "correct_answer": "c²", "hint": "Hypotenusenquadrat"}],
        "word_bank": ["c²", "2ab", "h²"],
        "sentences": [
            {
                "index": 0,
                "text_with_blanks": "In einem rechtwinkligen Dreieck gilt: a² + b² = [c²].",
                "full_text_solved": "In einem rechtwinkligen Dreieck gilt: a² + b² = c².",
                "blank_ids": [1],
                "audio_base64": None
            }
        ]
    }
    mock_res = {
        "title": "Übung: Satz des Pythagoras",
        "content_json": json.dumps(mock_cloze),
        "tutor_speech": "Viel Erfolg!"
    }
    with patch("backend.app.routers.exercises.generate_board_exercise", return_value=mock_res):
        res = client.post("/api/v1/exercises/cloze/generate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["exercise_type"] == "fill_in_the_blank"
        assert "content" in data
        assert len(data["content"]["blanks"]) == 1
        assert len(data["content"]["sentences"]) == 1

