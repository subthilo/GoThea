"""Übungen aus echten Aufgaben – der Kern für alle Fächer und Übungstypen (Konzept-Doc).

Jede Übung geht auf eine Aufgabe aus Theas Materialien zurück (A Original, B Zwilling, C umgeformt). Die Daten
entstehen in Claude-Code-Sessions, werden dort von den Eltern begutachtet und liegen als JSON in
``backend/app/exercise_sets/`` (eine Datei je Typ und Sammlung, ``"typ"`` nennt den Übungstyp).
Der Kern kennt den Kopf jeder Übung (Fach, Thema, Fundstelle, Status) und die Liste; was die
Aufgabenform ausmacht (Datenprüfung, Stufen, Bausteine), steht im Typ (services/exercise_types/).
Entwürfe sieht nur der Eltern-Modus. Die Eltern geben Übungen in der App frei (oder ziehen sie zurück); das
liegt in der Datenbank (``practice_releases``) und gilt vor dem Status der Datei – ``sync_releases`` lädt es.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.services import exercise_types

EXERCISE_SETS_DIR = Path(__file__).resolve().parent.parent / "exercise_sets"

ENTWURF, FREIGEGEBEN = "entwurf", "freigegeben"
STATUSES = (ENTWURF, FREIGEGEBEN)

# A Original, C umgeformt (gleicher Inhalt in anderer Übungsform, Quelle = Originalaufgabe): eigene Zeile in der
# Liste. B Zwilling: hängt per zwilling_von an einer A- oder C-Übung desselben Typs.
ABLEITUNGEN = ("A", "B", "C")


# --- Kopf jeder Übung (alle Fächer und Typen): Fach, Thema, Quelle und Fundstelle ---------------------------
# quelle/nachschlagen: material_id + material_seite = Seite in der Datei (bei Buchkapiteln im Kapitel-PDF),
# seite = Seite, wie Thea sie sieht (gedruckte Buchseite), material = Titel (beim Kapitel der Buchtitel).
# Ausnahme Grundwissen (Einmaleins …, vom Code erzeugt, ``erzeugt`` gesetzt): quelle = {material: "Grundwissen",
# grundwissen: "Einmaleins", nummer} ohne Material in der Datenbank.
REFERENCE_KEYS = ("quelle", "nachschlagen")


def is_basic_knowledge(ex: dict, key: str = "quelle") -> bool:
    ref = ex.get(key) or {}
    return bool(ex.get("erzeugt") and ref.get("grundwissen") and not ref.get("material_id"))


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
    exercise_type = exercise_types.get(ex.get("typ"))
    if exercise_type is None:
        errors.append(f"Übungstyp „{ex.get('typ')}“ gibt es nicht")
    elif "stufen" in ex and not (ex["stufen"] and set(ex["stufen"]) <= set(exercise_type.STAGES)):
        errors.append(f"stufen: nur Stufen des Typs ({', '.join(map(str, exercise_type.STAGES))})")
    if ex.get("ableitung") not in ABLEITUNGEN:
        errors.append(f"Ableitung fehlt ({', '.join(ABLEITUNGEN)})")
    elif (ex["ableitung"] == "B") != bool(ex.get("zwilling_von")):
        errors.append("zwilling_von gehört genau zu Zwillingen (B)")
    if ex.get("status") == FREIGEGEBEN and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(ex.get("freigegeben_am") or "")):
        errors.append("freigegeben_am fehlt (JJJJ-MM-TT)")
    for key in REFERENCE_KEYS:
        ref = ex.get(key)
        if not ref or is_basic_knowledge(ex, key):
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
        if not ref or is_basic_knowledge(ex, key):
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


def _read_sets() -> List[dict]:
    """Alle Übungen aller Dateien, auch doppelte IDs (für check_collection)."""
    exercises: List[dict] = []
    for path in sorted(EXERCISE_SETS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        exercises += [{**ex, "typ": data["typ"], "datei": path.name} for ex in data["uebungen"]]
    return exercises


@lru_cache(maxsize=1)
def _load_all() -> Dict[str, dict]:
    return {ex["id"]: {k: v for k, v in ex.items() if k != "datei"} for ex in _read_sets()}


def all_ids() -> List[str]:
    """IDs aller Übungen samt Entwürfen – auch solcher, die in keiner Liste auftauchen."""
    return list(_load_all())


def check_collection() -> List[str]:
    """Fehler, die erst im Zusammenspiel der Übungen auffallen: doppelte IDs, Zwilling ohne passendes Original."""
    errors: List[str] = []
    seen: Dict[str, str] = {}
    for ex in _read_sets():
        if ex["id"] in seen:
            errors.append(f"{ex['id']}: doppelt ({seen[ex['id']]} und {ex['datei']})")
        seen.setdefault(ex["id"], ex["datei"])
    exercises = _load_all()
    for ex in exercises.values():
        if not ex.get("zwilling_von"):
            continue
        head = exercises.get(ex["zwilling_von"])
        if head is None:
            errors.append(f"{ex['id']}: zwilling_von {ex['zwilling_von']} gibt es nicht")
        elif head.get("zwilling_von"):
            errors.append(f"{ex['id']}: {head['id']} ist selbst ein Zwilling")
        elif head["typ"] != ex["typ"]:
            errors.append(f"{ex['id']}: Zwilling muss den Typ des Originals haben ({head['typ']})")
        elif is_draft(head) and not is_draft(ex):
            errors.append(f"{ex['id']}: freigegeben, das Original {head['id']} noch nicht")
    return errors


# --- Freigaben aus der App (Datenbank) ----------------------------------------------------------------------
# exercise_id → (status, Datum); gilt vor dem Status der Datei. Der Router lädt sie zu Beginn jeder Anfrage.
_releases: Dict[str, tuple] = {}


def sync_releases(db) -> None:
    from backend.app.models.practice_release import PracticeRelease
    _releases.clear()
    for r in db.query(PracticeRelease).all():
        _releases[r.exercise_id] = (r.status, r.changed_at.strftime("%Y-%m-%d"))


def _effective(ex: dict) -> dict:
    if ex["id"] not in _releases:
        return ex
    status, day = _releases[ex["id"]]
    out = {**ex, "status": status, "freigabe_in_app": True}
    if status == FREIGEGEBEN:
        out["freigegeben_am"] = day
    return out


def family_ids(exercise_id: str) -> List[str]:
    """Eine Aufgabe = Original (A, C) mit seinen Zwillingen (B); freigegeben wird immer die ganze Aufgabe."""
    exercises = _load_all()
    head = exercises[exercise_id].get("zwilling_von") or exercise_id
    return [head] + [i for i, ex in exercises.items() if ex.get("zwilling_von") == head]


def set_release(db, exercise_id: str, status: str) -> List[str]:
    """Aufgabe (Original + Zwillinge) freigeben oder zurückziehen. Freigeben nur, wenn die Daten stimmig sind."""
    from datetime import datetime
    from backend.app.models.practice_release import PracticeRelease
    if status not in STATUSES:
        raise ValueError(f"Status {status} gibt es nicht")
    if exercise_id not in _load_all():
        raise KeyError(exercise_id)
    ids = family_ids(exercise_id)
    if status == FREIGEGEBEN:
        for i in ids:
            errors = validate(get_exercise(i, include_drafts=True))
            if errors:
                raise ValueError(f"{i}: {'; '.join(errors)}")
    now = datetime.utcnow()
    for i in ids:
        row = db.get(PracticeRelease, i)
        if row is None:
            db.add(PracticeRelease(exercise_id=i, status=status, changed_at=now))
        else:
            row.status, row.changed_at = status, now
    db.commit()
    sync_releases(db)
    return ids


def _visible(include_drafts: bool) -> Dict[str, dict]:
    effective = {i: _effective(ex) for i, ex in _load_all().items()}
    return {i: ex for i, ex in effective.items() if include_drafts or not is_draft(ex)}


def _stages(ex: dict) -> dict:
    """Stufen des Typs; eine Übung kann einzelne weglassen (``stufen``), z. B. das freie Schreiben ganzer Sätze."""
    exercise_type = exercise_types.get(ex["typ"])
    stages = [s for s in exercise_type.STAGES if s in ex.get("stufen", exercise_type.STAGES)]
    return {"stufen": stages, "tafel_stufen": [s for s in exercise_type.BOARD_STAGES if s in stages]}


def list_exercises(include_drafts: bool = False) -> List[dict]:
    """Kurzfassung für die Liste: Übungen ohne Zwillingsbezug (A, C) mit ihren Zwillingen (Entwürfe nur für die Eltern)."""
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
            "freigegeben_am": ex.get("freigegeben_am"),
            "aufgabentext": ex["aufgabentext"],
            "abschnitt": ex.get("abschnitt"),
            "quelle": ex["quelle"],
            "nachschlagen": ex.get("nachschlagen"),
            "zwillinge": twins.get(ex["id"], []),
            **_stages(ex),
            **exercise_types.get(ex["typ"]).summary(ex),
        }
        for ex in visible.values() if not ex.get("zwilling_von")
    ]


def get_exercise(exercise_id: str, include_drafts: bool = False) -> Optional[dict]:
    visible = _visible(include_drafts)
    ex = visible.get(exercise_id)
    if ex is None:
        return None
    twins = [t["id"] for t in visible.values() if t.get("zwilling_von") == exercise_id]
    return {**ex, "zwillinge": twins, **_stages(ex), **exercise_types.get(ex["typ"]).prepare(ex)}
