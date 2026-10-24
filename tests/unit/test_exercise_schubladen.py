"""Übungstyp „Schubladen“: Datenprüfung, Beispiele und die Fehler-Belegung für Stufe 3."""
from backend.app.services.exercise_types import schubladen
from backend.app.services import practice_exercises as pe


def _ex(**kw):
    return {"id": "x", "gruppen": [{"name": "A", "begriffe": ["a1", "a2"]}, {"name": "B", "begriffe": ["b1", "b2"]}], **kw}


def test_valid_exercise_has_no_errors():
    assert schubladen.validate(_ex()) == []


def test_validate_catches_broken_data():
    assert schubladen.validate(_ex(gruppen=[{"name": "A", "begriffe": ["a", "b", "c", "d"]}])) == ["Mindestens zwei Gruppen"]
    assert schubladen.validate(_ex(gruppen=[{"name": "A", "begriffe": ["a1", "x"]}, {"name": "B", "begriffe": ["x", "b"]}])) == \
        ["Ein Begriff steht in zwei Gruppen"]
    assert schubladen.validate(_ex(gruppen=[{"name": "A", "begriffe": ["a1", "a2", "a3"]}, {"name": "B", "begriffe": []}])) == \
        ["Gruppe ohne Begriffe", "Mindestens 4 Begriffe"]
    assert schubladen.validate(_ex(gruppen=[{"name": "A", "begriffe": ["a1", "a2"]}, {"name": "a ", "begriffe": ["b1", "b2"]}])) == \
        ["Ein Gruppenname kommt doppelt vor"]


def test_stage_three_has_exactly_two_terms_in_the_wrong_drawer():
    for ex_id in ("x", "y", "z", "ch"):
        ex = _ex(id=ex_id)
        layout = schubladen.wrong_layout(ex)
        right = {t: i for i, g in enumerate(ex["gruppen"]) for t in g["begriffe"]}
        assert sorted(layout) == sorted(right)
        assert sum(layout[t] != right[t] for t in right) == 2


def test_examples_are_one_per_drawer():
    prep = schubladen.prepare(_ex())
    assert prep["beispiele"] == ["a1", "b1"] and sorted(prep["karten"]) == ["a1", "a2", "b1", "b2"]


def test_chemistry_drafts_load():
    ex = pe.get_exercise("ch-reinstoffe-gemische", include_drafts=True)
    assert ex["typ"] == "schubladen" and len(ex["karten"]) == 8 and ex["buch_url"]
