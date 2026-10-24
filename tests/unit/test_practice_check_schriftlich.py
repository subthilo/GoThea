"""Schriftlich rechnen, Stufe 5 auf der Tafel: Luna liest, der Code rechnet nach (services/practice_check_schriftlich.py)."""
from backend.app.services import practice_check_schriftlich as check
from backend.app.services.practice_check import NOCH_NICHT, RICHTIG, UNSICHER

MUL = {"id": "t", "verfahren": "multiplikation", "aufgabe": "243 · 12",
       "nachschlagen": {"stelle": "3. Die schriftliche Multiplikation"}}
ADD = {"id": "t", "verfahren": "addition", "aufgabe": "18,45 + 59,75"}


def test_expected_rows_follow_the_written_sum():
    assert check.expected_rows(MUL) == ["243·12", "2430", "+486", "2916"]
    assert check.expected_rows(ADD) == ["18,45", "+59,75", "78,20"]


def test_right_result_is_enough_and_trailing_zeros_do_not_matter():
    out = check.evaluate(ADD, 5, {"zeilen": ["18,45", "+59,75", "78,2"], "ergebnis": "78,2", "unsicher": False})
    assert out["status"] == RICHTIG
    assert check.feedback(ADD, out, 1) == "Richtig gerechnet!"


def test_wrong_result_names_the_first_wrong_line_with_what_luna_read():
    read = {"zeilen": ["243·12", "243", "+486", "729"], "ergebnis": "729", "unsicher": False,
            "bereiche": [{"x_pct": 1, "y_pct": 1, "w_pct": 5, "h_pct": 5}, {"x_pct": 2, "y_pct": 10, "w_pct": 5, "h_pct": 5}]}
    out = check.evaluate(MUL, 5, read)
    assert out["status"] == NOCH_NICHT
    assert out["probleme"][0]["bereich"] == "2" and "„243“" in out["probleme"][0]["text"]
    assert "2916" not in check.feedback(MUL, out, 1)  # verrät die Lösung nicht
    assert "Merkblatt" in check.feedback(MUL, out, 2)
    assert check.marks(read, out) == [{"action": "highlight_box", "coords": {"x_pct": 2, "y_pct": 10, "w_pct": 5, "h_pct": 5}}]
    assert check.describe_read(read, MUL)["ergebnis"] == "729"


def test_unsure_reading_asks_instead_of_judging():
    out = check.evaluate(MUL, 5, {"zeilen": ["243·12", "2430", "+486", "29?6"], "ergebnis": "29?6", "unsicher": True})
    assert out["status"] == UNSICHER
    assert "deutlicher" in check.feedback(MUL, out, 1)


def test_missing_result_is_named():
    out = check.evaluate(MUL, 5, {"zeilen": ["243·12"], "ergebnis": "", "unsicher": False})
    assert out["status"] == NOCH_NICHT and out["probleme"][0]["bereich"] == "ergebnis"
