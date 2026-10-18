"""Versuche an Übungen: Stufe 0 meldet ihre Schritte, Tafel-Prüfungen zählt der Server."""
from unittest.mock import patch

import pytest

from backend.app import config
from backend.app.services import practice_check as pc


@pytest.fixture(autouse=True)
def trial_on(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", True)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)


def _event(client, attempt_id, kind, **data):
    res = client.post(f"/api/v1/practice/attempts/{attempt_id}/events", json={"kind": kind, "data": data})
    assert res.status_code == 200, res.text
    return res.json()


def _board(client, stage=1, exercise_id="sa-gummibaerchen"):
    return client.post("/api/v1/boards", json={"subject_id": "sub_math", "title": f"Übung · Stufe {stage}",
                                               "practice_exercise_id": exercise_id, "practice_stage": stage}).json()


def _check(client, board_id, status, stage=1):
    problems = [] if status == "richtig" else [
        {"bereich": "ergebnis", "text": "Stimmt noch nicht.", "gelesen": "1", "unsicher": status == "unsicher"}]
    outcome = {"status": status, "probleme": problems, "hinweise": []}
    with patch.object(pc.llm, "is_available", return_value=True), \
         patch.object(pc, "read_board", return_value={}), \
         patch.object(pc, "evaluate", return_value=outcome):
        res = client.post("/api/v1/practice/sa-gummibaerchen/check",
                          json={"image_base64": "data:image/jpeg;base64,AAAA", "stage": stage, "board_id": board_id})
    assert res.status_code == 200, res.text


def test_stage0_attempt_counts_steps_and_shows_in_progress(client):
    attempt = client.post("/api/v1/practice/sa-gummibaerchen/attempts", json={"stage": 0}).json()
    assert attempt["stage"] == 0 and attempt["checks"] == 0
    _event(client, attempt["id"], "guess", value="mehr")
    _event(client, attempt["id"], "check", status="noch_nicht", falsch=["ergebnis"])
    _event(client, attempt["id"], "hint")
    done = _event(client, attempt["id"], "check", status="richtig")
    assert done["solved"] and done["checks"] == 2 and done["failed_checks"] == 1 and done["hints_used"] == 1

    stage0 = client.get("/api/v1/practice/progress").json()["progress"]["sa-gummibaerchen"]["0"]
    assert stage0["attempts"] == 1 and stage0["solved"] and not stage0["solved_first_try"]


def test_opened_but_untouched_attempt_is_not_counted(client):
    client.post("/api/v1/practice/sa-gummibaerchen/attempts", json={"stage": 0})
    assert client.get("/api/v1/practice/progress").json()["progress"] == {}


def test_board_attempt_is_reused_and_checks_are_counted_by_server(client):
    board = _board(client, stage=2)
    first = client.post("/api/v1/practice/sa-gummibaerchen/attempts", json={"stage": 2, "board_id": board["id"]}).json()
    again = client.post("/api/v1/practice/sa-gummibaerchen/attempts", json={"stage": 2, "board_id": board["id"]}).json()
    assert first["id"] == again["id"] and first["board_id"] == board["id"]

    _check(client, board["id"], "unsicher", stage=2)
    _check(client, board["id"], "richtig", stage=2)
    _event(client, first["id"], "solution")
    stage2 = client.get("/api/v1/practice/progress").json()["progress"]["sa-gummibaerchen"]["2"]
    # Unsicher gelesen ist kein Fehler von Thea; die Lösung kam erst danach
    assert stage2 == {**stage2, "attempts": 1, "solved": True, "solved_first_try": True}


def test_board_check_without_explicit_attempt_creates_one(client):
    board = _board(client, stage=1)
    _check(client, board["id"], "noch_nicht")
    stage1 = client.get("/api/v1/practice/progress").json()["progress"]["sa-gummibaerchen"]["1"]
    assert stage1["attempts"] == 1 and not stage1["solved"]


def test_board_checks_cannot_be_reported_by_the_browser(client):
    board = _board(client)
    attempt = client.post("/api/v1/practice/sa-gummibaerchen/attempts", json={"stage": 1, "board_id": board["id"]}).json()
    res = client.post(f"/api/v1/practice/attempts/{attempt['id']}/events",
                      json={"kind": "check", "data": {"status": "richtig"}})
    assert res.status_code == 400


def test_invalid_events_and_foreign_boards_are_rejected(client):
    attempt = client.post("/api/v1/practice/sa-gummibaerchen/attempts", json={"stage": 0}).json()
    url = f"/api/v1/practice/attempts/{attempt['id']}/events"
    assert client.post(url, json={"kind": "tanzen"}).status_code == 422
    assert client.post(url, json={"kind": "check", "data": {"status": "super"}}).status_code == 422
    assert client.post("/api/v1/practice/attempts/pat_gibtsnicht/events", json={"kind": "hint"}).status_code == 404
    other = _board(client, exercise_id="sa-apfelsaft-flaschen")
    res = client.post("/api/v1/practice/sa-gummibaerchen/attempts", json={"stage": 1, "board_id": other["id"]})
    assert res.status_code == 404


def test_attempt_survives_deleting_the_board(client, db_session):
    from backend.app.models.practice_attempt import PracticeAttempt
    board = _board(client)
    _check(client, board["id"], "richtig")
    assert client.delete(f"/api/v1/boards/{board['id']}").status_code == 204
    db_session.expire_all()
    attempt = db_session.query(PracticeAttempt).one()
    assert attempt.board_id is None and attempt.solved_at is not None


def test_trial_off_hides_attempts(client, monkeypatch):
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", False)
    assert client.post("/api/v1/practice/sa-gummibaerchen/attempts", json={"stage": 0}).status_code == 404
    assert client.get("/api/v1/practice/progress").json() == {"progress": {}}


def test_list_carries_progress_and_suggestion(client):
    data = client.get("/api/v1/practice").json()
    first = data["exercises"][0]["id"]
    assert data["vorschlag"]["art"] == "neu" and data["vorschlag"]["exercise_id"] == first
    board = _board(client, stage=1)
    _check(client, board["id"], "noch_nicht")
    data = client.get("/api/v1/practice").json()
    # Angefangen und nicht gelöst: weiter auf derselben Tafel
    assert data["vorschlag"] == {"art": "weiter", "familie": "sa-gummibaerchen", "exercise_id": "sa-gummibaerchen",
                                 "stufe": 1, "board_id": board["id"]}
    assert data["wiederholen"][0]["familie"] == "sa-gummibaerchen"


def _sample(label, x=0.0):
    return {"label": label, "strokes": [[[x, 0.0], [0.3, 0.5], [0.4, 1.0]], [[0.1, 0.6], [0.6, 0.6]]]}


def test_handwriting_samples_are_kept_per_digit_newest_last(client, monkeypatch):
    from backend.app.routers import practice as practice_router
    monkeypatch.setattr(practice_router, "SAMPLES_PER_DIGIT", 10)
    assert client.get("/api/v1/practice/handwriting").json() == {"samples": []}
    for k in range(12):
        res = client.post("/api/v1/practice/handwriting", json={"samples": [_sample("4", k / 100), _sample("7")]})
        assert res.status_code == 200
    samples = client.get("/api/v1/practice/handwriting").json()["samples"]
    fours = [s for s in samples if s["label"] == "4"]
    assert len(fours) == 10 and len([s for s in samples if s["label"] == "7"]) == 10
    assert fours[-1]["strokes"][0][0][0] == 0.11  # die neueste bleibt


def test_handwriting_rejects_bad_samples(client):
    assert client.post("/api/v1/practice/handwriting", json={"samples": [_sample("x")]}).status_code == 422
    empty = {"label": "3", "strokes": []}
    assert client.post("/api/v1/practice/handwriting", json={"samples": [empty]}).status_code == 422
    far = {"label": "3", "strokes": [[[9, 0], [0, 0]]]}
    assert client.post("/api/v1/practice/handwriting", json={"samples": [far]}).status_code == 422
