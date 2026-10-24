"""Übungstyp „Ordnen“: Datenprüfung und vorbereitete Kärtchen."""
from backend.app.services.exercise_types import ordnen
from backend.app.services import practice_exercises as pe


def _ex(**kw):
    return {"id": "x", "titel": "Ablauf", "schritte": ["a", "b", "c", "d", "e"], "ablenker": ["z"], **kw}


def test_valid_exercise_has_no_errors():
    assert ordnen.validate(_ex()) == []


def test_validate_catches_broken_data():
    assert ordnen.validate(_ex(titel="")) == ["Titel des Ablaufs fehlt"]
    assert ordnen.validate(_ex(schritte=["a", "b"])) == ["Mindestens 3 Schritte"]
    assert ordnen.validate(_ex(schritte=["a", "b", "A "])) == ["Ein Schritt kommt doppelt vor"]
    assert ordnen.validate(_ex(ablenker=[])) == ["Mindestens ein Ablenker für Stufe 3"]
    assert ordnen.validate(_ex(ablenker=["c"])) == ["Ein Ablenker ist zugleich ein Schritt"]
    assert ordnen.validate(_ex(buch="gibt-es-nicht.jpg")) == ["Bild „gibt-es-nicht.jpg“ fehlt in exercise_sets/bilder"]


def test_cards_are_mixed_never_in_order_and_help_fixes_first_and_last():
    for steps in (["a", "b", "c"], ["a", "b", "c", "d", "e"], list("abcdefghij")):
        prep = ordnen.prepare(_ex(schritte=steps))
        assert sorted(prep["karten"]) == sorted(steps) and prep["karten"] != steps
        assert sorted(prep["karten_ablenker"]) == sorted(steps + ["z"])
    prep = ordnen.prepare(_ex())
    assert prep["fest"] == [0, 4] and sorted(prep["karten_hilfe"]) == ["b", "c", "d"]
    assert ordnen.prepare(_ex(schritte=["a", "b", "c"]))["fest"] == [0]


def test_burner_exercises_load_with_book_image():
    ex = pe.get_exercise("ch-brenner-entzuenden", include_drafts=True)
    assert ex["typ"] == "ordnen" and len(ex["schritte"]) == 6
    assert ex["buch_url"].endswith("ch-brenner-ablauf_buch.jpg")
