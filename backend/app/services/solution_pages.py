"""Welche Seiten eines Dokuments Lösungen sind – die sieht Thea nicht (Seitenbild, Download, Volltext).

Gesperrt wird nur nach Angaben, die die Eltern beim Upload bestätigt haben: die Dokumentart („Lösungsheft“ →
ganzes Dokument) und die Lösungsseiten der Voranalyse. Die Markierung der Seiten-Erschließung
(material_pages.is_solution_page) zählt hier bewusst nicht: Sie trifft auch Methodenseiten mit Beispiellösung
(gemessen 24.10. auf Staging, z. B. Chemie Buch S. 20 „Protokollieren“), und die braucht Thea.

Frei werden die Lösungen eines Dokuments, sobald Thea es bearbeitet hat (Nutzer, 24.10.): auf Papier (Voranalyse:
bearbeitet oder von der Lehrkraft bewertet) oder hier – jede freigegebene Übung mit dem Dokument als Quelle
einmal geschafft (egal auf welcher Stufe, auch über einen Zwilling; wie das Öffnen der Knoten in practice_due).
Danach lernt sie mit der Lösung. Später (Bearbeitungs-Ablauf): auch nach Abgabe.
"""
import json
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from backend.app.models.practice_attempt import PracticeAttempt
from backend.app.services import practice_exercises


# Statt der Lösungsseite: A4-Blatt mit dem Schloss aus frontend/Icons/Schloss.svg (Seitenverhältnis wie eine Seite,
# damit Leser und Tafel nicht springen)
LOCKED_PAGE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 595 842" width="595" height="842">'
    '<rect width="595" height="842" fill="#F1F5F9"/>'
    '<g transform="translate(222.5 346) scale(1.5)" fill="none" stroke="#94A3B8" stroke-width="4" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="24" y="44" width="52" height="40" rx="6"/>'
    '<path d="M 34 44 L 34 32 A 16 16 0 0 1 66 32 L 66 44"/>'
    '<line x1="50" y1="58" x2="50" y2="70"/></g></svg>'
)


def whole_document(material) -> bool:
    return "lösung" in (material.kind or "").lower()


def pages(material) -> Set[int]:
    """Lösungsseiten laut Voranalyse (Seiten in der Datei)."""
    try:
        return {int(p) for p in json.loads(material.solution_pages_json or "[]")}
    except (ValueError, TypeError):
        return set()


def is_solution_page(material, page: int) -> bool:
    return whole_document(material) or page in pages(material)


def _as_json(numbers) -> Optional[str]:
    return json.dumps(sorted(numbers)) if numbers else None


def after_reorder(material, page_order: List[int]) -> Optional[str]:
    """Lösungsseiten nach Umsortieren/Löschen (page_order[i] = alte Seite an Position i+1): jede Sperre wandert
    mit ihrer Seite – sonst läge sie danach auf einer Aufgabenseite und die Lösung wäre für Thea frei."""
    old = pages(material)
    return _as_json({new for new, prev in enumerate(page_order, start=1) if prev in old})


def after_merge(materials, page_counts: Dict[str, int], page_offsets: Dict[str, int]) -> Optional[str]:
    """Lösungsseiten des zusammengeführten Dokuments: die der Quellen, verschoben um die Seiten davor. Ist eine
    Quelle ganz ein Lösungsdokument, sind alle ihre Seiten gesperrt (das neue Dokument trägt die Art der ersten)."""
    locked = set()
    for mat in materials:
        offset = page_offsets[mat.id]
        own = range(1, page_counts[mat.id] + 1) if whole_document(mat) else pages(mat)
        locked |= {offset + p for p in own if 1 <= p <= page_counts[mat.id]}
    return _as_json(locked)


def unlocked(db: Session, material) -> bool:
    """Darf Thea die Lösungen sehen? Ja, sobald sie das Dokument bearbeitet hat (siehe oben)."""
    if material.worked_on_paper or material.teacher_graded:
        return True
    families = [f for f in practice_exercises.list_exercises()
                if (f.get("quelle") or {}).get("material_id") == material.id]
    if not families:
        return False
    ids = [i for f in families for i in (f["id"], *f["zwillinge"])]
    solved = {row[0] for row in db.query(PracticeAttempt.exercise_id)
              .filter(PracticeAttempt.exercise_id.in_(ids), PracticeAttempt.solved_at.isnot(None))}
    return all(solved & {f["id"], *f["zwillinge"]} for f in families)
