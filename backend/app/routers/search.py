"""Suche in Theas Unterlagen (Lupe in der App; später Lunas Werkzeug „Unterlagen durchsuchen“)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.services import material_search
from backend.app.services.parent_auth import is_parent

router = APIRouter(prefix="/api/v1/search", tags=["Suche"])


@router.get("")
def search_materials(
    q: str = Query(..., min_length=1, max_length=200),
    subject_id: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
    parent: bool = Depends(is_parent),
    db: Session = Depends(get_db),
) -> List[dict]:
    # Lösungen nur im Eltern-Modus – für Thea serverseitig verborgen
    hits = material_search.search(db, q, include_solutions=parent, subject_id=subject_id, kind=kind, limit=limit)
    return [h.to_dict() for h in hits]
