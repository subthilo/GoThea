"""Übungstyp „Schubladen“: Begriffe in Gruppen sortieren (alle Fächer).

Reinstoff oder Stoffgemisch, löslich oder unlöslich, Pflanzen- oder Tierzelle, Pro oder Contra … Jede Gruppe
(``gruppen``: ``[{name, begriffe}]``) ist eine Schublade; Namen und Begriffe wortgleich wie im Buch, jeder
Begriff gehört in genau eine Schublade. Optional ``buch``: Bild des Buchausschnitts für „Im Buch“.

Stufen: -1 Anschauen (Schublade antippen, ihr Inhalt erscheint), 1 Sortieren, in jeder Schublade liegt schon
ein Beispiel, 2 alles sortieren, 3 Fehler finden: alle Kärtchen liegen schon, zwei davon falsch – finden und
richtig einsortieren. Geprüft im Browser (js/practice_schubladen.js), keine Tafel.
"""
from __future__ import annotations

from typing import Dict, List

from backend.app.services.exercise_types.common import shuffled
from backend.app.services.exercise_types.zuordnen import IMAGE_URL, IMAGES_DIR

TYP = "schubladen"
STAGES = [-1, 1, 2, 3]
BOARD_STAGES: List[int] = []
WRONG_IN_STAGE_3 = 2


def _norm(text: str) -> str:
    return " ".join(str(text).split()).lower()


def validate(ex: dict) -> List[str]:
    errors: List[str] = []
    groups = ex.get("gruppen") or []
    if len(groups) < 2:
        errors.append("Mindestens zwei Gruppen")
    names = [_norm(g.get("name", "")) for g in groups]
    if any(not n for n in names):
        errors.append("Gruppe ohne Namen")
    if len(set(names)) != len(names):
        errors.append("Ein Gruppenname kommt doppelt vor")
    terms = [_norm(t) for g in groups for t in g.get("begriffe") or []]
    if any(not (g.get("begriffe") or []) for g in groups):
        errors.append("Gruppe ohne Begriffe")
    if len(set(terms)) != len(terms):
        errors.append("Ein Begriff steht in zwei Gruppen")
    if len(terms) < WRONG_IN_STAGE_3 + 2:
        errors.append(f"Mindestens {WRONG_IN_STAGE_3 + 2} Begriffe")
    if ex.get("buch") and not (IMAGES_DIR / ex["buch"]).is_file():
        errors.append(f"Bild „{ex['buch']}“ fehlt in exercise_sets/bilder")
    return errors


def wrong_layout(ex: dict) -> Dict[str, int]:
    """Stufe 3: alle Begriffe in ihrer Gruppe, außer zwei aus verschiedenen Gruppen, die vertauscht sind."""
    layout = {t: i for i, g in enumerate(ex["gruppen"]) for t in g["begriffe"]}
    order = shuffled(list(layout), ex["id"] + "-fehler")
    first = order[0]
    second = next(t for t in order[1:] if layout[t] != layout[first])
    layout[first], layout[second] = layout[second], layout[first]
    return layout


def prepare(ex: dict) -> dict:
    terms = [t for g in ex["gruppen"] for t in g["begriffe"]]
    return {
        "karten": shuffled(terms, ex["id"] + "-karten"),
        "beispiele": [g["begriffe"][0] for g in ex["gruppen"]],  # Stufe 1: je Schublade das erste
        "fehler_belegung": wrong_layout(ex),
        "buch_url": IMAGE_URL + ex["buch"] if ex.get("buch") else None,
    }


def summary(ex: dict) -> dict:
    return {}
