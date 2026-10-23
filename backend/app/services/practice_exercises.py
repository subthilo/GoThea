"""Übungen aus echten Aufgaben – der Kern für alle Fächer und Übungstypen (Konzept-Doc).

Jede Übung geht auf eine Aufgabe aus Theas Materialien zurück (A Original, B Zwilling). Die Daten
entstehen in Claude-Code-Sessions, werden dort von den Eltern begutachtet und liegen als JSON in
``backend/app/exercise_sets/`` (eine Datei je Typ und Sammlung, ``"typ"`` nennt den Übungstyp).
Der Kern kennt den Kopf jeder Übung (Fach, Thema, Fundstelle, Status) und die Liste; was die
Aufgabenform ausmacht (Datenprüfung, Stufen, Bausteine), steht im Typ (services/exercise_types/).
Entwürfe sieht nur der Eltern-Modus.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.services import exercise_types

EXERCISE_SETS_DIR = Path(__file__).resolve().parent.parent / "exercise_sets"

ENTWURF, FREIGEGEBEN = "entwurf", "freigegeben"
STATUSES = (ENTWURF, FREIGEGEBEN)


# --- Kopf jeder Übung (alle Fächer und Typen): Fach, Thema, Quelle und Fundstelle ---------------------------
# quelle/nachschlagen: material_id + material_seite = Seite in der Datei (bei Buchkapiteln im Kapitel-PDF),
# seite = Seite, wie Thea sie sieht (gedruckte Buchseite), material = Titel (beim Kapitel der Buchtitel).
REFERENCE_KEYS = ("quelle", "nachschlagen")


def validate_header(ex: dict) -> List[str]:
    """Fehlerliste des Kopfs ohne Datenbank (leer = vollständig)."""
    errors: List[str] = []
    if not str(ex.get("fach") or "").startswith("sub_"):
        errors.append("Fach fehlt (fach: sub_…)")
    if not str(ex.get("thema") or "").startswith("top_"):
        errors.append("Thema fehlt (thema: top_…)")
    if not ex.get("quelle"):
        errors.append("Quelle fehlt")
    if not ex.get("aufgabentext"):
        errors.append("Aufgabentext fehlt")
    if ex.get("status") not in STATUSES:
        errors.append(f"Status fehlt ({' oder '.join(STATUSES)})")
    if exercise_types.get(ex.get("typ")) is None:
        errors.append(f"Übungstyp „{ex.get('typ')}“ gibt es nicht")
    for key in REFERENCE_KEYS:
        ref = ex.get(key)
        if not ref:
            continue
        if not str(ref.get("material_id") or "").startswith("mat_"):
            errors.append(f"{key}: material_id fehlt")
        page = ref.get("material_seite")
        if not isinstance(page, int) or page < 1:
            errors.append(f"{key}: material_seite fehlt")
    return errors


def check_references(db, ex: dict) -> List[str]:
    """Stimmen Fach, Thema und Fundstellen mit der Datenbank überein? Für scripts/check_exercises.py."""
    from backend.app.models.material import Material
    from backend.app.models.taxonomy import Subject, Topic

    errors: List[str] = []
    if db.get(Subject, ex.get("fach")) is None:
        errors.append(f"Fach {ex.get('fach')} gibt es nicht")
    topic = db.get(Topic, ex.get("thema"))
    if topic is None:
        errors.append(f"Thema {ex.get('thema')} gibt es nicht")
    elif topic.subject_id != ex.get("fach"):
        errors.append(f"Thema „{topic.name}“ gehört nicht zum Fach {ex.get('fach')}")
    for key in REFERENCE_KEYS:
        ref = ex.get(key)
        if not ref:
            continue
        material = db.get(Material, ref.get("material_id"))
        if material is None:
            errors.append(f"{key}: Material {ref.get('material_id')} gibt es nicht")
            continue
        if material.subject_id != ex.get("fach"):
            errors.append(f"{key}: „{material.title}“ gehört nicht zum Fach {ex.get('fach')}")
        page = ref.get("material_seite")
        if not 1 <= page <= (material.page_count or 1):
            errors.append(f"{key}: „{material.title}“ hat keine Seite {page}")
        if material.start_page and ref.get("seite") and material.start_page + page - 1 != ref["seite"]:
            errors.append(f"{key}: Seite {page} von „{material.title}“ ist Buchseite "
                          f"{material.start_page + page - 1}, nicht {ref['seite']}")
        title = material.parent.title if material.parent else material.title
        if ref.get("material") and ref["material"] != title:
            errors.append(f"{key}: Material heißt „{title}“, nicht „{ref['material']}“")
    return errors



def validate(ex: dict) -> List[str]:
    """Fehlerliste einer Übung ohne Datenbank: Kopf, dann die Daten nach den Regeln ihres Typs."""
    errors = validate_header(ex)
    exercise_type = exercise_types.get(ex.get("typ"))
    return errors + (exercise_type.validate(ex) if exercise_type else [])


def is_draft(ex: dict) -> bool:
    return ex.get("status") != FREIGEGEBEN


# --- Laden ---------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_all() -> Dict[str, dict]:
    exercises: Dict[str, dict] = {}
    for path in sorted(EXERCISE_SETS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for ex in data["uebungen"]:
            exercises[ex["id"]] = {**ex, "typ": data["typ"]}
    return exercises


def _visible(include_drafts: bool) -> Dict[str, dict]:
    return {i: ex for i, ex in _load_all().items() if include_drafts or not is_draft(ex)}


def _stages(ex: dict) -> dict:
    exercise_type = exercise_types.get(ex["typ"])
    return {"stufen": list(exercise_type.STAGES), "tafel_stufen": list(exercise_type.BOARD_STAGES)}


def list_exercises(include_drafts: bool = False) -> List[dict]:
    """Kurzfassung für die Liste: Originale mit ihren Zwillingen (Entwürfe nur für die Eltern)."""
    visible = _visible(include_drafts)
    twins: Dict[str, List[str]] = {}
    for ex in visible.values():
        if ex.get("zwilling_von"):
            twins.setdefault(ex["zwilling_von"], []).append(ex["id"])
    return [
        {
            "id": ex["id"],
            "typ": ex["typ"],
            "fach": ex["fach"],
            "thema": ex["thema"],
            "status": ex["status"],
            "aufgabentext": ex["aufgabentext"],
            "abschnitt": ex.get("abschnitt"),
            "quelle": ex["quelle"],
            "zwillinge": twins.get(ex["id"], []),
            **_stages(ex),
            **exercise_types.get(ex["typ"]).summary(ex),
        }
        for ex in visible.values() if ex["ableitung"] == "A"
    ]


def get_exercise(exercise_id: str, include_drafts: bool = False) -> Optional[dict]:
    visible = _visible(include_drafts)
    ex = visible.get(exercise_id)
    if ex is None:
        return None
    twins = [t["id"] for t in visible.values() if t.get("zwilling_von") == exercise_id]
    return {**ex, "zwillinge": twins, **_stages(ex), **exercise_types.get(ex["typ"]).prepare(ex)}
