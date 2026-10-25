from datetime import datetime
from sqlalchemy import Column, String, DateTime
from backend.app.database import Base


class PracticeRelease(Base):
    """Freigabe einer Übung durch die Eltern in der App (Tab „Üben“, Eltern-Modus).

    Überschreibt den Status aus der Übungsdatei (exercise_sets/*.json): die Dateien kommen mit jedem Deploy neu,
    die Entscheidung der Eltern bleibt in der Datenbank. Eine Zeile je Übung (auch je Zwilling).
    """
    __tablename__ = "practice_releases"

    exercise_id = Column(String, primary_key=True)
    status = Column(String, nullable=False)  # 'freigegeben' oder 'entwurf' (zurückgezogen)
    changed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
