"""Erklär-Stufe (services/explanations.py): Aufbau für die Ansicht und Prüfung der Daten."""
import copy

from backend.app.services import explanations
from backend.app.services import practice_exercises as pe


def _ex(exercise_id="sa-gummibaerchen"):
    return copy.deepcopy(pe._load_all()[exercise_id])


def test_task_is_read_first_sentence_by_sentence_with_marks():
    built = pe.get_exercise("sa-gummibaerchen")["erklaeren"]
    first = built["schritte"][0]
    assert first[0]["satz"] == explanations.INTRO
    assert [b["zeige"] for b in first[1:]] == [["a1"], ["a2"], ["a3"]]
    assert "".join(s["t"] for s in built["segmente"]) == _ex()["aufgabentext"]
    known = [s for s in built["segmente"] if "bekannt" in s["marken"]]
    assert "".join(s["t"] for s in known) == "kosten 150 g Gummibärchen 3 €" and all("a2" in s["marken"] for s in known)
    assert all(b["audio"].startswith("/static/hilfe/saetze/") for step in built["schritte"] for b in step)


def test_quiz_answers_are_shuffled_but_stay_with_their_reason():
    raw = _ex()["erklaerung"]["abfrage"]
    built = pe.get_exercise("sa-gummibaerchen")["erklaeren"]["abfrage"]
    for q_raw, q in zip(raw, built):
        assert q["antworten"][q["richtig"]] == q_raw["antworten"][q_raw["richtig"]]
        for answer, why in zip(q["antworten"], q["warum"]):
            assert why == q_raw["warum"][q_raw["antworten"].index(answer)]


def test_dreisatz_table_comes_from_the_exercise():
    display = pe.get_exercise("sa-taxi")["erklaeren"]["anzeige"]
    assert display["zeilen"] == [["3", "10,20"], ["1", "30,60"], ["4", "7,65"]]
    assert display["pfeile"] == [[":3", "·3"], ["·4", ":4"]]  # antiproportional: rechts umgekehrt


def test_validate_finds_wrong_calculation_foreign_number_unknown_element_and_missing_mark():
    ex = _ex()
    data = ex["erklaerung"]
    data["schritte"][3][2]["satz"] = "Denn 150 g geteilt durch 3 ist 60 g."
    data["schritte"][0][0]["satz"] = "Stell dir 777 Gummibärchen vor."
    data["schritte"][1][1]["zeige"].append("z9l")
    data["markierungen"]["weg"] = "steht nicht im Text"
    errors = pe.validate(ex)
    assert any("150 geteilt durch 3 ist nicht 60" in e for e in errors)
    assert any("Zahl 777" in e for e in errors)
    assert any("„z9l“ gibt es nicht" in e for e in errors)
    assert any("Markierung „weg“" in e for e in errors)


def test_only_exercises_with_an_explanation_have_the_stage():
    assert pe.get_exercise("sa-gummibaerchen")["stufen"][0] == -2
    assert -2 not in pe.get_exercise("sa-gummibaerchen-z1")["stufen"]  # Zwilling ohne Erklärung


def test_short_answers_are_spoken_as_a_whole_sentence():
    built = pe.get_exercise("sa-gummibaerchen")["erklaeren"]["abfrage"][0]
    assert explanations.spoken_answer(built["frage"], "größer") == "Der Preis wird größer."
    assert built["audio"]["antworten"][built["antworten"].index("größer")] == \
        explanations.sentence_url("Der Preis wird größer.")
    assert explanations.spoken_answer("Was bedeuten die 30,60 €?", "Das Trinkgeld.") == "Das Trinkgeld."


def test_validate_wants_short_answers_to_complete_the_question():
    ex = _ex()
    ex["erklaerung"]["abfrage"][0]["frage"] = "Du kaufst mehr Gummibärchen. Wie ändert sich der Preis?"
    assert any("kurze Antworten" in e for e in pe.validate(ex))


def test_validate_wants_units_in_every_calculation():
    """„150 geteilt durch 3 ist 50“ ist für 150 g falsch (Nutzer 31.10.): Größen tragen ihre Einheit."""
    ex = _ex()
    beat = ex["erklaerung"]["schritte"][3][2]
    for wrong, why in [("Denn 150 geteilt durch 3 ist 50.", "Größen immer mit Einheit"),
                       ("Denn 150 g geteilt durch 3 ist 50.", "Größen immer mit Einheit"),
                       ("Denn 150 g geteilt durch 3 ist 50 €.", "dieselbe Einheit"),
                       ("Denn 150 g geteilt durch 3 ist 50 Stück.", "dieselbe Einheit")]:
        beat["satz"] = wrong
        assert any(why in e for e in pe.validate(ex)), wrong
    beat["satz"] = "Denn 150 g geteilt durch 3 ist 50 g."
    assert pe.validate(ex) == []
    # geteilt durch dieselbe Einheit ergibt eine Anzahl; Einzahl/Mehrzahl zählt als gleich
    assert explanations._unit_error("Liter", "geteilt durch", "Liter", "") == ""
    assert explanations._unit_error("Liter", "geteilt durch", "Liter", "Liter") != ""
    assert explanations._unit_error("Personen", "geteilt durch", "", "Person") == ""
