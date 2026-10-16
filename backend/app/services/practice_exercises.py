"""Übungen aus echten Aufgaben (Konzept-Doc, Tab „Mathe – Aufgabentypen“).

Jede Übung geht auf eine Aufgabe aus Theas Materialien zurück (A Original, B Zwilling). Die Daten
entstehen in Claude-Code-Sessions und liegen als JSON in ``backend/app/exercise_sets/``.
Grundsatz „Luna liest, der Code rechnet“: ``validate`` rechnet jede Lösung exakt nach,
``building_blocks`` erzeugt die Bausteine für Stufe 0 (Tabelle per Antippen/Ziehen füllen).
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

EXERCISE_SETS_DIR = Path(__file__).resolve().parent.parent / "exercise_sets"


def _num(x) -> Fraction:
    return Fraction(str(x).replace(",", "."))


def fmt_number(x, money: bool = False) -> str:
    """Zahl in deutscher Schreibweise; Geldbeträge mit zwei Nachkommastellen, wenn nicht ganz."""
    value = _num(x)
    if value.denominator == 1:
        return str(value.numerator)
    if money:
        return f"{float(value):.2f}".replace(".", ",")
    return f"{float(value):g}".replace(".", ",")


def _apply(op: str, value: Fraction) -> Fraction:
    factor = _num(op[1:])
    return value / factor if op[0] == ":" else value * factor


def _inverse(op: str) -> str:
    return ("·" if op[0] == ":" else ":") + op[1:]


def right_ops(ex: dict) -> List[str]:
    """Rechenschritte der rechten Spalte: beim antiproportionalen Dreisatz jeweils umgekehrt."""
    anti = ex["schema"] == "dreisatz_antiproportional"
    return [_inverse(op) if anti else op for op in ex["schritte"]]


def is_money_column(ex: dict) -> bool:
    return ex["schema"].startswith("dreisatz") and ex["groessen"][1]["einheit"] == "€"


# --- Prüfung der Daten -------------------------------------------------------------------------


def validate(ex: dict) -> List[str]:
    """Fehlerliste einer Übung (leer = alles nachgerechnet und stimmig)."""
    errors: List[str] = []
    result = _num(ex["ergebnis"]["wert"])
    if ex["schema"] == "rechnung":
        a, b = (_num(z) for z in ex["rechnung"]["zahlen"])
        if a / b != result:
            errors.append(f"{a} : {b} ergibt {a / b}, nicht {result}")
        left, right = (_num(t) for t in ex["rechnung"]["umformung"].split(":"))
        if left / right != a / b or right.denominator != 1:
            errors.append("Umformung (Komma verschieben) stimmt nicht")
    else:
        rows = [(_num(x), _num(y)) for x, y in ex["zeilen"]]
        for i, (op_l, op_r) in enumerate(zip(ex["schritte"], right_ops(ex))):
            (x0, y0), (x1, y1) = rows[i], rows[i + 1]
            if _apply(op_l, x0) != x1:
                errors.append(f"Zeile {i + 2} links: {x0} {op_l} ergibt nicht {x1}")
            if _apply(op_r, y0) != y1:
                errors.append(f"Zeile {i + 2} rechts: {y0} {op_r} ergibt nicht {y1}")
        anti = ex["schema"] == "dreisatz_antiproportional"
        if len({x * y if anti else y / x for x, y in rows}) != 1:
            errors.append("Zeilen gehören nicht zu einer Zuordnung")
        if rows[-1][1] != result:
            errors.append("letzte Zeile ist nicht das Ergebnis")

    numbers = re.findall(r"\d[\d.]*(?:,\d+)?", ex["antwortsatz"])
    if not numbers or _num(numbers[-1].replace(".", "")) != result:
        errors.append("Zahl im Antwortsatz ist nicht das Ergebnis")
    unit = ex["ergebnis"]["einheit"]
    if unit and unit not in ex["antwortsatz"]:
        errors.append(f"Einheit „{unit}“ fehlt im Antwortsatz")
    if not ex["antwortsatz"].startswith(ex["antwort_anfang"]):
        errors.append("Antwortsatz beginnt nicht mit antwort_anfang")

    guess = ex["schaetzfrage"]
    ref = _num(guess["vergleichswert"])
    if result == ref or (result > ref) != (guess["ergebnis_ist"] == "groesser"):
        errors.append("Schätzfrage passt nicht zum Ergebnis")
    if guess["antwort"] not in guess["optionen"]:
        errors.append("Antwort der Schätzfrage fehlt in den Optionen")
    if _num(ex["fehlerbeispiel"]["wert"]) == result:
        errors.append("Fehlerbeispiel ist gleich dem Ergebnis")
    return errors


# --- Laden ---------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_all() -> Dict[str, dict]:
    exercises: Dict[str, dict] = {}
    for path in sorted(EXERCISE_SETS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for ex in data["uebungen"]:
            exercises[ex["id"]] = {**ex, "typ": data["typ"]}
    return exercises


def list_exercises() -> List[dict]:
    """Kurzfassung für die Liste: Originale mit ihren Zwillingen."""
    all_ex = _load_all()
    twins: Dict[str, List[str]] = {}
    for ex in all_ex.values():
        if ex.get("zwilling_von"):
            twins.setdefault(ex["zwilling_von"], []).append(ex["id"])
    return [
        {
            "id": ex["id"],
            "typ": ex["typ"],
            "aufgabentext": ex["aufgabentext"],
            "abschnitt": ex["abschnitt"],
            "quelle": ex["quelle"],
            "schema": ex["schema"],
            "zwillinge": twins.get(ex["id"], []),
        }
        for ex in all_ex.values() if ex["ableitung"] == "A"
    ]


def get_exercise(exercise_id: str) -> Optional[dict]:
    ex = _load_all().get(exercise_id)
    if ex is None:
        return None
    twins = [t["id"] for t in _load_all().values() if t.get("zwilling_von") == exercise_id]
    return {**ex, "zwillinge": twins, "bausteine": building_blocks(ex)}


# --- Stufe 0: Bausteine --------------------------------------------------------------------------


def _shuffled(items: list, seed: str) -> list:
    rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16))
    out = list(items)
    rng.shuffle(out)
    return out


def _value_tokens(correct: List[tuple], distractors: List[tuple]) -> List[str]:
    """Richtige Werte plus bis zu drei Ablenker, ohne Doppelte. Einträge: (Wert, Geldbetrag?)."""
    seen, tokens = set(), []
    for i, (v, money) in enumerate(correct + distractors):
        if v <= 0 or v in seen or (i >= len(correct) and len(tokens) >= len(correct) + 3):
            continue
        if (v * (100 if money else 1000)).denominator != 1:  # krumme Beträge verraten den Ablenker
            continue
        seen.add(v)
        tokens.append(fmt_number(v, money))
    return tokens


def _answer_options(ex: dict) -> List[dict]:
    """Drei Antwortsätze: richtig, ohne Einheit, mit der Zahl aus dem typischen Fehler."""
    correct = ex["antwortsatz"]
    unit = ex["ergebnis"]["einheit"]
    numbers = re.findall(r"\d[\d.]*(?:,\d+)?", correct)
    number = numbers[-1]
    money = unit == "€"
    without_unit = re.sub(r"\s+" + re.escape(unit) + r"(?=\W|$)", "", correct, count=1) if unit else correct
    wrong_value = fmt_number(ex["fehlerbeispiel"]["wert"], money)
    head, _, tail = correct.rpartition(number)
    wrong_number = head + wrong_value + tail
    options = [
        {"text": correct, "richtig": True},
        {"text": without_unit, "richtig": False, "grund": "Einheit fehlt"},
        {"text": wrong_number, "richtig": False, "grund": "Zahl passt nicht zur Rechnung"},
    ]
    unique = {o["text"]: o for o in options}
    return _shuffled(list(unique.values()), ex["id"] + "-antwort")


def building_blocks(ex: dict) -> dict:
    """Felder und Bausteine für Stufe 0. Jedes Feld nennt den richtigen Baustein."""
    result = _num(ex["ergebnis"]["wert"])
    if ex["schema"] == "rechnung":
        a, b = (_num(z) for z in ex["rechnung"]["zahlen"])
        left, right = (_num(t) for t in ex["rechnung"]["umformung"].split(":"))
        slots = {
            "ueberschlag": fmt_number(a),
            "umformung_links": fmt_number(left),
            "umformung_rechts": fmt_number(right),
            "ergebnis": fmt_number(result),
        }
        values = _value_tokens([(a, False), (left, False), (right, False), (result, False)],
                               [(v, False) for v in (result / 10, result * 10, right * 10, a / 10)])
        return {
            "felder": slots,
            "werte": _shuffled(values, ex["id"] + "-werte"),
            "rechenschritte": [],
            "antworten": _answer_options(ex),
        }

    rows = ex["zeilen"]
    money = is_money_column(ex)
    ops_l, ops_r = ex["schritte"], right_ops(ex)
    slots = {
        "op_links_1": ops_l[0], "op_links_2": ops_l[1],
        "op_rechts_1": ops_r[0], "op_rechts_2": ops_r[1],
        "mitte_links": fmt_number(rows[1][0]),
        "mitte_rechts": fmt_number(rows[1][1], money),
        "ergebnis": fmt_number(rows[2][1], money),
    }
    op_tokens = []
    for op in ops_l + ops_r + [_inverse(o) for o in ops_l]:
        if op not in op_tokens:
            op_tokens.append(op)
    mid_x, mid_y = _num(rows[1][0]), _num(rows[1][1])
    correct = [(mid_x, False), (mid_y, money), (result, money)]
    # Ablenker aus typischen Fehlern: Rechenfehler, verrutschtes Komma, falscher Hilfswert
    distractors = [(v, money) for v in (_num(ex["fehlerbeispiel"]["wert"]), result * 10, result / 10,
                                        mid_y * 10, result * 2)]
    distractors += [(mid_x * 10, False), (mid_x * 2, False)]
    values = _value_tokens(correct, distractors)
    return {
        "felder": slots,
        "werte": _shuffled(values, ex["id"] + "-werte"),
        "rechenschritte": _shuffled(op_tokens, ex["id"] + "-ops"),
        "antworten": _answer_options(ex),
    }
