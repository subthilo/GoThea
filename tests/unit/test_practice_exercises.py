"""Übungen aus echten Aufgaben: Daten nachgerechnet, Bausteine vollständig, Schalter wirkt."""
import pytest

from backend.app import config
from backend.app.services import practice_exercises as pe


def all_exercises():
    return [pe.get_exercise(i) for e in pe.list_exercises() for i in [e["id"], *e["zwillinge"]]]


def test_pilot_data_is_loaded():
    exercises = all_exercises()
    assert len(exercises) >= 14
    assert all(ex["ableitung"] in ("A", "B") for ex in exercises)


@pytest.mark.parametrize("ex", all_exercises(), ids=lambda ex: ex["id"])
def test_every_solution_is_recalculated_exactly(ex):
    # „Luna liest, der Code rechnet“: jede Zeile, Ergebnis, Antwortsatz, Schätzfrage
    assert pe.validate(ex) == []


@pytest.mark.parametrize("ex", all_exercises(), ids=lambda ex: ex["id"])
def test_building_blocks_can_fill_every_field(ex):
    blocks = ex["bausteine"]
    tokens = blocks["werte"] + blocks["rechenschritte"]
    for field, expected in blocks["felder"].items():
        assert expected in tokens, f"{field}: {expected} fehlt"
    assert len(blocks["werte"]) > len(set(blocks["felder"].values()) & set(blocks["werte"])), "keine Ablenker"
    answers = blocks["antworten"]
    assert sum(a["richtig"] for a in answers) == 1
    assert len({a["text"] for a in answers}) == len(answers) >= 2


def test_twin_reference_points_to_original():
    for ex in all_exercises():
        if ex["ableitung"] == "B":
            assert pe.get_exercise(ex["zwilling_von"])["ableitung"] == "A"


def test_validate_catches_wrong_row():
    ex = pe.get_exercise("sa-gummibaerchen")
    broken = {**ex, "zeilen": [[150, 3], [50, 1], [500, 11]]}
    assert any("Zeile 3" in e for e in pe.validate(broken))


def test_money_formatting():
    assert pe.fmt_number(8.4, money=True) == "8,40"
    assert pe.fmt_number(10, money=True) == "10"
    assert pe.fmt_number(0.5) == "0,5"


def test_api_lists_and_returns_exercises(client, monkeypatch):
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", True)
    data = client.get("/api/v1/practice").json()
    assert data["enabled"] is True
    first = data["exercises"][0]
    detail = client.get(f"/api/v1/practice/{first['id']}").json()
    assert detail["bausteine"]["felder"]
    assert client.get("/api/v1/practice/gibt-es-nicht").status_code == 404


def test_api_is_off_when_switched_off(client, monkeypatch):
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", False)
    assert client.get("/api/v1/practice").json() == {"enabled": False, "exercises": []}
    assert client.get("/api/v1/practice/sa-gummibaerchen").status_code == 404
