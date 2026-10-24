"""Übungstyp „Ordnen“: Schritte eines Ablaufs in die richtige Reihenfolge bringen (alle Fächer).

Brenner entzünden, Arbeitsschritte einer Methode, Nahrungskette, Dialog, Kreislauf … Die Schritte stehen
wortgleich wie im Buch, in richtiger Reihenfolge (``schritte``). ``kreis: true`` = Kreislauf: der Anfang ist
egal, nur die Folge zählt. ``ablenker`` = Schritte aus derselben Quelle, die nicht in diesen Ablauf gehören.
Optional ``buch``: Bild des Buchausschnitts für „Im Buch“ (exercise_sets/bilder).

Stufen: -1 Anschauen (die Plätze der Reihe nach antippen, der Schritt erscheint), 1 Ordnen mit Hilfe (erster
Schritt, ab 5 Schritten auch der letzte, steht schon), 2 alle Schritte ordnen, 3 dazu Ablenker, die liegen
bleiben müssen. Geprüft im Browser (js/practice_ordnen.js), keine Tafel.
"""
from __future__ import annotations

from typing import List

from backend.app.services.exercise_types.common import shuffled
from backend.app.services.exercise_types.zuordnen import IMAGE_URL, IMAGES_DIR

TYP = "ordnen"
STAGES = [-1, 1, 2, 3]
BOARD_STAGES: List[int] = []
MIN_STEPS = 3


def _norm(text: str) -> str:
    return " ".join(str(text).split()).lower()


def validate(ex: dict) -> List[str]:
    errors: List[str] = []
    steps = ex.get("schritte") or []
    if not str(ex.get("titel") or "").strip():
        errors.append("Titel des Ablaufs fehlt")
    if len(steps) < MIN_STEPS:
        errors.append(f"Mindestens {MIN_STEPS} Schritte")
    if any(not str(s).strip() for s in steps):
        errors.append("Leerer Schritt")
    normed = [_norm(s) for s in steps]
    if len(set(normed)) != len(normed):
        errors.append("Ein Schritt kommt doppelt vor")
    distractors = [_norm(d) for d in ex.get("ablenker") or []]
    if not distractors:
        errors.append("Mindestens ein Ablenker für Stufe 3")
    if set(distractors) & set(normed):
        errors.append("Ein Ablenker ist zugleich ein Schritt")
    if ex.get("buch") and not (IMAGES_DIR / ex["buch"]).is_file():
        errors.append(f"Bild „{ex['buch']}“ fehlt in exercise_sets/bilder")
    return errors


def _mixed(items: list, seed: str, avoid: list) -> list:
    """Gemischt, aber nie schon in der richtigen Reihenfolge."""
    out = shuffled(items, seed)
    if out == avoid[:len(out)] and len(out) > 1:
        out = out[1:] + out[:1]
    return out


def fixed_positions(ex: dict) -> List[int]:
    """Stufe 1: Plätze (ab 0), die schon belegt sind – der erste, ab 5 Schritten auch der letzte."""
    n = len(ex["schritte"])
    return [0, n - 1] if n >= 5 else [0]


def prepare(ex: dict) -> dict:
    steps = list(ex["schritte"])
    fixed = fixed_positions(ex)
    return {
        "karten": _mixed(steps, ex["id"] + "-karten", steps),
        "karten_hilfe": _mixed([s for i, s in enumerate(steps) if i not in fixed], ex["id"] + "-hilfe",
                               [s for i, s in enumerate(steps) if i not in fixed]),
        "karten_ablenker": _mixed(steps + list(ex["ablenker"]), ex["id"] + "-ablenker", steps),
        "fest": fixed,
        "buch_url": IMAGE_URL + ex["buch"] if ex.get("buch") else None,
    }


def summary(ex: dict) -> dict:
    return {}
