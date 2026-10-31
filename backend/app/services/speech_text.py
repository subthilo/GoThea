"""Text für die Sprachausgabe vorbereiten: Zeichen, die eine Stimme falsch oder englisch liest, als deutsche Wörter.

„7 · 8 = 56“ las die Stimme als „siebenachtsechzig“ (gemessen 31.10. mit scripts/eval_speech.py: Text → Stimme →
zurück in Text). Deshalb gehen Rechenzeichen, Dezimalkomma, Brüche und Einheiten hinter Zahlen ausgeschrieben an
die Stimme; angezeigt wird weiter der Originaltext.
"""
import re

_UNITS = {"g": "Gramm", "kg": "Kilogramm", "mg": "Milligramm", "t": "Tonnen", "l": "Liter", "ml": "Milliliter",
          "hl": "Hektoliter", "cm": "Zentimeter", "mm": "Millimeter", "m": "Meter", "km": "Kilometer",
          "h": "Stunden", "min": "Minuten", "s": "Sekunden", "€": "Euro", "ct": "Cent", "%": "Prozent",
          "°C": "Grad Celsius", "m²": "Quadratmeter", "cm²": "Quadratzentimeter", "m³": "Kubikmeter",
          "cm³": "Kubikzentimeter", "km/h": "Kilometer pro Stunde"}
_DENOM = {2: "Halbe", 3: "Drittel", 4: "Viertel", 5: "Fünftel", 6: "Sechstel", 7: "Siebtel", 8: "Achtel",
          9: "Neuntel", 10: "Zehntel", 12: "Zwölftel", 20: "Zwanzigstel", 100: "Hundertstel", 1000: "Tausendstel"}
_NUM = r"\d+(?:[.\s]\d{3})*(?:,\d+)?"


def _fraction(m: re.Match) -> str:
    z, n = int(m.group(1)), int(m.group(2))
    if n == 2 and z == 1:
        return "ein halb"
    name = _DENOM.get(n)
    return f"{z} {name}" if name else f"{z} durch {n}"


def spoken_german(text: str) -> str:
    t = re.sub(r"(\d+),(\d{2})\s?€", r"\1 Euro \2", text)              # 3,25 € → 3 Euro 25
    # Einheiten hinter Zahlen (längste zuerst, damit „km/h“ nicht als „km“ endet)
    for unit in sorted(_UNITS, key=len, reverse=True):
        t = re.sub(rf"(?<=\d)\s?{re.escape(unit)}(?![\wäöüß²³/])", f" {_UNITS[unit]}", t)
    t = re.sub(r"(?<![\d/])(\d+)\s?/\s?(\d+)(?![\d/])", _fraction, t)   # 3/4 → 3 Viertel
    # 5,579 → 5 Komma 5 7 9 (Nachkommastellen einzeln, wie man sie spricht)
    t = re.sub(r"(\d),(\d+)", lambda m: f"{m.group(1)} Komma {' '.join(m.group(2))}", t)
    t = re.sub(r"\s*[·×]\s*", " mal ", t)
    t = re.sub(rf"(?<=\d)\s*:\s*(?={_NUM})", " geteilt durch ", t)
    t = re.sub(r"\s*=\s*", " gleich ", t)
    t = re.sub(r"\s*≈\s*", " ungefähr ", t)
    t = t.replace("→", " zu ").replace("−", " minus ").replace("+", " plus ")
    t = re.sub(r"(?<=\d) - (?=\d)", " minus ", t)
    return re.sub(r"\s{2,}", " ", t).strip()
