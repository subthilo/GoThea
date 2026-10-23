"""Übungen aus echten Aufgaben: Daten nachgerechnet, Bausteine vollständig, Schalter wirkt."""
import pytest

from backend.app import config
from backend.app.services import practice_exercises as pe
from backend.app.services.exercise_types import sachaufgabe as sa


def all_exercises(typ=None):
    """Alle Übungen samt Entwürfen (auch solche, die in keiner Liste auftauchen); mit typ nur die eines Übungstyps."""
    return [ex for ex in (pe.get_exercise(i, include_drafts=True) for i in pe.all_ids())
            if typ is None or ex["typ"] == typ]


def test_pilot_data_is_loaded():
    exercises = all_exercises()
    assert len(exercises) >= 14
    assert all(ex["ableitung"] in pe.ABLEITUNGEN for ex in exercises)


@pytest.mark.parametrize("ex", all_exercises(), ids=lambda ex: ex["id"])
def test_every_exercise_is_valid_for_its_type(ex):
    # Mathe: „Luna liest, der Code rechnet“ – jede Zeile, Ergebnis, Antwortsatz, Schätzfrage nachgerechnet
    # „Luna liest, der Code rechnet“: jede Zeile, Ergebnis, Antwortsatz, Schätzfrage
    assert pe.validate(ex) == []


@pytest.mark.parametrize("ex", all_exercises("sachaufgabe"), ids=lambda ex: ex["id"])
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


def test_collection_has_unique_ids_and_matching_twins():
    assert pe.check_collection() == []


def test_collection_check_catches_duplicates_and_broken_twins(monkeypatch):
    def check(*exercises):
        monkeypatch.setattr(pe, "_read_sets", lambda: [{"typ": "zuordnen", "datei": "x.json", "status": "entwurf", **e}
                                                       for e in exercises])
        pe._load_all.cache_clear()
        return pe.check_collection()

    try:
        assert check({"id": "a"}, {"id": "a"}) == ["a: doppelt (x.json und x.json)"]
        assert check({"id": "b", "zwilling_von": "weg"}) == ["b: zwilling_von weg gibt es nicht"]
        assert check({"id": "a"}, {"id": "b", "zwilling_von": "a", "typ": "sachaufgabe"}) == \
            ["b: Zwilling muss den Typ des Originals haben (zuordnen)"]
        assert check({"id": "a"}, {"id": "b", "zwilling_von": "a", "status": "freigegeben"}) == \
            ["b: freigegeben, das Original a noch nicht"]
        assert check({"id": "a"}, {"id": "b", "zwilling_von": "a"}) == []
    finally:
        monkeypatch.undo()
        pe._load_all.cache_clear()


def test_reshaped_exercise_gets_its_own_row(monkeypatch):
    base = {"typ": "zuordnen", "status": "freigegeben", "fach": "sub_chemie", "thema": "top_x", "aufgabentext": "…",
            "quelle": {}, "felder": []}
    monkeypatch.setattr(pe, "_load_all", lambda: {
        "c": {**base, "id": "c", "ableitung": "C"},
        "c-z1": {**base, "id": "c-z1", "ableitung": "B", "zwilling_von": "c"}})
    assert [(f["id"], f["zwillinge"]) for f in pe.list_exercises()] == [("c", ["c-z1"])]


def test_validate_catches_wrong_row():
    ex = pe.get_exercise("sa-gummibaerchen")
    broken = {**ex, "zeilen": [[150, 3], [50, 1], [500, 11]]}
    assert any("Zeile 3" in e for e in pe.validate(broken))


@pytest.mark.parametrize("ex", all_exercises("sachaufgabe"), ids=lambda ex: ex["id"])
def test_every_exercise_has_a_checked_reasoning_path(ex):
    # Leichteste Stufe: Gedankengang in Sätzen, mindestens eine nachgerechnete Gleichung
    steps = ex["gedankengang"]
    assert len(steps) >= 3
    assert sum(len(sa.EQUATION.findall(sa.fill_blanks(s["satz"]))) for s in steps) >= 2


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
    errors = pe.validate_header({"quelle": {"material_id": "mat_a"}, "typ": "gibt-es-nicht"})
    assert errors == ["Fach fehlt (fach: sub_…)", "Thema fehlt (thema: top_…)", "Aufgabentext fehlt",
                      "Status fehlt (entwurf oder freigegeben)", "Übungstyp „gibt-es-nicht“ gibt es nicht",
                      "Ableitung fehlt (A, B, C)", "quelle: material_seite fehlt"]


def test_header_checks_twin_link_and_release_date():
    ex = {**pe.get_exercise("ch-brenner"), "zwillinge": []}
    assert pe.validate_header(ex) == []
    assert pe.validate_header({**ex, "freigegeben_am": None}) == ["freigegeben_am fehlt (JJJJ-MM-TT)"]
    assert pe.validate_header({**ex, "ableitung": "B"}) == ["zwilling_von gehört genau zu Zwillingen (B)"]
    assert pe.validate_header({**ex, "ableitung": "C", "zwilling_von": "x"}) == \
        ["zwilling_von gehört genau zu Zwillingen (B)"]


def test_every_exercise_lists_the_stages_of_its_type():
    from backend.app.services import exercise_types
    for fam in pe.list_exercises(include_drafts=True):
        exercise_type = exercise_types.get(fam["typ"])
        assert fam["stufen"] == exercise_type.STAGES and fam["tafel_stufen"] == exercise_type.BOARD_STAGES


def test_drafts_are_only_visible_when_asked_for(monkeypatch):
    exercises = dict(pe._load_all())
    draft = {**exercises["sa-drucker"], "status": "entwurf"}
    monkeypatch.setattr(pe, "_load_all", lambda: {**exercises, "sa-drucker": draft})
    assert "sa-drucker" not in {e["id"] for e in pe.list_exercises()}
    assert pe.get_exercise("sa-drucker") is None
    assert "sa-drucker" in {e["id"] for e in pe.list_exercises(include_drafts=True)}
    assert pe.get_exercise("sa-drucker", include_drafts=True)["status"] == "entwurf"


def test_money_formatting():
    assert sa.fmt_number(8.4, money=True) == "8,40"
    assert sa.fmt_number(10, money=True) == "10"
    assert sa.fmt_number(0.5) == "0,5"


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
