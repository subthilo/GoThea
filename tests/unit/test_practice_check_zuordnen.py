"""Zuordnen auf der Tafel: Luna liest, der Code vergleicht mit den Begriffen aus dem Buch."""
from backend.app.services import practice_check_zuordnen as pz
from backend.app.services import practice_exercises as pe


def brenner():
    return pe.get_exercise("ch-brenner")


def read_all(ex, changes=None):
    changes = changes or {}
    rows = [{"nr": f["nr"], "text": changes.get(f["nr"], f["begriff"])} for f in ex["felder"]]
    return {"zeilen": rows, "unsicher": [], "bereiche": {"2": {"x_pct": 60, "y_pct": 20, "w_pct": 30, "h_pct": 5}}}


def test_all_terms_right_even_with_case_and_spaces():
    ex = brenner()
    out = pz.evaluate(ex, 3, read_all(ex, {1: "  Heißeste   zone ", 4: "brennerrohr."}))
    assert out["status"] == "richtig" and out["probleme"] == []


def test_one_letter_off_counts_but_names_the_spelling():
    ex = brenner()
    out = pz.evaluate(ex, 3, read_all(ex, {8: "Brenerfuß"}))
    assert out["status"] == "richtig"
    assert out["hinweise"] == ["Bei 8 schreibt man „Brennerfuß“."]
    assert "Brennerfuß" in pz.feedback(ex, out, 1)


def test_short_words_need_exact_spelling():
    ex = brenner()
    out = pz.evaluate(ex, 3, read_all(ex, {5: "Duse"}))  # Düse: kurz, keine Toleranz
    assert out["status"] == "noch_nicht"


def test_wrong_and_missing_terms_name_what_was_read():
    ex = brenner()
    out = pz.evaluate(ex, 3, read_all(ex, {2: "Innenkegel", 3: ""}))
    assert out["status"] == "noch_nicht"
    texts = [p["text"] for p in out["probleme"]]
    assert texts == ["Bei 2 lese ich „Innenkegel“. Das passt noch nicht.", "Bei 3 fehlt noch der Begriff."]
    assert pz.feedback(ex, out, 1) == "Bei 2 lese ich „Innenkegel“. Das passt noch nicht. Schau auch noch mal bei 3."
    assert ex["hilfen"]["denkanstoss"] in pz.feedback(ex, out, 2)
    assert "Seite 22" in pz.feedback(ex, out, 3)
    assert pz.marks(read_all(ex), out) == [{"action": "highlight_box",
                                           "coords": {"x_pct": 60, "y_pct": 20, "w_pct": 30, "h_pct": 5}}]


def test_unsure_reading_asks_instead_of_judging():
    ex = brenner()
    read = read_all(ex, {6: "Lufz"})
    read["unsicher"] = [6]
    out = pz.evaluate(ex, 3, read)
    assert out["status"] == "unsicher"
    assert "nicht sicher" in pz.feedback(ex, out, 1) and "„Lufz“" in pz.feedback(ex, out, 1)


def test_board_check_endpoint_uses_the_label_checker(client, monkeypatch):
    from unittest.mock import patch
    from backend.app import config
    monkeypatch.setattr(config, "EXERCISE_TRIAL_ENABLED", True)
    ex = brenner()
    with patch.object(pz.llm, "is_available", return_value=True), \
         patch.object(pz, "read_board", return_value=read_all(ex, {2: "Gashahn"})):
        res = client.post("/api/v1/practice/ch-brenner/check",
                          json={"image_base64": "data:image/jpeg;base64,AAAA", "stage": 3})
    data = res.json()
    assert res.status_code == 200 and data["status"] == "noch_nicht"
    assert data["gelesen"]["2"] == "Gashahn" and "„Gashahn“" in data["text"]
    assert client.post("/api/v1/practice/ch-brenner/check",
                       json={"image_base64": "data:image/jpeg;base64,AAAA", "stage": 2}).status_code == 400
