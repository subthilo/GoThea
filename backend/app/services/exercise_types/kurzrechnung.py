"""Übungstyp „Kurzrechnung“: ein Päckchen kurzer Rechnungen mit einer Zahl oder einem Bruch als Antwort (Mathe).

Aus Theas Fehlern (Mathe-Strategie): Komma und Größenordnung ohne Überschlag, Brüche kürzen ↔ dividieren,
Einheiten. Thea tippt die Antwort über Zahlentasten (keine Ziffernerkennung, Nutzer 24.10.), daneben eine
Nebenrechnung mit Kästchen. Der Code prüft, keine KI.

Daten einer Übung (``aufgaben``, je Aufgabe genau eine Art, ``ergebnis`` = Lösung der Session, wird nachgerechnet):
  {"rechnung": "3,2 : 8", "ergebnis": "0,4"}                          Dezimalzahl (Komma, Tausender mit Leerzeichen)
  {"rechnung": "11/18 : 22/6", "antwort": "bruch", "ergebnis": "1/6"} Bruch, vollständig gekürzt verlangt
  {"vor": "Dividiere durch 3", "zeige": "15/24", "rechnung": "15/24 : 3", "antwort": "bruch",
   "gekuerzt": false, "ergebnis": "5/24"}                              jeder Bruch mit dem richtigen Wert zählt
  {"kuerzen": "15/24", "mit": 3, "ergebnis": "5/8"}                    genau dieser Bruch („mit“: Zahl oder „vollständig“)
  {"umrechnen": "3/4 l", "in": "cm³", "ergebnis": "750"}              Einheiten (Länge, Fläche, Volumen, Masse, Zeit)
Optional je Aufgabe ``nummer`` (wie auf dem Blatt), ``fehler`` (Theas falsche Antwort im Original, zur Doku),
``ueberschlag: false``.

Grundwissen (Ausnahme vom Grundsatz „nie frei erdacht“, Nutzer 24.10.): ``erzeugt`` statt ``aufgaben``.
  "einmaleins"          alle 36 Aufgaben 2·2 … 9·9 ohne Tauschaufgaben, als Check: Zeit still gemessen (erste
                        Antwort), falsch → richtiges Ergebnis gezeigt; Auswertung für die Eltern (sicher / langsam / falsch)
  "einmaleins_wacklig"  (``aus``: ID des Checks) nur die wackligen Aufgaben aus dem letzten Check, normal geübt;
                        eine Aufgabe ist wieder sicher, sobald sie in einem Versuch auf Anhieb und schnell gelang.
                        Ohne wacklige Aufgaben ist die Übung ausgeblendet.

Stufen: -1 Antippen (vier Angebote; falsche = typische Fehler: Komma verschoben, ohne Kehrwert, nicht gekürzt),
1 erst den Überschlag antippen (Größenordnung), dann eintippen, 2 gleich eintippen. Stufe 1 nur, wenn eine
Aufgabe einen Überschlag hat (Malnehmen und Teilen mit Dezimalzahlen); sonst lässt die Übung sie per ``stufen`` weg.
Geprüft im Browser (js/practice_kurzrechnung.js); jede Antwort wird als Ereignis „step“ mit Zeit festgehalten.
"""
from __future__ import annotations

import re
import statistics
from decimal import Decimal, localcontext
from fractions import Fraction
from math import floor, gcd, log10
from typing import Dict, List, Optional, Tuple

from backend.app.services.exercise_types.common import shuffled

TYP = "kurzrechnung"
STAGES = [-1, 1, 2]
BOARD_STAGES: List[int] = []
MAX_AUFGABEN = 20
MAX_NACHKOMMA = 8

# Einmaleins-Check: „langsam“ = mehr als doppelt so lange wie Theas Median im selben Check, mindestens 4 s
LANGSAM_FAKTOR = 2
LANGSAM_MIN_MS = 4000
EINMALEINS = [(a, b) for a in range(2, 10) for b in range(a, 10)]

# --- Rechnen in Theas Schreibweise ------------------------------------------------------------------------

_NUMBER = r"\d{1,3}(?: \d{3})+(?:,\d+)?|\d+(?:,\d+)?"
_TOKEN = re.compile(rf"\s*(?:(?P<frac>(?:{_NUMBER})/(?:{_NUMBER}))|(?P<num>{_NUMBER})|(?P<op>[+\-−·*×:÷])|(?P<par>[()]))")
_OPS = {"+": "+", "-": "-", "−": "-", "·": "*", "*": "*", "×": "*", ":": "/", "÷": "/"}


def number(text: str) -> Fraction:
    """„2 103,976“ → Fraction; „15/24“ → Fraction(15, 24) (ungekürzt geht beim Rechnen verloren, siehe fraction_parts)."""
    text = str(text).strip()
    if "/" in text:
        z, n = text.split("/")
        return Fraction(number(z)) / number(n)
    return Fraction(Decimal(text.replace(" ", "").replace(",", ".")))


def fraction_parts(text: str) -> Tuple[int, int]:
    """„15/24“ → (15, 24), ohne zu kürzen."""
    z, n = str(text).split("/")
    return int(z.strip()), int(n.strip())


def evaluate(expr: str) -> Fraction:
    """Rechnung wie auf dem Blatt: + − · :, Brüche a/b, Klammern; Punkt vor Strich, sonst von links."""
    tokens, pos = [], 0
    expr = expr.strip()
    while pos < len(expr):
        m = _TOKEN.match(expr, pos)
        if not m or m.end() == pos:
            raise ValueError(f"Unbekanntes Zeichen in „{expr}“ bei „{expr[pos:]}“")
        pos = m.end()
        if m.group("frac") or m.group("num"):
            tokens.append(("n", number(m.group("frac") or m.group("num"))))
        elif m.group("op"):
            tokens.append(("op", _OPS[m.group("op")]))
        else:
            tokens.append(("par", m.group("par")))
    value, rest = _sum(tokens)
    if rest:
        raise ValueError(f"Rechnung „{expr}“ ist unvollständig")
    return value


def _sum(tokens):
    value, tokens = _product(tokens)
    while tokens and tokens[0] in (("op", "+"), ("op", "-")):
        op = tokens[0][1]
        right, tokens = _product(tokens[1:])
        value = value + right if op == "+" else value - right
    return value, tokens


def _product(tokens):
    value, tokens = _atom(tokens)
    while tokens and tokens[0] in (("op", "*"), ("op", "/")):
        op = tokens[0][1]
        right, tokens = _atom(tokens[1:])
        if op == "/" and right == 0:
            raise ValueError("Teilen durch 0")
        value = value * right if op == "*" else value / right
    return value, tokens


def _atom(tokens):
    if not tokens:
        raise ValueError("Rechnung endet zu früh")
    kind, val = tokens[0]
    if kind == "n":
        return val, tokens[1:]
    if (kind, val) == ("par", "("):
        value, rest = _sum(tokens[1:])
        if not rest or rest[0] != ("par", ")"):
            raise ValueError("Klammer nicht geschlossen")
        return value, rest[1:]
    raise ValueError("Zahl erwartet")


def is_decimal(value: Fraction) -> bool:
    """Endlicher Dezimalbruch mit höchstens MAX_NACHKOMMA Stellen?"""
    d = value.denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    return d == 1 and (value * 10 ** MAX_NACHKOMMA).denominator == 1


def fmt_decimal(value: Fraction) -> str:
    """Fraction (endlicher Dezimalbruch) → „0,4“, „2103976“; ohne Tausenderpunkte, wie Thea tippt."""
    with localcontext() as ctx:
        ctx.prec = 40
        d = Decimal(value.numerator) / Decimal(value.denominator)
    text = format(d.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",").replace("-", "−")


def fmt_fraction(z: int, n: int) -> str:
    return f"{z}/{n}"


# --- Einheiten (Grundwissen: Umrechnungszahlen) -------------------------------------------------------------

UNITS: Dict[str, Tuple[str, Fraction]] = {}
for _dim, _table in {
    "Länge": {"mm": 1, "cm": 10, "dm": 100, "m": 1000, "km": 1_000_000},
    "Fläche": {"mm²": 1, "cm²": 100, "dm²": 10_000, "m²": 1_000_000, "a": 10 ** 8, "ha": 10 ** 10, "km²": 10 ** 12},
    "Volumen": {"mm³": 1, "cm³": 1000, "ml": 1000, "dm³": 10 ** 6, "l": 10 ** 6, "hl": 10 ** 8, "m³": 10 ** 9},
    "Masse": {"mg": 1, "g": 1000, "kg": 10 ** 6, "t": 10 ** 9},
    "Zeit": {"s": 1, "min": 60, "h": 3600, "d": 86400},
}.items():
    for _u, _f in _table.items():
        UNITS[_u] = (_dim, Fraction(_f))


def convert(amount: str, target: str) -> Fraction:
    """„3/4 l“ in „cm³“ → 750."""
    m = re.fullmatch(r"\s*(.+?)\s*([a-zA-Z²³]+)\s*", amount)
    if not m or m.group(2) not in UNITS:
        raise ValueError(f"Größe „{amount}“ nicht lesbar")
    if target not in UNITS:
        raise ValueError(f"Einheit „{target}“ unbekannt")
    (dim_from, f_from), (dim_to, f_to) = UNITS[m.group(2)], UNITS[target]
    if dim_from != dim_to:
        raise ValueError(f"{m.group(2)} und {target} passen nicht zusammen")
    return number(m.group(1)) * f_from / f_to


# --- Eine Aufgabe: Lösung, Anzeige, Angebote ----------------------------------------------------------------

def _kind(item: dict) -> Optional[str]:
    kinds = [k for k in ("rechnung", "kuerzen", "umrechnen") if k in item]
    return kinds[0] if len(kinds) == 1 else None


def solve(item: dict) -> dict:
    """{antwort: zahl|bruch, wert: Fraction, exakt: (z, n) | None, text: Lösung wie Thea sie schreibt}."""
    kind = _kind(item)
    if kind is None:
        raise ValueError("Genau eine Art angeben: rechnung, kuerzen oder umrechnen")
    if kind == "kuerzen":
        z, n = fraction_parts(item["kuerzen"])
        mit = item.get("mit")
        k = gcd(z, n) if mit == "vollständig" else mit
        if not isinstance(k, int) or k < 2 or z % k or n % k:
            raise ValueError(f"{item['kuerzen']} lässt sich nicht mit {mit} kürzen")
        exact = (z // k, n // k)
        return {"antwort": "bruch", "wert": Fraction(z, n), "exakt": exact, "text": fmt_fraction(*exact)}
    if kind == "umrechnen":
        value = convert(item["umrechnen"], item.get("in", ""))
        if not is_decimal(value):
            raise ValueError(f"{item['umrechnen']} in {item.get('in')} ergibt keine Dezimalzahl")
        return {"antwort": "zahl", "wert": value, "exakt": None, "text": fmt_decimal(value)}
    value = evaluate(item["rechnung"])
    if item.get("antwort", "zahl") == "bruch":
        reduced = (value.numerator, value.denominator)
        if item.get("gekuerzt", True):
            return {"antwort": "bruch", "wert": value, "exakt": reduced, "text": fmt_fraction(*reduced)}
        # jeder Bruch mit diesem Wert zählt; gezeigt wird die Form vom Blatt (15/24 : 3 = 5/24), sonst gekürzt
        shown = str(item.get("ergebnis") or "")
        ok = "/" in shown and fraction_parts(shown)[1] > 0 and Fraction(*fraction_parts(shown)) == value
        return {"antwort": "bruch", "wert": value, "exakt": None, "text": shown if ok else fmt_fraction(*reduced)}
    if not is_decimal(value):
        raise ValueError(f"{item['rechnung']} ergibt keine endliche Dezimalzahl (antwort: bruch?)")
    return {"antwort": "zahl", "wert": value, "exakt": None, "text": fmt_decimal(value)}


def _matches(sol: dict, text: str) -> bool:
    """Passt ein Ergebnis-Text (aus den Daten) zur Lösung? Brüche mit exakt verlangtem Zähler/Nenner genau."""
    if sol["antwort"] == "bruch":
        if "/" not in str(text):
            return False
        parts = fraction_parts(text)
        return parts == sol["exakt"] if sol["exakt"] else Fraction(*parts) == sol["wert"]
    try:
        return number(text) == sol["wert"]
    except (ValueError, ArithmeticError):
        return False


def has_estimate(item: dict, sol: dict) -> bool:
    """Überschlag: bei Malnehmen und Teilen mit Dezimalzahl-Ergebnis (dort geht die Größenordnung verloren)."""
    return (sol["antwort"] == "zahl" and "rechnung" in item and item.get("ueberschlag", True)
            and sol["wert"] != 0 and bool(re.search(r"[·*×:÷]", item["rechnung"])))


def _round_one_digit(value: Fraction) -> Fraction:
    exp = floor(log10(abs(value)))
    step = Fraction(10) ** exp
    return (floor(abs(value) / step + Fraction(1, 2)) * step) or step


def estimate_options(value: Fraction, seed: str) -> dict:
    """Vier Größenordnungen des gerundeten Ergebnisses (≈ 0,04 · 0,4 · 4 · 40), die richtige an fester Zufallsstelle."""
    r = _round_one_digit(value)
    at = shuffled([0, 1, 2, 3], seed)[0]
    options = [fmt_decimal(r * Fraction(10) ** (j - at)) for j in range(4)]
    return {"angebote": options, "richtig": at}


def _shift_options(value: Fraction) -> List[Fraction]:
    ten = Fraction(10)
    return [value, value * ten, value / ten, value / (ten * ten) if abs(value) >= 1 else value * ten * ten]


def choice_options(item: dict, sol: dict, seed: str) -> dict:
    """Stufe -1: Lösung und typische Fehler, gemischt. Brüche als Text „z/n“."""
    if sol["antwort"] == "zahl":
        texts = [fmt_decimal(v) for v in _shift_options(sol["wert"]) if is_decimal(v)]
    else:
        right = sol["exakt"] or fraction_parts(sol["text"])
        wrong: List[Tuple[int, int]] = []
        if "kuerzen" in item:
            z, n = fraction_parts(item["kuerzen"])
            k = n // right[1]
            wrong += [(z // k, n), (z, n // k), (sol["wert"].numerator, sol["wert"].denominator)]
            p = next((p for p in range(2, k + 1) if k % p == 0), k)
            if p < k:
                wrong.append((z // p, n // p))                                # nur halb gekürzt
        else:
            parts = re.split(r"\s*[:÷]\s*", item["rechnung"].strip())
            if len(parts) == 2 and "/" not in parts[0] and "/" not in parts[1]:   # Zahl : Zahl als Bruch
                a, b = int(number(parts[0])), int(number(parts[1]))
                wrong += [(a, b), (b, a)]                                     # nicht gekürzt, vertauscht
            elif len(parts) == 2:
                a, b = number(parts[0]), number(parts[1])
                wrong.append(((a * b).numerator, (a * b).denominator))          # ohne Kehrwert
                if "/" in parts[0] and "/" not in parts[1]:                   # Bruch : Zahl
                    z, n = fraction_parts(parts[0])
                    k = int(b)
                    if z % k == 0 and n % k == 0:
                        wrong.append((z // k, n // k))                        # mit k gekürzt statt geteilt
                    wrong += [(z * k, n), (z, n)]                         # malgenommen, gar nicht gerechnet
            inv = 1 / sol["wert"]
            wrong.append((inv.numerator, inv.denominator))                    # Kehrwert
            if sol["exakt"] and gcd(*right) == 1:
                wrong.append((right[0] * 2, right[1] * 2))                    # nicht fertig gekürzt
        seen, texts = set(), [fmt_fraction(*right)]
        seen.add(right if sol["exakt"] else Fraction(*right))
        for w in wrong:
            key = w if sol["exakt"] else Fraction(*w)
            if w[1] <= 1 or key in seen or (not sol["exakt"] and Fraction(*w) == sol["wert"]):
                continue
            seen.add(key)
            texts.append(fmt_fraction(*w))
    texts = list(dict.fromkeys(texts))[:4]
    order = shuffled(texts, seed)
    return {"angebote": order, "richtig": order.index(texts[0])}


def display(item: dict, sol: dict) -> dict:
    """Was Thea sieht: optional ein Wort davor, die Aufgabe, nach dem Antwortkästchen ggf. die Einheit."""
    if "kuerzen" in item:
        mit = item["mit"]
        return {"vor": "Kürze vollständig" if mit == "vollständig" else f"Kürze mit {mit}", "zeige": item["kuerzen"], "nach": ""}
    if "umrechnen" in item:
        return {"vor": item.get("vor", ""), "zeige": item["umrechnen"], "nach": item["in"]}
    return {"vor": item.get("vor", ""), "zeige": item.get("zeige", item["rechnung"]), "nach": ""}


def _value_hint(item: dict, sol: dict) -> str:
    """Rückmeldung, wenn der Wert stimmt, aber nicht der verlangte Bruch."""
    if "kuerzen" in item and item["mit"] != "vollständig":
        return f"Der Wert stimmt. Kürze genau mit {item['mit']}."
    return "Stimmt. Geht noch weiter."


def prepare_item(item: dict, seed: str, index: int) -> dict:
    sol = solve(item)
    out = {
        "id": item.get("id") or str(index),
        "nummer": item.get("nummer"),
        **display(item, sol),
        "antwort": sol["antwort"],
        "loesung": sol["text"],
        "wert": [str(sol["wert"].numerator), str(sol["wert"].denominator)],
        "exakt": [str(x) for x in sol["exakt"]] if sol["exakt"] else None,
        "hinweis_wert": _value_hint(item, sol),
        "auswahl": choice_options(item, sol, f"{seed}-{index}-auswahl"),
        "ueberschlag": estimate_options(sol["wert"], f"{seed}-{index}-ue") if has_estimate(item, sol) else None,
    }
    return out


# --- Typ-Schnittstelle --------------------------------------------------------------------------------------

GENERATORS = ("einmaleins", "einmaleins_wacklig")


def validate(ex: dict) -> List[str]:
    errors: List[str] = []
    stages = ex.get("stufen", STAGES)
    if ex.get("erzeugt"):
        if ex["erzeugt"] not in GENERATORS:
            return [f"erzeugt: {' oder '.join(GENERATORS)}"]
        if ex.get("aufgaben"):
            errors.append("Erzeugte Übungen haben keine eigenen aufgaben")
        if stages != [2]:
            errors.append("Einmaleins: nur Stufe 2 (stufen: [2])")
        if ex["erzeugt"] == "einmaleins_wacklig" and not ex.get("aus"):
            errors.append("einmaleins_wacklig braucht aus (ID des Checks)")
        return errors
    items = ex.get("aufgaben") or []
    if not items:
        return ["Keine aufgaben"]
    if len(items) > MAX_AUFGABEN:
        errors.append(f"Höchstens {MAX_AUFGABEN} Aufgaben je Übung")
    any_estimate = False
    for i, item in enumerate(items, start=1):
        label = f"Aufgabe {item.get('nummer') or i}"
        try:
            sol = solve(item)
        except (ValueError, ZeroDivisionError, KeyError, ArithmeticError) as e:
            errors.append(f"{label}: {e}")
            continue
        if "ergebnis" not in item:
            errors.append(f"{label}: ergebnis fehlt (Lösung {sol['text']})")
        elif not _matches(sol, item["ergebnis"]):
            errors.append(f"{label}: ergebnis {item['ergebnis']} stimmt nicht, richtig ist {sol['text']}")
        if item.get("fehler") is not None and _matches(sol, str(item["fehler"])):
            errors.append(f"{label}: fehler {item['fehler']} ist gar nicht falsch")
        if len(choice_options(item, sol, "pruefen")["angebote"]) < 3:
            errors.append(f"{label}: zu wenige Angebote zum Antippen")
        any_estimate = any_estimate or has_estimate(item, sol)
    if 1 in stages and not any_estimate:
        errors.append("Stufe 1 braucht eine Aufgabe mit Überschlag (sonst stufen: [-1, 2])")
    return errors


def _einmaleins_items(seed: str, keys: Optional[List[str]] = None) -> List[dict]:
    """Einmaleins als Aufgaben; die Reihenfolge der Faktoren bei jeder Aufgabe fest gemischt."""
    items = []
    for a, b in EINMALEINS:
        key = f"{a}·{b}"
        if keys is not None and key not in keys:
            continue
        x, y = shuffled([a, b], f"{seed}-{key}")
        items.append({"id": key, "rechnung": f"{x} · {y}", "ergebnis": str(a * b), "ueberschlag": False})
    return shuffled(items, f"{seed}-reihenfolge")


def prepare(ex: dict) -> dict:
    if ex.get("erzeugt") == "einmaleins":
        items = _einmaleins_items(ex["id"])
    elif ex.get("erzeugt") == "einmaleins_wacklig":
        items = []  # personalize() setzt die wackligen Aufgaben aus der Datenbank ein
    else:
        items = ex["aufgaben"]
    return {"liste": [prepare_item(item, ex["id"], i) for i, item in enumerate(items, start=1)],
            "check": ex.get("erzeugt") == "einmaleins"}


def summary(ex: dict) -> dict:
    return {}


# --- Einmaleins: Auswertung aus den Versuchen ---------------------------------------------------------------

def _key(text: str) -> Optional[str]:
    """„7 · 8“ oder „8·7“ → „7·8“ (kleinerer Faktor zuerst), sonst None."""
    m = re.fullmatch(r"\s*(\d)\s*·\s*(\d)\s*", str(text))
    if not m:
        return None
    a, b = sorted((int(m.group(1)), int(m.group(2))))
    return f"{a}·{b}"


def evaluate_check(check_steps: List[dict], practice: List[List[dict]]) -> dict:
    """check_steps: Antworten des letzten vollständigen Checks ({aufgabe, antwort, richtig, ms}).
    practice: je späterem Übungsversuch die Antworten in Reihenfolge (auch Fehlversuche).
    Ergebnis: Zellen mit sicher/langsam/falsch, Median, Grenze und was noch wacklig ist."""
    cells: Dict[str, dict] = {}
    for st in check_steps:
        key = _key(st.get("aufgabe", ""))
        if key and key not in cells:
            cells[key] = {"antwort": st.get("antwort"), "richtig": bool(st.get("richtig")), "ms": int(st.get("ms") or 0)}
    times = [c["ms"] for c in cells.values() if c["richtig"] and c["ms"] > 0]
    median = int(statistics.median(times)) if times else 0
    limit = max(LANGSAM_FAKTOR * median, LANGSAM_MIN_MS)
    for c in cells.values():
        c["status"] = "falsch" if not c["richtig"] else "langsam" if c["ms"] > limit else "sicher"
    wobbly = {k for k, c in cells.items() if c["status"] != "sicher"}
    cleared: Dict[str, int] = {}
    for steps in practice:
        first: Dict[str, dict] = {}
        for st in steps:
            key = _key(st.get("aufgabe", ""))
            if key and key not in first:
                first[key] = st
        for key, st in first.items():
            if key in wobbly and st.get("richtig") and int(st.get("ms") or 0) <= limit:
                cleared[key] = cleared.get(key, 0) + 1
    still = sorted((k for k in wobbly if not cleared.get(k)), key=lambda k: tuple(map(int, k.split("·"))))
    return {"zellen": cells, "median_ms": median, "grenze_ms": limit, "wacklig": still,
            "anzahl": len(cells), "geuebt": cleared}


def _steps(attempt) -> List[dict]:
    import json
    return [json.loads(ev.data_json) for ev in sorted(attempt.events, key=lambda e: e.created_at)
            if ev.kind == "step" and ev.data_json]


def check_result(db, check_id: str, wobbly_id: Optional[str] = None) -> Optional[dict]:
    """Letzter vollständiger Einmaleins-Check (gelöst) samt späteren Übungsversuchen der wackligen Aufgaben."""
    from backend.app.models.practice_attempt import PracticeAttempt
    check = (db.query(PracticeAttempt)
             .filter(PracticeAttempt.exercise_id == check_id, PracticeAttempt.solved_at.isnot(None))
             .order_by(PracticeAttempt.solved_at.desc()).first())
    if check is None:
        return None
    practice = []
    if wobbly_id:
        later = (db.query(PracticeAttempt)
                 .filter(PracticeAttempt.exercise_id == wobbly_id, PracticeAttempt.started_at >= check.solved_at)
                 .order_by(PracticeAttempt.started_at).all())
        practice = [_steps(a) for a in later]
    return {"datum": check.solved_at.isoformat(), **evaluate_check(_steps(check), practice)}


def _wobbly_id_for(check_id: str) -> Optional[str]:
    from backend.app.services import practice_exercises
    return next((i for i in practice_exercises.all_ids()
                 if (practice_exercises.get_exercise(i, include_drafts=True) or {}).get("aus") == check_id), None)


def personalize(ex: dict, db) -> dict:
    """Wacklige Einmaleins-Aufgaben aus der Datenbank einsetzen (nur für einmaleins_wacklig)."""
    if ex.get("erzeugt") != "einmaleins_wacklig":
        return ex
    result = check_result(db, ex["aus"], ex["id"])
    keys = result["wacklig"] if result else []
    items = _einmaleins_items(ex["id"], keys)
    return {**ex, "liste": [prepare_item(item, ex["id"], i) for i, item in enumerate(items, start=1)],
            "grenze_ms": result["grenze_ms"] if result else None}


def hidden(ex: dict, db) -> bool:
    """Wacklige Aufgaben üben: nur, wenn es nach dem letzten Check welche gibt."""
    if ex.get("erzeugt") != "einmaleins_wacklig":
        return False
    result = check_result(db, ex["aus"], ex["id"])
    return not (result and result["wacklig"])


def auswertung(ex: dict, db) -> Optional[dict]:
    """Für die Eltern: Ergebnis des letzten Einmaleins-Checks (nur beim Check selbst)."""
    if ex.get("erzeugt") != "einmaleins":
        return None
    return check_result(db, ex["id"], _wobbly_id_for(ex["id"]))
