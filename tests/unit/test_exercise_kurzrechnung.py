"""Übungstyp „Kurzrechnung“: Rechnen in Theas Schreibweise, Datenprüfung, Angebote, Einmaleins-Check."""
import json
from datetime import datetime, timedelta
from fractions import Fraction

import pytest

from backend.app import config
from backend.app.services import practice_exercises as pe
from backend.app.services.exercise_types import kurzrechnung as kr


def _ex(**kw):
    return {"id": "x", "aufgaben": [{"rechnung": "3,2 : 8", "ergebnis": "0,4"}], **kw}


# --- Rechnen ---------------------------------------------------------------------------------------------

def test_evaluates_like_on_the_sheet():
    assert kr.evaluate("3,2 : 8") == Fraction(2, 5)
    assert kr.evaluate("2 103,976 · 1 000") == 2103976
    assert kr.evaluate("4,03 : 1 000") == Fraction("0.00403")
    assert kr.evaluate("11/18 : 22/6") == Fraction(1, 6)
    assert kr.evaluate("2 + 3 · 4") == 14 and kr.evaluate("(2 + 3) · 4") == 20
    assert kr.evaluate("83,4 − 5,579") == Fraction("77.821")
    with pytest.raises(ValueError):
        kr.evaluate("3,2 ? 8")


def test_decimal_formatting_without_thousands_separators():
    assert kr.fmt_decimal(Fraction(2, 5)) == "0,4"
    assert kr.fmt_decimal(Fraction(2103976)) == "2103976"
    assert kr.fmt_decimal(Fraction("0.0004")) == "0,0004"
    assert kr.is_decimal(Fraction(1, 8)) and not kr.is_decimal(Fraction(1, 3))


def test_units_convert_within_one_dimension():
    assert kr.convert("3/4 l", "cm³") == 750
    assert kr.convert("2 hl", "l") == 200
    assert kr.convert("1,5 km", "m") == 1500
    with pytest.raises(ValueError):
        kr.convert("1 l", "kg")


# --- Lösung und Datenprüfung -------------------------------------------------------------------------------

def test_reduce_asks_for_exactly_that_fraction():
    sol = kr.solve({"kuerzen": "15/24", "mit": 3})
    assert sol["exakt"] == (5, 8)
    assert kr.solve({"kuerzen": "48/96", "mit": "vollständig"})["exakt"] == (1, 2)
    with pytest.raises(ValueError):
        kr.solve({"kuerzen": "15/24", "mit": 5})


def test_dividing_a_fraction_accepts_any_equal_fraction_and_shows_the_sheet_form():
    item = {"rechnung": "15/24 : 3", "antwort": "bruch", "gekuerzt": False, "ergebnis": "5/24"}
    sol = kr.solve(item)
    assert sol["exakt"] is None and sol["text"] == "5/24"
    assert kr._matches(sol, "10/48") and not kr._matches(sol, "5/8")


def test_validate_recomputes_every_result():
    assert kr.validate(_ex()) == []
    assert kr.validate(_ex(aufgaben=[{"rechnung": "3,2 : 8", "ergebnis": "4"}])) == \
        ["Aufgabe 1: ergebnis 4 stimmt nicht, richtig ist 0,4"]
    assert kr.validate(_ex(aufgaben=[{"rechnung": "3,2 : 8"}])) == ["Aufgabe 1: ergebnis fehlt (Lösung 0,4)"]
    assert kr.validate(_ex(aufgaben=[{"rechnung": "1 : 3", "ergebnis": "0,3"}]))[0].startswith("Aufgabe 1: 1 : 3 ergibt keine")
    assert kr.validate(_ex(aufgaben=[{"rechnung": "3,2 : 8", "ergebnis": "0,4", "fehler": "0,40"}])) == \
        ["Aufgabe 1: fehler 0,40 ist gar nicht falsch"]
    assert kr.validate(_ex(aufgaben=[{"rechnung": "2 : 12", "antwort": "bruch", "ergebnis": "2/12"}], stufen=[-1, 2])) == \
        ["Aufgabe 1: ergebnis 2/12 stimmt nicht, richtig ist 1/6"]


def test_stage_one_needs_an_estimate():
    fractions_only = _ex(aufgaben=[{"kuerzen": "15/24", "mit": 3, "ergebnis": "5/8"}])
    assert kr.validate(fractions_only) == ["Stufe 1 braucht eine Aufgabe mit Überschlag (sonst stufen: [-1, 2])"]
    assert kr.validate({**fractions_only, "stufen": [-1, 2]}) == []


def test_generated_exercises_have_no_own_tasks_and_only_stage_two():
    assert kr.validate({"id": "c", "erzeugt": "einmaleins", "stufen": [2]}) == []
    assert kr.validate({"id": "c", "erzeugt": "einmaleins"}) == ["Einmaleins: nur Stufe 2 (stufen: [2])"]
    assert kr.validate({"id": "w", "erzeugt": "einmaleins_wacklig", "stufen": [2]}) == \
        ["einmaleins_wacklig braucht aus (ID des Checks)"]
    assert kr.validate({"id": "x", "erzeugt": "zauberei", "stufen": [2]}) == ["erzeugt: einmaleins oder einmaleins_wacklig"]


# --- Angebote ---------------------------------------------------------------------------------------------

def test_estimate_offers_four_orders_of_magnitude_with_the_rounded_result():
    ue = kr.estimate_options(Fraction(2, 5), "s")
    assert len(ue["angebote"]) == 4 and ue["angebote"][ue["richtig"]] == "0,4"
    values = [kr.number(v) for v in ue["angebote"]]
    assert all(b == a * 10 for a, b in zip(values, values[1:]))
    assert kr.estimate_options(Fraction("342.9"), "s")["angebote"][kr.estimate_options(Fraction("342.9"), "s")["richtig"]] == "300"
    assert kr.estimate_options(Fraction("0.775"), "t")["angebote"][kr.estimate_options(Fraction("0.775"), "t")["richtig"]] == "0,8"


def test_tap_offers_contain_the_answer_and_typical_mistakes():
    item = {"rechnung": "3,2 : 8", "ergebnis": "0,4"}
    opts = kr.choice_options(item, kr.solve(item), "s")
    assert opts["angebote"][opts["richtig"]] == "0,4" and set(opts["angebote"]) >= {"4", "0,04"}
    item = {"kuerzen": "48/96", "mit": "vollständig"}
    opts = kr.choice_options(item, kr.solve(item), "s")
    assert opts["angebote"][opts["richtig"]] == "1/2" and "24/48" in opts["angebote"]
    item = {"rechnung": "28/72 : 12/16", "antwort": "bruch"}
    opts = kr.choice_options(item, kr.solve(item), "s")
    assert opts["angebote"][opts["richtig"]] == "14/27" and "27/14" in opts["angebote"]  # Kehrwert
    assert len(set(opts["angebote"])) == len(opts["angebote"]) >= 3


def test_only_multiplication_and_division_get_an_estimate():
    for item, expected in [({"rechnung": "34,29 · 10"}, True), ({"rechnung": "18,45 + 59,75"}, False),
                           ({"rechnung": "3,2 : 8", "ueberschlag": False}, False),
                           ({"umrechnen": "1 l", "in": "cm³"}, False)]:
        assert kr.has_estimate(item, kr.solve(item)) is expected


def test_drafts_load_with_tasks_and_solutions():
    ex = pe.get_exercise("km-zehnerzahlen-1", include_drafts=True)
    assert ex["typ"] == "kurzrechnung" and len(ex["liste"]) == 8
    assert ex["liste"][0]["loesung"] == "342,9" and ex["liste"][0]["ueberschlag"]
    assert pe.get_exercise("km-kuerzen-dividieren", include_drafts=True)["liste"][1]["loesung"] == "5/24"


# --- Einmaleins ------------------------------------------------------------------------------------------

def test_einmaleins_check_has_all_36_tasks_without_commuted_twins():
    ex = pe.get_exercise("km-einmaleins-check", include_drafts=True)
    keys = {kr._key(it["zeige"]) for it in ex["liste"]}
    assert len(ex["liste"]) == 36 and len(keys) == 36 and ex["check"] is True
    assert pe.validate_header(ex) == []  # Grundwissen: keine Materialseite nötig


def test_basic_knowledge_source_only_for_generated_exercises():
    ex = pe.get_exercise("km-zehnerzahlen-1", include_drafts=True)
    assert "quelle: material_id fehlt" in pe.validate_header({**ex, "quelle": {"material": "Grundwissen", "grundwissen": "x"}})


def _steps(rows):
    return [{"aufgabe": k, "antwort": a, "richtig": r, "ms": ms} for k, a, r, ms in rows]


def test_check_sorts_into_safe_slow_and_wrong():
    rows = [(f"{a} · {b}", str(a * b), True, 2000) for a, b in kr.EINMALEINS]
    rows[0] = ("2 · 2", "5", False, 1500)          # falsch
    rows[1] = ("3 · 2", "6", True, 9000)           # langsam (Grenze: max(2 · 2000, 4000) = 4000), Faktoren vertauscht
    result = kr.evaluate_check(_steps(rows), [])
    assert result["median_ms"] == 2000 and result["grenze_ms"] == 4000
    assert result["zellen"]["2·2"]["status"] == "falsch" and result["zellen"]["2·3"]["status"] == "langsam"
    assert result["wacklig"] == ["2·2", "2·3"]


def test_wobbly_task_is_safe_after_one_quick_right_first_answer():
    rows = [(f"{a} · {b}", str(a * b), True, 2000) for a, b in kr.EINMALEINS]
    rows[0] = ("2 · 2", "5", False, 1500)
    rows[1] = ("2 · 3", "6", True, 9000)
    practice = [_steps([("2 · 2", "4", True, 1800), ("3 · 2", "7", False, 1000), ("3 · 2", "6", True, 1000)])]
    result = kr.evaluate_check(_steps(rows), practice)
    assert result["wacklig"] == ["2·3"]  # 2·3 erst im zweiten Anlauf richtig


def _attempt(db, exercise_id, steps, solved, at):
    from backend.app.models.practice_attempt import PracticeAttempt, PracticeEvent
    a = PracticeAttempt(exercise_id=exercise_id, exercise_type="kurzrechnung", stage=2, started_at=at,
                        last_activity_at=at, checks=1 if solved else 0, solved_at=at if solved else None)
    db.add(a)
    db.flush()
    for i, st in enumerate(steps):
        db.add(PracticeEvent(attempt_id=a.id, kind="step", created_at=at + timedelta(seconds=i), data_json=json.dumps(st)))
    db.commit()
    return a


def test_wobbly_exercise_follows_the_last_check(db_session):
    check = pe.get_exercise("km-einmaleins-check", include_drafts=True)
    wobbly = pe.get_exercise("km-einmaleins-wacklig", include_drafts=True)
    assert kr.hidden(wobbly, db_session)  # noch kein Check
    rows = [(f"{a} · {b}", str(a * b), True, 2000) for a, b in kr.EINMALEINS]
    rows[5] = ("7 · 8", "54", False, 3000)
    start = datetime(2026, 10, 25, 15)
    _attempt(db_session, check["id"], _steps(rows), True, start)
    assert not kr.hidden(wobbly, db_session)
    personal = kr.personalize(wobbly, db_session)
    assert [kr._key(it["zeige"]) for it in personal["liste"]] == ["7·8"] and personal["grenze_ms"] == 4000
    _attempt(db_session, wobbly["id"], _steps([("8 · 7", "56", True, 1500)]), True, start + timedelta(days=1))
    assert kr.hidden(wobbly, db_session)
    assert kr.auswertung(check, db_session)["wacklig"] == []


def test_evaluation_endpoint_is_for_parents_only(client, monkeypatch):
    from backend.main import app
    from backend.app.services.parent_auth import is_parent
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", True)
    assert client.get("/api/v1/practice/km-einmaleins-check/auswertung").status_code == 403
    app.dependency_overrides[is_parent] = lambda: True
    try:
        assert client.get("/api/v1/practice/km-einmaleins-check/auswertung").json() == {"auswertung": None}
        listed = {ex["id"] for ex in client.get("/api/v1/practice").json()["exercises"]}
        assert "km-einmaleins-check" in listed and "km-einmaleins-wacklig" not in listed  # nichts Wackliges
    finally:
        app.dependency_overrides.pop(is_parent, None)


def test_step_events_are_recorded_without_counting(db_session):
    from backend.app.services import practice_attempts
    a = practice_attempts.start(db_session, {"id": "km-zehnerzahlen-1", "typ": "kurzrechnung"}, 2)
    practice_attempts.record(db_session, a, "step", {"aufgabe": "1", "antwort": "342,9", "richtig": True, "ms": 1200})
    assert a.checks == 0 and a.failed_checks == 0 and a.solved_at is None
