from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.app.database import Base


class StudyScope(Base):
    """Ein Stück Buch, das dran ist: Buchkapitel (Material) und Seitenbereich darin (Seiten im Kapitel-PDF).

    Mit test_id gehört es zu einem Test oder einer Arbeit, ohne zu „gerade dran“. Eine Übung ist dran, wenn
    ihre Quelle oder Fundstelle in einem solchen Bereich liegt (oder ihr Thema gewählt ist).
    """
    __tablename__ = "study_scopes"

    id = Column(String, primary_key=True, default=lambda: f"scp_{uuid.uuid4().hex[:8]}")
    test_id = Column(String, ForeignKey("tests.id", ondelete="CASCADE"), nullable=True)
    material_id = Column(String, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    start_page = Column(Integer, nullable=False)
    end_page = Column(Integer, nullable=False)
    title = Column(String, nullable=False)          # Abschnitt bzw. Kapitel, wie im Inhaltsverzeichnis
    book_page = Column(Integer, nullable=True)      # gedruckte Seite des Anfangs (zum Anzeigen)
    created_at = Column(DateTime, default=datetime.utcnow)

    material = relationship("Material")
