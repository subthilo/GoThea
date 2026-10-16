"""Lückentext-Normalisierung (genutzt von der Tafel-Aufgabe des alten Tutors)."""


def test_cloze_fachbegriff_placeholder_removal(client):
    from backend.app.services.tutor_service import normalize_cloze_content
    raw_content = {
        "text": "In einem Bruch steht oben der [[1: Fachbegriff]] und unten der [[2: Fachbegriff]].",
        "blanks": [
            {"id": 1, "expected_answer": "Zähler"},
            {"id": 2, "expected_answer": "Nenner"}
        ],
        "word_bank": ["Zähler", "Nenner", "Fachbegriff"]
    }
    norm = normalize_cloze_content(raw_content, generate_sentence_audio=False)
    assert len(norm["sentences"]) == 1
    s = norm["sentences"][0]
    assert s["text_with_blanks"] == "In einem Bruch steht oben der [blank_1] und unten der [blank_2]."
    assert s["full_text_solved"] == "In einem Bruch steht oben der Zähler und unten der Nenner."
    assert "Fachbegriff" not in s["full_text_solved"]
    assert "Fachbegriff" not in norm["word_bank"]
