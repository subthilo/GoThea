"""Übungstyp „Zuordnen“: Begriffe an ihren Platz bringen – zuerst an die Ziffern eines Schaubilds.

In jedem Fach nutzbar (Chemie: Brenner, Laborgeräte; Bio: Zelle; Geo: Karte …). Das Bild ist die Abbildung aus
dem Buch, nachgezeichnet mit Ziffernkreisen statt Beschriftungen (scripts/figure_tool.py, geprüft und von den
Eltern freigegeben); die Begriffe stehen wortgleich wie im Buch. Neben dem Bild liegt der Buchausschnitt selbst
(``original``), damit Thea nachsehen kann.

Stufen: -1 Anschauen (jede Ziffer antippen, der Begriff erscheint), 1 Wortbank mit genau den Begriffen,
2 Wortbank mit Ablenkern. Geprüft wird im Browser: gleicher Begriff (Groß-/Kleinschreibung egal) oder einer
aus ``auch``. Selbst schreiben auf der Tafel (Luna liest, der Code vergleicht) folgt als eigene Stufe.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from backend.app.services.exercise_types.common import shuffled

TYP = "zuordnen"
STAGES = [-1, 1, 2]
BOARD_STAGES: List[int] = []

IMAGES_DIR = Path(__file__).resolve().parent.parent.parent / "exercise_sets" / "bilder"
IMAGE_URL = "/api/v1/practice/bilder/"


def _norm(term: str) -> str:
    return " ".join(str(term).split()).lower()


def validate(ex: dict) -> List[str]:
    errors: List[str] = []
    image = ex.get("bild") or {}
    for key in ("datei", "original"):
        if not image.get(key) or not (IMAGES_DIR / image[key]).is_file():
            errors.append(f"Bild „{image.get(key)}“ fehlt in exercise_sets/bilder")
    fields = ex.get("felder") or []
    if len(fields) < 2:
        errors.append("Zu wenige Felder")
    if sorted(f.get("nr") for f in fields) != list(range(1, len(fields) + 1)):
        errors.append("Felder müssen 1, 2, 3 … nummeriert sein")
    for f in fields:
        if not (0 <= f.get("x", -1) <= 1 and 0 <= f.get("y", -1) <= 1):
            errors.append(f"Feld {f.get('nr')}: Lage außerhalb des Bilds")
        if not str(f.get("begriff") or "").strip():
            errors.append(f"Feld {f.get('nr')}: Begriff fehlt")
    terms = [_norm(f.get("begriff", "")) for f in fields]
    if len(set(terms)) != len(terms):
        errors.append("Ein Begriff kommt doppelt vor")
    distractors = [_norm(d) for d in ex.get("ablenker") or []]
    if len(distractors) < 2:
        errors.append("Mindestens zwei Ablenker für Stufe 2")
    if set(distractors) & set(terms):
        errors.append("Ein Ablenker ist zugleich ein richtiger Begriff")
    return errors


def prepare(ex: dict) -> dict:
    terms = [f["begriff"] for f in ex["felder"]]
    return {
        "bild_url": IMAGE_URL + ex["bild"]["datei"],
        "original_url": IMAGE_URL + ex["bild"]["original"],
        "wortbank": shuffled(terms, ex["id"] + "-bank"),
        "wortbank_ablenker": shuffled(terms + list(ex["ablenker"]), ex["id"] + "-ablenker"),
    }


def summary(ex: dict) -> dict:
    return {}
