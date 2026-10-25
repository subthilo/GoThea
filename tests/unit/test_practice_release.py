"""Freigabe von Übungen in der App: gilt vor dem Status der Datei, immer für die ganze Aufgabe."""
import pytest

from backend.app import config
from backend.app.services import practice_exercises as pe


def test_release_overrides_the_file_and_withdraw_works_both_ways(db_session):
    assert pe.is_draft(pe.get_exercise("km-messbecher", include_drafts=True))
    assert pe.set_release(db_session, "km-messbecher", pe.FREIGEGEBEN) == ["km-messbecher"]
    ex = pe.get_exercise("km-messbecher")
    assert ex is not None and ex["status"] == "freigegeben" and ex["freigegeben_am"]
    assert pe.validate_header(ex) == []
    pe.set_release(db_session, "sa-gummibaerchen", pe.ENTWURF)   # in der Datei freigegeben
    assert pe.get_exercise("sa-gummibaerchen") is None
    pe.sync_releases(db_session)                                   # aus der Datenbank wieder geladen
    assert "sa-gummibaerchen" not in {f["id"] for f in pe.list_exercises()}


def test_release_covers_the_whole_family(db_session):
    assert pe.set_release(db_session, "sa-gummibaerchen-z1", pe.ENTWURF) == ["sa-gummibaerchen", "sa-gummibaerchen-z1"]


def test_release_refuses_unknown_or_broken_exercises(db_session, monkeypatch):
    with pytest.raises(KeyError):
        pe.set_release(db_session, "gibt-es-nicht", pe.FREIGEGEBEN)
    monkeypatch.setattr(pe, "validate", lambda ex: ["kaputt"])
    with pytest.raises(ValueError):
        pe.set_release(db_session, "km-messbecher", pe.FREIGEGEBEN)


def test_api_release_needs_parents(strict_client, monkeypatch):
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", True)
    assert strict_client.put("/api/v1/practice/km-messbecher/freigabe", json={"status": "freigegeben"}).status_code == 403


def test_api_release_and_names(client, monkeypatch):
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", True)
    r = client.put("/api/v1/practice/km-messbecher/freigabe", json={"status": "freigegeben"})
    assert r.status_code == 200 and r.json()["uebungen"] == ["km-messbecher"]
    listed = client.get("/api/v1/practice").json()          # ohne Eltern-Token: nur Freigegebenes
    assert "km-messbecher" in {f["id"] for f in listed["exercises"]}
    assert listed["faecher"]["sub_math"]
    assert client.put("/api/v1/practice/km-messbecher/freigabe", json={"status": "weg"}).status_code == 422
