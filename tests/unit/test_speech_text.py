"""Text für die Sprachausgabe (services/speech_text.py): Zeichen, die die Stimme falsch las, als deutsche Wörter."""
import pytest

from backend.app.services.speech_text import number_words, spoken_german


@pytest.mark.parametrize("text, spoken", [
    ("Du hast 7 · 8 = 56 richtig gerechnet.", "Du hast sieben mal acht gleich sechsundfünfzig richtig gerechnet."),
    ("3,2 : 8 ist 0,4", "drei Komma zwei geteilt durch acht ist null Komma vier"),
    ("83,4 − 5,579 ≈ 78", "dreiundachtzig Komma vier minus fünf Komma fünf sieben neun ungefähr achtundsiebzig"),
    ("500 g kosten 3,25 €, 10 € reichen", "fünfhundert Gramm kosten drei Euro fünfundzwanzig, zehn Euro reichen"),
    ("3/4 von 12 m, 1/2 l, 5/13", "drei Viertel von zwölf Meter, ein halb Liter, fünf durch dreizehn"),
    ("50 km/h und 25 %", "fünfzig Kilometer pro Stunde und fünfundzwanzig Prozent"),
    ("· 3", "mal drei"),  # einzeln las die Stimme „malt three“
    ("1.500 g", "tausendfünfhundert Gramm"),
    ("Schau z. B. auf S. 22, Nr. 3", "Schau zum Beispiel auf Seite zweiundzwanzig, Nummer drei"),
    # Physik (7.11.): Kraft-Einheiten, auch ohne Zahl davor, und „≙“ wie im Unterricht
    ("1 N geteilt durch 2 cm ist 0,5 N/cm.", "Ein Newton geteilt durch zwei Zentimeter ist null Komma fünf Newton pro Zentimeter."),
    ("Also N/kg, 3 kN.", "Also Newton pro Kilogramm, drei Kilonewton."),
    ("100 g ≙ 1 N", "hundert Gramm entspricht einem Newton"),
])
def test_signs_units_and_decimals_are_spoken_as_words(text, spoken):
    assert spoken_german(text) == spoken


@pytest.mark.parametrize("text, spoken", [
    ("3 € geteilt durch 3 ist 1 €.", "drei Euro geteilt durch drei ist ein Euro."),  # sprach „eins Euro“
    ("Von 1 Minute auf 12 Minuten.", "Von einer Minute auf zwölf Minuten."),
    ("In 1 h schafft 1 Person 21 h nicht.", "In einer Stunde schafft eine Person einundzwanzig Stunden nicht."),
    ("Er bräuchte 1 Helfer, mit 1 Helfer.", "Er bräuchte einen Helfer, mit einem Helfer."),
    ("Genau. 1 Helfer reicht.", "Genau. Ein Helfer reicht."),
    ("Die 1 Minute, mit 1-Liter-Flaschen.", "Die eine Minute, mit Ein-Liter-Flaschen."),
    ("1 mal 10 ist 10, 1,5 h, 0,1 l", "eins mal zehn ist zehn, eins Komma fünf Stunden, null Komma eins Liter"),
])
def test_one_before_a_noun_gets_gender_and_case(text, spoken):
    assert spoken_german(text) == spoken


@pytest.mark.parametrize("n, word", [(0, "null"), (1, "eins"), (17, "siebzehn"), (21, "einundzwanzig"),
                                     (101, "hunderteins"), (150, "hundertfünfzig"), (2100, "zweitausendhundert"),
                                     (21000, "einundzwanzigtausend"), (1500000, "eine Million fünfhunderttausend")])
def test_number_words(n, word):
    assert number_words(n) == word


def test_plain_sentences_stay_as_they_are():
    text = "Tippe auf den Haken: dann geht es weiter. Wie viele Gramm sind es – mehr oder weniger?"
    assert spoken_german(text) == text
