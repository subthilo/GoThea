"""Text für die Sprachausgabe (services/speech_text.py): Zeichen, die die Stimme falsch las, als deutsche Wörter."""
import pytest

from backend.app.services.speech_text import spoken_german


@pytest.mark.parametrize("text, spoken", [
    ("Du hast 7 · 8 = 56 richtig gerechnet.", "Du hast 7 mal 8 gleich 56 richtig gerechnet."),  # las „siebenachtsechzig“
    ("3,2 : 8 ist 0,4", "3 Komma 2 geteilt durch 8 ist 0 Komma 4"),
    ("83,4 − 5,579 ≈ 78", "83 Komma 4 minus 5 Komma 5 7 9 ungefähr 78"),
    ("500 g kosten 3,25 €, 10 € reichen", "500 Gramm kosten 3 Euro 25, 10 Euro reichen"),
    ("3/4 von 12 m, 1/2 l, 5/13", "3 Viertel von 12 Meter, ein halb Liter, 5 durch 13"),
    ("50 km/h und 25 %", "50 Kilometer pro Stunde und 25 Prozent"),
])
def test_signs_units_and_decimals_are_spoken_as_words(text, spoken):
    assert spoken_german(text) == spoken


def test_plain_sentences_stay_as_they_are():
    text = "Tippe auf den Haken: dann geht es weiter. Wie viele Gramm sind es – mehr oder weniger?"
    assert spoken_german(text) == text
