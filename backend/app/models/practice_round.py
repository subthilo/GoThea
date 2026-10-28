from datetime import datetime
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Index
from backend.app.database import Base


class PracticeRound(Base):
    """Eine Runde, die Thea gestartet hat (Akku-Frage beantwortet): für die Eltern sichtbar, wie oft sie
    „fast leer“ wählt, und Grundlage für den Wechsel sicher/leicht bei „fast leer“ (services/practice_due.py).
    Runden der Eltern („Runde wie Thea“) und der Punkt am Üben-Symbol werden nicht festgehalten."""
    __tablename__ = "practice_rounds"

    id = Column(String, primary_key=True, default=lambda: f"prd_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, nullable=False, default="usr_thea")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    akku = Column(String, nullable=False)          # 'fast_leer', 'geht_so', 'voll'
    fach = Column(String, nullable=True)           # Fachseite; leer = alle Fächer
    art = Column(String, nullable=True)            # Art der ersten Aufgabe ('sicher', 'leicht', 'neu' …), leer = nichts dran
    aufgaben = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_practice_rounds_created", "created_at"),
    )
