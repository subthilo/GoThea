from datetime import datetime
import uuid
from sqlalchemy import Boolean, Column, String, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base


class PracticeAttempt(Base):
    """Ein Versuch an einer Übung auf einer Stufe (Anfang von Gedächtnis/Lernstand).

    Stufe 0 läuft im Tab „Üben“, Stufen 1–4 auf einer Übungstafel (ein Versuch pro Tafel). Die Zähler
    fassen die Ereignisse zusammen; der Versuch bleibt, auch wenn die Tafel gelöscht wird.
    """
    __tablename__ = "practice_attempts"

    id = Column(String, primary_key=True, default=lambda: f"pat_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, nullable=False, default="usr_thea")
    exercise_id = Column(String, nullable=False)
    exercise_type = Column(String, nullable=True)  # z. B. 'sachaufgabe'
    stage = Column(Integer, nullable=False)
    board_id = Column(String, ForeignKey("tutor_sessions.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_activity_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    solved_at = Column(DateTime, nullable=True)  # erstes Mal richtig
    solved_first_try = Column(Boolean, nullable=True)  # beim Lösen: bis dahin kein Fehler, Tipp, keine Lösung
    checks = Column(Integer, nullable=False, default=0)
    failed_checks = Column(Integer, nullable=False, default=0)  # Prüfungen mit Fehlern (nicht: unsicher gelesen)
    hints_used = Column(Integer, nullable=False, default=0)
    solution_shown = Column(Boolean, nullable=False, default=False)
    guess = Column(String, nullable=True)  # Antwort auf die Schätzfrage (Stufe 0)

    events = relationship("PracticeEvent", back_populates="attempt", cascade="all, delete-orphan",
                          order_by="PracticeEvent.created_at")

    __table_args__ = (
        Index("idx_practice_attempts_exercise", "exercise_id", "stage"),
        Index("idx_practice_attempts_board", "board_id"),
    )


class PracticeEvent(Base):
    """Einzelnes Ereignis eines Versuchs: Schätzung, Tipp, Lösung gezeigt, Prüfung (mit Ergebnis)."""
    __tablename__ = "practice_events"

    id = Column(String, primary_key=True, default=lambda: f"pev_{uuid.uuid4().hex[:8]}")
    attempt_id = Column(String, ForeignKey("practice_attempts.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String, nullable=False)  # 'guess', 'hint', 'solution', 'check'
    data_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    attempt = relationship("PracticeAttempt", back_populates="events")

    __table_args__ = (
        Index("idx_practice_events_attempt", "attempt_id"),
    )
