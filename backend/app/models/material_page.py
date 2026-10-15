from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import backref, relationship

from backend.app.database import Base


class MaterialPage(Base):
    """Erschlossener Inhalt einer Dokumentseite (gedruckter Text, Aufgaben, Handschrift, Korrekturen)."""
    __tablename__ = "material_pages"

    id = Column(String, primary_key=True, default=lambda: f"pg_{uuid.uuid4().hex[:10]}")
    material_id = Column(String, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False)
    content_key = Column(String, nullable=False)        # Prüfsumme der Datei + Seite (für den gemeinsamen Cache)
    text = Column(Text, nullable=False, default="")     # Vollständige Transkription (Markdown, markierte Handschrift)
    tasks_json = Column(Text, nullable=True)            # Aufgaben der Seite
    has_handwriting = Column(Boolean, default=False)
    has_teacher_marks = Column(Boolean, default=False)
    is_solution_page = Column(Boolean, default=False)
    legibility = Column(String, nullable=True)          # gut | mittel | schlecht
    model = Column(String, nullable=True)
    extracted_at = Column(DateTime, default=datetime.utcnow)

    # Mit dem Dokument löschen (ohne Kaskade versuchte SQLAlchemy, material_id zu leeren → Fehler)
    material = relationship("Material", backref=backref("pages", cascade="all, delete-orphan"))

    __table_args__ = (
        Index("idx_material_pages_unique", "material_id", "page_number", unique=True),
    )
