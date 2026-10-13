import pytest
from backend.app.services.tutor_service import clean_text_for_speech


def test_clean_text_for_speech_roots():
    assert "Wurzel aus 16" in clean_text_for_speech("Berechne \\sqrt{16}.")
    assert "Wurzel aus 25" in clean_text_for_speech("Berechne √25.")
    assert "Wurzel aus 9" in clean_text_for_speech("Berechne sqrt(9).")
    assert "dritte Wurzel aus 8" in clean_text_for_speech("Die \\sqrt[3]{8} ist 2.")
    assert "Wurzel aus 4" in clean_text_for_speech("Root aus 4")


def test_clean_text_for_speech_math_operators():
    # Multiplikation
    res_mult = clean_text_for_speech("A = g \\cdot h")
    assert "mal" in res_mult
    assert "ist gleich" in res_mult

    res_cross = clean_text_for_speech("g × h")
    assert "g mal h" in res_cross

    res_star = clean_text_for_speech("2 * r * \\pi")
    assert "2 mal r mal Pi" in res_star

    # Division
    res_div = clean_text_for_speech("v = s / t")
    assert "v ist gleich s geteilt durch t" in res_div

    res_colon = clean_text_for_speech("12 : 3 = 4")
    assert "12 geteilt durch 3 ist gleich 4" in res_colon

    res_div_sym = clean_text_for_speech("10 ÷ 2")
    assert "10 geteilt durch 2" in res_div_sym


def test_clean_text_for_speech_units_and_powers():
    res_units = clean_text_for_speech("100 cm² entsprechen 1 dm².")
    assert "100 Quadratzentimeter entsprechen 1 Quadratdezimeter" in res_units

    res_speed = clean_text_for_speech("50 km/h und 10 m/s")
    assert "Kilometer pro Stunde" in res_speed
    assert "Meter pro Sekunde" in res_speed

    res_power = clean_text_for_speech("x² + 5x = 0")
    assert "x hoch zwei + 5x ist gleich 0" in res_power


def test_clean_text_for_speech_fractions():
    res_half = clean_text_for_speech("\\frac{1}{2}")
    assert "ein Halb" in res_half

    res_quarter = clean_text_for_speech("\\frac{3}{4}")
    assert "drei Viertel" in res_quarter

    res_general = clean_text_for_speech("\\frac{a}{b}")
    assert "a geteilt durch b" in res_general


def test_clean_text_for_speech_comparisons_and_greek():
    res = clean_text_for_speech("v ≈ 3,5 m/s und a ≠ 0")
    assert "ungefähr gleich" in res
    assert "ungleich" in res
    assert "Meter pro Sekunde" in res

    res_greek = clean_text_for_speech("Winkel \\alpha und \\beta")
    assert "Alpha" in res_greek
    assert "Beta" in res_greek


def test_clean_text_for_speech_english():
    res = clean_text_for_speech("\\sqrt{16} = 4", lang="en")
    assert "square root of 16" in res
    assert "equals" in res
