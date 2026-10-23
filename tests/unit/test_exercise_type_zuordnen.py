"""Übungstyp „Zuordnen“: Daten geprüft, Wortbänke vollständig, Bilder werden ausgeliefert."""
import pytest

from backend.app import config
from backend.app.services import practice_exercises as pe
from backend.app.services.exercise_types import zuordnen


def brenner():
    return pe.get_exercise("ch-brenner", include_drafts=True)


def test_burner_uses_the_terms_of_the_book():
    ex = brenner()
    assert ex["typ"] == "zuordnen" and ex["fach"] == "sub_chemie" and ex["status"] == "entwurf"
    terms = [f["begriff"] for f in ex["felder"]]
    assert "Stellschraube für Luftzufuhr" in terms and "Brennerfuß" in terms
    assert sorted(ex["wortbank"]) == sorted(terms)
    assert set(ex["wortbank_ablenker"]) == set(terms) | set(ex["ablenker"])
    assert ex["bild_url"].endswith("ch-brenner.jpg") and ex["original_url"].endswith("ch-brenner_original.jpg")


def test_validate_catches_broken_data():
    ex = brenner()
    fields = [dict(f) for f in ex["felder"]]
    fields[1]["begriff"] = fields[0]["begriff"]
    fields[2]["x"] = 1.5
    broken = {**ex, "felder": fields, "ablenker": [fields[3]["begriff"]], "bild": {"datei": "fehlt.jpg"}}
    errors = zuordnen.validate(broken)
    assert "Ein Begriff kommt doppelt vor" in errors
    assert any("außerhalb des Bilds" in e for e in errors)
    assert "Mindestens zwei Ablenker für Stufe 2" in errors and "Ein Ablenker ist zugleich ein richtiger Begriff" in errors
    assert any("fehlt in exercise_sets/bilder" in e for e in errors)


@pytest.fixture
def trial_on(monkeypatch):
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", True)


def test_images_are_served_only_by_safe_name(client, trial_on):
    res = client.get("/api/v1/practice/bilder/ch-brenner.jpg")
    assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
    assert client.get("/api/v1/practice/bilder/..%2Fzuordnen_chemie.json").status_code == 404
    assert client.get("/api/v1/practice/bilder/gibt-es-nicht.jpg").status_code == 404


def test_images_are_off_with_the_trial(client, monkeypatch):
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", False)
    assert client.get("/api/v1/practice/bilder/ch-brenner.jpg").status_code == 404
