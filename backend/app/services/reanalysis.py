"""
Neu-Einordnung bereits gespeicherter Dokumente mit der aktuellen Dokumentanalyse
(z. B. nach Einführung neuer Dokumentarten).
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.app.config import DATA_DIR
from backend.app.models.material import Material
from backend.app.services.document_analyzer import analyze_document_content
from backend.app.services.document_kinds import BUCH, BUCHAUSZUG, NEVER_BOOK_KINDS, STUNDENPLAN

logger = logging.getLogger(__name__)


@dataclass
class ReanalysisChange:
    material_id: str
    changes: List[str] = field(default_factory=list)
    removed_chapters: int = 0
    segmentation_triggered: bool = False


def remove_book_chapters(db: Session, book: Material) -> int:
    """Entfernt alle Kapitel eines Buchs inklusive Dateien (nur im Datenordner) und Seitenbilder."""
    from backend.app.services.page_renderer import page_renderer

    chapters = db.query(Material).filter_by(parent_id=book.id).all()
    files = [Path(c.file_path) for c in chapters if c.file_path]
    ids = [c.id for c in chapters]
    for chapter in chapters:
        db.delete(chapter)
    db.commit()
    for f in files:
        if f.resolve().is_relative_to(DATA_DIR.resolve()) and f != Path(book.file_path):
            f.unlink(missing_ok=True)
    page_renderer.purge_material_cache(ids)
    return len(ids)


def reanalyze_material(db: Session, material: Material) -> Optional[ReanalysisChange]:
    """Analysiert ein Dokument neu und übernimmt Art, Titel, Zusammenfassung, Thema und Signale.
    Das Fach bleibt unverändert. Kapitel und Stundenpläne werden übersprungen."""
    if material.parent_id or material.kind in (STUNDENPLAN, BUCHAUSZUG):
        return None
    path = Path(material.file_path or "")
    if not path.exists():
        return None

    result = analyze_document_content(db, path, material.extracted_text or "", material.mime_type, original_filename=material.filename)
    report = ReanalysisChange(material_id=material.id)

    def update(attr: str, value, label: str):
        old = getattr(material, attr)
        if value is not None and value != old:
            report.changes.append(f"{label}: {old!r} -> {value!r}")
            setattr(material, attr, value)

    old_kind = material.kind
    new_kind = result.kind
    # Ein Buch verliert seine Kapitel nur, wenn es ausdrücklich als etwas anderes erkannt wird
    if old_kind == BUCH and new_kind not in NEVER_BOOK_KINDS:
        new_kind = BUCH
    update("kind", new_kind, "Art")
    update("title", result.title, "Titel")
    update("summary", result.summary, "Zusammenfassung")
    if result.subject_id == material.subject_id:
        update("topic_id", result.topic_id, "Thema")
    update("solution_pages_json", json.dumps(result.solution_pages) if result.solution_pages else None, "Lösungsseiten")
    update("worked_on_paper", result.worked_on_paper, "bearbeitet")
    update("teacher_graded", result.teacher_graded, "bewertet")
    db.commit()

    if old_kind == BUCH and material.kind != BUCH:
        report.removed_chapters = remove_book_chapters(db, material)
    elif material.kind == BUCH and old_kind != BUCH:
        from backend.app.services.book_segmentation import trigger_background_book_segmentation
        trigger_background_book_segmentation(material.id)
        report.segmentation_triggered = True

    return report


def reanalyze_all(db: Session) -> List[ReanalysisChange]:
    reports = []
    for material in db.query(Material).filter(Material.parent_id.is_(None)).order_by(Material.created_at).all():
        try:
            report = reanalyze_material(db, material)
        except Exception as e:
            db.rollback()
            logger.error(f"Neu-Einordnung von {material.id} fehlgeschlagen: {e}", exc_info=True)
            continue
        if report:
            reports.append(report)
    return reports
