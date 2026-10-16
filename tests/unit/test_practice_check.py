"""Übungsprüfung auf der Tafel: Das Programm prüft, was Luna gelesen hat („Luna liest, der Code rechnet“)."""
from unittest.mock import patch

import pytest

from backend.app import config
from backend.app.services import practice_check as pc
from backend.app.services import practice_exercises as pe


def gummi():
    return pe.get_exercise("sa-gummibaerchen")


def read_table(rows, ops_l=(":3", "·10"), ops_r=None, result="10", unit="€",
               sentence="500 g Gummibärchen kosten 10 €.", **extra):
    return {"tabelle": [{"links": a, "rechts": b} for a, b in rows], "schritte_links": list(ops_l),
            "schritte_rechts": list(ops_r if ops_r is not None else ops_l), "ergebnis": result, "einheit": unit,
            "antwortsatz": sentence, "antwortsatz_passt": True, "unsicher": [], **extra}


GOOD_ROWS = [("150", "3"), ("50", "1"), ("500", "10")]


def test_correct_solution_is_accepted():
    out = pc.evaluate(gummi(), 1, read_table(GOOD_ROWS))
    assert out["status"] == pc.RICHTIG and out["probleme"] == []


def test_any_valid_path_counts():
    # anderer Hilfswert als im Buch: über 1 g statt über 50 g
    rows = [("150", "3"), ("1", "0,02"), ("500", "10")]
    out = pc.evaluate(gummi(), 2, read_table(rows, ops_l=(":150", "·500")))
    assert out["status"] == pc.RICHTIG


def test_wrong_result_names_the_read_value():
    rows = [("150", "3"), ("50", "1"), ("500", "1")]
    out = pc.evaluate(gummi(), 1, read_table(rows, result="1"))
    assert out["status"] == pc.NOCH_NICHT
    first = out["probleme"][0]
    assert first["bereich"] == "tabelle" and "500 → 1" in first["text"]


def test_wrong_step_is_found():
    out = pc.evaluate(gummi(), 1, read_table(GOOD_ROWS, ops_l=(":3", "·3")))
    assert "Rechenschritt links ·3" in out["probleme"][0]["text"]


def test_missing_unit_after_correct_result():
    out = pc.evaluate(gummi(), 1, read_table(GOOD_ROWS, unit="", sentence="500 g Gummibärchen kosten 10."))
    assert out["status"] == pc.NOCH_NICHT
    assert any("Einheit" in p["text"] for p in out["probleme"])


def test_answer_sentence_number_must_match_result():
    # Theas Fehler aus der Matheprobe: Rechnung und Antwortsatz passen nicht zusammen
    out = pc.evaluate(gummi(), 1, read_table(GOOD_ROWS, sentence="500 g Gummibärchen kosten 1 €."))
    assert any(p["bereich"] == "antwortsatz" and "lese ich 1" in p["text"] for p in out["probleme"])


def test_missing_answer_sentence():
    out = pc.evaluate(gummi(), 3, read_table(GOOD_ROWS, sentence=""))
    assert [p["bereich"] for p in out["probleme"]] == ["antwortsatz"]


def test_missing_steps_block_only_on_stage_one():
    no_ops = read_table(GOOD_ROWS, ops_l=(), ops_r=())
    assert pc.evaluate(gummi(), 1, no_ops)["status"] == pc.NOCH_NICHT
    relaxed = pc.evaluate(gummi(), 2, no_ops)
    assert relaxed["status"] == pc.RICHTIG and relaxed["hinweise"]


def test_unsure_reading_asks_instead_of_judging():
    rows = [("150", "3"), ("50", "1"), ("500", "70")]
    out = pc.evaluate(gummi(), 1, read_table(rows, result="70", unsicher=["tabelle", "ergebnis"]))
    assert out["status"] == pc.UNSICHER
    assert "nicht sicher" in pc.feedback(gummi(), out, 1)


def test_antiproportional_table():
    ex = pe.get_exercise("sa-umzug")
    rows = [("2", "12"), ("1", "24"), ("3", "8")]
    read = read_table(rows, ops_l=(":2", "·3"), ops_r=("·2", ":3"), result="8", unit="h",
                      sentence="Mit 3 Helfern dauert der Umzug 8 Stunden.")
    assert pc.evaluate(ex, 1, read)["status"] == pc.RICHTIG
    # proportional gerechnet (typischer Fehler) fällt auf
    wrong = read_table([("2", "12"), ("1", "6"), ("3", "18")], ops_l=(":2", "·3"), result="18",
                       sentence="Mit 3 Helfern dauert der Umzug 18 Stunden.")
    assert pc.evaluate(ex, 1, wrong)["status"] == pc.NOCH_NICHT


def test_division_calculation():
    ex = pe.get_exercise("sa-apfelsaft-flaschen")
    good = {"rechnung": "2100 : 0,7 = 21000 : 7 = 3000", "ergebnis": "3000", "einheit": "Flaschen",
            "antwortsatz": "Es werden 3000 Flaschen mit Apfelsaft gefüllt.", "antwortsatz_passt": True}
    assert pc.evaluate(ex, 1, good)["status"] == pc.RICHTIG
    theas = {**good, "rechnung": "2100 : 7 = 300", "ergebnis": "300", "antwortsatz": "Es werden 3 Flaschen befüllt."}
    out = pc.evaluate(ex, 3, theas)
    assert out["probleme"][0]["bereich"] == "ergebnis" and "300" in out["probleme"][0]["text"]


def test_reasoning_required_and_judged_by_luna():
    ex = pe.get_exercise("sa-flugzeug")
    base = read_table([("3", "2640"), ("0,5", "440"), ("2,5", "2200")], ops_l=(":6", "·5"), result="2200",
                      unit="km", sentence="In 2,5 Stunden fliegt das Flugzeug 2200 km.")
    assert any(p["bereich"] == "begruendung" for p in pc.evaluate(ex, 2, base)["probleme"])
    weak = {**base, "begruendung": "Je länger, desto weiter.", "begruendung_passt": False,
            "begruendung_hinweis": "Doppelte Zeit, doppelte Strecke?"}
    assert "Doppelte Zeit" in pc.evaluate(ex, 2, weak)["probleme"][0]["text"]
    good = {**base, "begruendung": "Es fliegt gleich schnell.", "begruendung_passt": True}
    assert pc.evaluate(ex, 2, good)["status"] == pc.RICHTIG


@pytest.mark.parametrize("text,expected", [(":3", (":", 3)), ("·10", ("·", 10)), ("x 10", ("·", 10)),
                                           ("*4", ("·", 4)), ("/6", (":", 6)), ("", None), ("?", None)])
def test_parse_op(text, expected):
    assert pc.parse_op(text) == expected


def test_feedback_adds_help_from_second_attempt():
    out = pc.evaluate(gummi(), 1, read_table(GOOD_ROWS, sentence=""))
    assert gummi()["hilfen"]["denkanstoss"] not in pc.feedback(gummi(), out, 1)
    assert gummi()["hilfen"]["denkanstoss"] in pc.feedback(gummi(), out, 2)


def test_check_endpoint_marks_board_solved(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", True)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    board = client.post("/api/v1/boards", json={"subject_id": "sub_math", "title": "Gummi · Stufe 1",
                                                "practice_exercise_id": "sa-gummibaerchen", "practice_stage": 1}).json()
    read = read_table(GOOD_ROWS, bereiche={"tabelle": {"x_pct": 1, "y_pct": 2, "w_pct": 3, "h_pct": 4}})
    with patch.object(pc.llm, "is_available", return_value=True), \
         patch.object(pc, "read_board", return_value=read):
        res = client.post("/api/v1/practice/sa-gummibaerchen/check",
                          json={"image_base64": "data:image/jpeg;base64,AAAA", "stage": 1, "board_id": board["id"]})
    assert res.status_code == 200 and res.json()["status"] == "richtig"
    assert client.post(f"/api/v1/boards/{board['id']}/open").json()["practice_solved"] is True
    assert (tmp_path / "practice_checks" / "checks.jsonl").exists()


def test_check_endpoint_without_ai(client, monkeypatch):
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", True)
    res = client.post("/api/v1/practice/sa-gummibaerchen/check", json={"image_base64": "AAAA", "stage": 1})
    assert res.status_code == 503
