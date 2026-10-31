"""Text für die Sprachausgabe vorbereiten: Zeichen, die eine Stimme falsch oder englisch liest, als deutsche Wörter.

„7 · 8 = 56“ las die Stimme als „siebenachtsechzig“ (gemessen 31.10. mit scripts/eval_speech.py: Text → Stimme →
zurück in Text). Deshalb gehen Rechenzeichen, Dezimalkomma, Brüche und Einheiten hinter Zahlen ausgeschrieben an
die Stimme; angezeigt wird weiter der Originaltext.

Zahlen gehen als Wörter an die Stimme: kurze Schnipsel wie das Antwort-Kärtchen „· 3“ las sie sonst englisch
(„malt three“, whisper erkannte 13 von 280 Erklär-Sätzen als Englisch, 31.10.). Die „1“ vor einem Nomen wird zu
„ein/eine/einem/einen“, je nach Geschlecht (Liste unten) und Fall (Präposition oder Verb davor) – sonst sprach
die Stimme „eins Euro“.
"""
import re

_UNITS = {"g": "Gramm", "kg": "Kilogramm", "mg": "Milligramm", "t": "Tonnen", "l": "Liter", "ml": "Milliliter",
          "hl": "Hektoliter", "cm": "Zentimeter", "mm": "Millimeter", "m": "Meter", "km": "Kilometer",
          "h": "Stunden", "min": "Minuten", "s": "Sekunden", "€": "Euro", "ct": "Cent", "%": "Prozent",
          "°C": "Grad Celsius", "m²": "Quadratmeter", "cm²": "Quadratzentimeter", "m³": "Kubikmeter",
          "cm³": "Kubikzentimeter", "km/h": "Kilometer pro Stunde"}
_SINGULAR = {"Tonnen": "Tonne", "Stunden": "Stunde", "Minuten": "Minute", "Sekunden": "Sekunde"}
_DENOM = {2: "Halbe", 3: "Drittel", 4: "Viertel", 5: "Fünftel", 6: "Sechstel", 7: "Siebtel", 8: "Achtel",
          9: "Neuntel", 10: "Zehntel", 12: "Zwölftel", 20: "Zwanzigstel", 100: "Hundertstel", 1000: "Tausendstel"}
_NUM = r"\d+(?:[.\s]\d{3})*(?:,\d+)?"

# Geschlecht der Nomen, die hinter einer „1“ vorkommen (Einheiten und Wörter aus den Übungen). Fehlt ein Nomen,
# wird es „ein“ (richtig für männlich/sächlich im Nominativ); tests/unit/test_practice_help.py meldet es.
_GENDER = {
    "m": "Euro Cent Liter Milliliter Hektoliter Meter Zentimeter Millimeter Kilometer Quadratmeter Kubikmeter "
         "Quadratzentimeter Kubikzentimeter Helfer Arbeiter Drucker Tag Monat Schritt Teil Punkt Kasten Karton "
         "Becher Eimer Apfel Bus Wagen Fahrer Schüler Freund Mensch Euroschein Behälter Kanister Sack Löffel",
    "f": "Stunde Minute Sekunde Tonne Person Flasche Packung Tüte Woche Pumpe Maschine Seite Kiste Dose Tafel "
         "Portion Runde Fahrt Schülerin Rolle Münze Stufe Zahl Reihe Strecke Schachtel Kugel Fahrkarte",
    "n": "Gramm Kilogramm Milligramm Prozent Grad Stück Jahr Kind Glas Paket Taxi Flugzeug Brot Ei Blatt "
         "Viertel Drittel Fünftel Sechstel Achtel Zehntel Hundertstel Tausendstel Päckchen Bild Heft Buch",
}
_GENDER_OF = {w: g for g, words in _GENDER.items() for w in words.split()}
_DATIVE = {"mit", "von", "vom", "in", "bei", "nach", "aus", "zu", "seit", "ab"}
_ACCUSATIVE = {"für", "durch", "ohne", "um", "gegen", "auf"}
_ACC_VERBS = {"braucht", "brauchen", "bräuchte", "bräuchten", "kostet", "kosten", "hat", "haben", "gibt",
              "bekommt", "bekommen", "kauft", "kaufen", "zahlt", "zahlen", "nimmt", "nehmen", "schafft",
              "schaffen", "füllt", "füllen", "druckt", "drucken"}
_ARTICLE = {"der": "eine", "die": "eine", "das": "eine", "den": "einen", "dem": "einen", "des": "einen"}
_ENDING = {"dat": {"m": "einem", "f": "einer", "n": "einem"},
           "acc": {"m": "einen", "f": "eine", "n": "ein"},
           "nom": {"m": "ein", "f": "eine", "n": "ein"}}

_ABBREVIATIONS = {"z. B.": "zum Beispiel", "S.": "Seite", "Nr.": "Nummer", "Abb.": "Abbildung", "usw.": "und so weiter"}

_ONES = ["null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn", "elf",
         "zwölf", "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn"]
_TENS = ["", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig", "neunzig"]


def _below_thousand(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    word = ("hundert" if hundreds == 1 else _ONES[hundreds] + "hundert") if hundreds else ""
    if rest < 20:
        return word + (_ONES[rest] if rest else "")
    ones, tens = rest % 10, rest // 10
    return word + (("ein" if ones == 1 else _ONES[ones]) + "und" if ones else "") + _TENS[tens]


def _prefix(n: int) -> str:
    """Zahl vor „tausend“: „einundzwanzigtausend“, „hunderteintausend“."""
    word = _below_thousand(n)
    return word[:-1] if word.endswith("eins") else word


def number_words(n: int) -> str:
    """Ganze Zahl als deutsches Wort: 2100 → „zweitausendeinhundert“, 1 → „eins“."""
    if n == 0:
        return "null"
    millions, rest = divmod(n, 1_000_000)
    thousands, rest = divmod(rest, 1000)
    parts = []
    if millions:
        parts.append("eine Million" if millions == 1 else f"{_prefix(millions)} Millionen")
    word = ("tausend" if thousands == 1 else _prefix(thousands) + "tausend") if thousands else ""
    if rest:
        word += _below_thousand(rest)
    if word:
        parts.append(word)
    return " ".join(parts)


def _fraction(m: re.Match) -> str:
    z, n = int(m.group(1)), int(m.group(2))
    if n == 2 and z == 1:
        return "ein halb"
    name = _DENOM.get(n)
    return f"{z} {name}" if name else f"{z} durch {n}"


def _unit(m: re.Match, unit: str) -> str:
    name = _UNITS[unit]
    before = m.string[m.start() - 1] if m.start() else ""
    if m.group(1) == "1" and not (before.isdigit() or before == ","):
        name = _SINGULAR.get(name, name)
    return f"{m.group(1)} {name}"


def _one(m: re.Match) -> str:
    """„1“ vor einem Nomen → „ein/eine/einem/einen“ nach Geschlecht und Fall."""
    prev, space, noun = m.group("prev") or "", m.group("space") or "", m.group("noun")
    word = prev.lower().rstrip(",;")
    gender = _GENDER_OF.get(noun, "m")
    if word in _ARTICLE:
        one = _ARTICLE[word]
    else:
        case = "dat" if word in _DATIVE else "acc" if word in _ACCUSATIVE or word in _ACC_VERBS else "nom"
        one = _ENDING[case][gender]
    if not prev or prev[-1] in ".!?":
        one = one.capitalize()
    return f"{prev}{space}{one} {noun}"


def spoken_german(text: str) -> str:
    t = text
    for short, long in _ABBREVIATIONS.items():
        t = re.sub(rf"(?<![\wäöüß]){re.escape(short)}", long, t)
    t = re.sub(r"(?<=\d)\.(?=\d{3}(?!\d))", "", t)                     # 1.500 → 1500
    t = re.sub(r"(\d+),(\d{2})\s?€", r"\1 Euro \2", t)                  # 3,25 € → 3 Euro 25
    # Einheiten hinter Zahlen (längste zuerst, damit „km/h“ nicht als „km“ endet); „1 h“ → „1 Stunde“
    for unit in sorted(_UNITS, key=len, reverse=True):
        t = re.sub(rf"(\d)\s?{re.escape(unit)}(?![\wäöüß²³/])", lambda m, u=unit: _unit(m, u), t)
    t = re.sub(r"(?<![\d/])(\d+)\s?/\s?(\d+)(?![\d/])", _fraction, t)   # 3/4 → 3 Viertel
    t = re.sub(r"(?<![\d,])\b1-(?=[A-ZÄÖÜ])", "Ein-", t)                 # 1-Liter-Flaschen
    # 1 Helfer → ein Helfer, von 1 Minute → von einer Minute
    t = re.sub(r"(?:(?P<prev>\S+)(?P<space>\s+))?(?<![\d,])\b1\s+(?P<noun>[A-ZÄÖÜ][\wäöüß]*)", _one, t)
    # 5,579 → 5 Komma 5 7 9 (Nachkommastellen einzeln, wie man sie spricht)
    t = re.sub(r"(\d),(\d+)", lambda m: f"{m.group(1)} Komma {' '.join(m.group(2))}", t)
    t = re.sub(r"\s*[·×]\s*", " mal ", t)
    t = re.sub(rf"(?<=\d)\s*:\s*(?={_NUM})", " geteilt durch ", t)
    t = re.sub(r"\s*=\s*", " gleich ", t)
    t = re.sub(r"\s*≈\s*", " ungefähr ", t)
    t = t.replace("→", " zu ").replace("−", " minus ").replace("+", " plus ")
    t = re.sub(r"(?<=\d) - (?=\d)", " minus ", t)
    t = re.sub(r"\d+", lambda m: number_words(int(m.group(0))), t)
    return re.sub(r"\s{2,}", " ", t).strip()
