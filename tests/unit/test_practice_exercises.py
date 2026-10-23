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


def test_reasoning_task_offers_reasoning_choices():
    blocks = pe.get_exercise("sa-flugzeug")["bausteine"]
    assert len(blocks["begruendungen"]) == 3
    assert sum(b["richtig"] for b in blocks["begruendungen"]) == 1
    assert pe.get_exercise("sa-gummibaerchen")["bausteine"]["begruendungen"] == []


def test_twin_reference_points_to_original():
    for ex in all_exercises():
        if ex["ableitung"] == "B":
            assert pe.get_exercise(ex["zwilling_von"])["ableitung"] == "A"


def test_validate_catches_wrong_row():
    ex = pe.get_exercise("sa-gummibaerchen")
    broken = {**ex, "zeilen": [[150, 3], [50, 1], [500, 11]]}
    assert any("Zeile 3" in e for e in pe.validate(broken))


@pytest.mark.parametrize("ex", all_exercises(), ids=lambda ex: ex["id"])
def test_every_exercise_has_a_checked_reasoning_path(ex):
    # Leichteste Stufe: Gedankengang in Sätzen, mindestens eine nachgerechnete Gleichung
    steps = ex["gedankengang"]
    assert len(steps) >= 3
    assert sum(len(pe.EQUATION.findall(pe.fill_blanks(s["satz"]))) for s in steps) >= 2


def test_reasoning_path_catches_wrong_equation_and_wrong_result():
    ex = pe.get_exercise("sa-gummibaerchen")
    steps = [dict(s) for s in ex["gedankengang"]]
    steps[1] = {"satz": "Erst rechnen wir auf 50 g herunter: 150 g : [[3]] = [[60]] g."}
    errors = pe.validate({**ex, "gedankengang": steps})
    assert any("150 : 3 ergibt nicht 60" in e for e in errors)
    steps = [dict(s) for s in ex["gedankengang"]][:-1] + [{"satz": "500 g Gummibärchen kosten [[11]] €."}]
    assert "Gedankengang: letzte Lücke ist nicht das Ergebnis" in pe.validate({**ex, "gedankengang": steps})


@pytest.mark.parametrize("ex", all_exercises(), ids=lambda ex: ex["id"])
def test_every_exercise_names_subject_topic_and_material_page(ex):
    assert pe.validate_header(ex) == []


def _book_with_topic(db):
    """Buch „Fundamente“ mit Kapitel ab Buchseite 11 (32 Seiten) und einem Mathe-Thema."""
    from backend.app.models.material import Material
    from backend.app.models.taxonomy import Topic
    db.add(Topic(id="top_zuord", subject_id="sub_math", name="Zuordnungen"))
    db.add(Material(id="mat_book", subject_id="sub_math", title="Fundamente der Mathematik 7", kind="Buch",
                    filename="b.pdf", file_path="/x/b.pdf", page_count=304))
    db.add(Material(id="mat_book_ch01", parent_id="mat_book", subject_id="sub_math", title="Kapitel 1",
                    kind="Buchauszug", filename="c.pdf", file_path="/x/c.pdf", page_count=32, start_page=11))
    db.commit()
    return {"id": "x", "fach": "sub_math", "thema": "top_zuord",
            "quelle": {"art": "Buch", "material": "Fundamente der Mathematik 7", "material_id": "mat_book_ch01",
                       "material_seite": 16, "seite": 26, "nummer": "1"}}


def test_references_are_checked_against_the_database(db_session):
    ex = _book_with_topic(db_session)
    assert pe.check_references(db_session, ex) == []

    def errors(**changes):
        return pe.check_references(db_session, {**ex, **changes})

    assert errors(thema="top_fehlt") == ["Thema top_fehlt gibt es nicht"]
    assert errors(fach="sub_bio") and any("gehört nicht zum Fach" in e for e in errors(fach="sub_bio"))
    assert any("ist Buchseite 27, nicht 26" in e for e in errors(quelle={**ex["quelle"], "material_seite": 17}))
    assert any("keine Seite 40" in e for e in errors(quelle={**ex["quelle"], "material_seite": 40, "seite": None}))
    assert any("gibt es nicht" in e for e in errors(nachschlagen={"material_id": "mat_weg", "material_seite": 1}))
    assert any("heißt „Fundamente" in e for e in errors(quelle={**ex["quelle"], "material": "Mathebuch"}))


def test_header_without_subject_or_page_is_rejected():
    errors = pe.validate_header({"quelle": {"material_id": "mat_a"}})
    assert errors == ["Fach fehlt (fach: sub_…)", "Thema fehlt (thema: top_…)", "quelle: material_seite fehlt"]


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
