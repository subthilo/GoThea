"""
Themenkatalog: mittlere Ebene (Lehrplan-Einheit, z. B. "Hookesches Gesetz") mit einem
Themenbereich darüber (z. B. "Mechanik"). Die Dokumentanalyse wählt aus diesem Katalog,
statt pro Dokument neue Themen zu erfinden.
"""
import uuid
from typing import Dict, Optional, Set

from sqlalchemy.orm import Session

from backend.app.models.taxonomy import Subject, Topic


def protected_topic_names() -> Dict[str, Set[str]]:
    """Lehrplan-Themen aus den Seed-Listen. Der Seeder legt sie bei jedem Start wieder an,
    deshalb dürfen sie beim Zusammenführen weder umbenannt noch gelöscht werden."""
    from backend.app.services.seeder import INITIAL_SUBJECTS
    from backend.app.services.timetable_analyzer import CANONICAL_SUBJECTS

    protected: Dict[str, Set[str]] = {}
    for entry in list(INITIAL_SUBJECTS) + list(CANONICAL_SUBJECTS.values()):
        for topic in entry.get("topics", []):
            protected.setdefault(entry["id"], set()).add(topic[0])
    return protected


def build_catalog_text(db: Session) -> str:
    """Vorhandene Themen je Fach als Text für den Analyse-Prompt."""
    lines = []
    for subject in db.query(Subject).filter_by(is_active=True).order_by(Subject.name).all():
        topics = db.query(Topic).filter_by(subject_id=subject.id).order_by(Topic.area, Topic.name).all()
        if not topics:
            continue
        entries = [f"{t.name} [{t.area}]" if t.area else t.name for t in topics]
        lines.append(f"- {subject.name}: " + "; ".join(entries))
    return "\n".join(lines)


def resolve_topic(db: Session, subject_id: str, name: Optional[str], area: Optional[str] = None) -> Optional[Topic]:
    """Findet das Thema (Groß-/Kleinschreibung egal) im Fach oder legt es mit Bereich neu an."""
    name = (name or "").strip()
    if not name:
        return None
    for topic in db.query(Topic).filter_by(subject_id=subject_id).all():
        if topic.name.strip().lower() == name.lower():
            if area and not topic.area:
                topic.area = area.strip()
                db.commit()
            return topic
    topic = Topic(
        id=f"top_{uuid.uuid4().hex[:8]}",
        subject_id=subject_id,
        name=name,
        area=(area or "").strip() or None,
        grade_level=7,
        rlp_level_code="E",
        standard_competencies=f"Automatisch erkannt: {name}",
    )
    db.add(topic)
    # Dauerhaft speichern: Die Voranalyse schlägt die ID vor, bestätigt wird im nächsten Request
    db.commit()
    return topic
