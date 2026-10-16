"""Werkzeuge, die Luna (KI) während einer Antwort aufrufen kann (siehe llm.chat_stream).

Kontext wie Datenbank und Rolle wird beim Anlegen gebunden, nie von der KI übergeben: Luna spricht mit
Thea, deshalb sucht sie immer ohne Lösungen.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.taxonomy import Subject
from backend.app.prompts.luna_tools import (
    SEARCH_KIND_DESCRIPTION,
    SEARCH_QUERY_DESCRIPTION,
    SEARCH_SUBJECT_DESCRIPTION,
    SEARCH_TOOL_DESCRIPTION,
)
from backend.app.services import document_kinds as kinds
from backend.app.services import llm, material_search

SEARCH_TOOL_NAME = "unterlagen_durchsuchen"

# Arten, deren Seiten erschlossen werden (Bücher als Ganzes und Stundenpläne nicht)
SEARCHABLE_KINDS = [kinds.MITSCHRIFT, kinds.ARBEITSBLATT, kinds.BUCHAUSZUG, kinds.TEST, kinds.KLASSENARBEIT,
                    kinds.VOKABELLISTE, kinds.SONSTIGES]


def search_tool(db: Session, limit: int = 6) -> llm.Tool:
    """Werkzeug „Unterlagen durchsuchen“ über material_search.search(), immer ohne Lösungen."""
    subjects = {s.name.lower(): s for s in db.query(Subject).filter(Subject.is_active.is_(True))}

    def run(suchbegriff: str, fach: Optional[str] = None, art: Optional[str] = None) -> Dict[str, Any]:
        notes: List[str] = []
        subject = subjects.get((fach or "").strip().lower())
        if fach and subject is None:
            notes.append(f"Fach „{fach}“ gibt es nicht – ohne Fachfilter gesucht.")
        kind = art if art in SEARCHABLE_KINDS else None
        if art and kind is None:
            notes.append(f"Art „{art}“ gibt es nicht – ohne Artfilter gesucht.")
        hits = material_search.search(db, suchbegriff, include_solutions=False,
                                      subject_id=subject.id if subject else None, kind=kind, limit=limit)
        if not hits:
            notes.append("Nichts gefunden. Versuche andere Wörter oder lass die Filter weg.")
        result: Dict[str, Any] = {"treffer": [_hit(h) for h in hits]}
        if notes:
            result["hinweis"] = " ".join(notes)
        return result

    parameters = {
        "type": "object",
        "properties": {
            "suchbegriff": {"type": "string", "description": SEARCH_QUERY_DESCRIPTION},
            "fach": {"type": "string", "enum": sorted(s.name for s in subjects.values()),
                     "description": SEARCH_SUBJECT_DESCRIPTION},
            "art": {"type": "string", "enum": SEARCHABLE_KINDS, "description": SEARCH_KIND_DESCRIPTION},
        },
        "required": ["suchbegriff"],
        "additionalProperties": False,
    }
    return llm.Tool(SEARCH_TOOL_NAME, SEARCH_TOOL_DESCRIPTION, parameters, run)


def _hit(hit: material_search.SearchHit) -> Dict[str, Any]:
    """Kompakter Treffer für die KI; leere Felder entfallen (spart Tokens)."""
    data = {"fundstelle": hit.label, "fach": hit.subject_name, "art": hit.kind, "abschnitt": hit.section,
            "ausschnitt": hit.snippet, "material_id": hit.material_id, "seite": hit.page,
            "bis_seite": hit.page_to, "buch_seite": hit.book_page}
    return {k: v for k, v in data.items() if v not in (None, "")}
