from datetime import datetime
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base

class TutorSession(Base):
    __tablename__ = "tutor_sessions"

    id = Column(String, primary_key=True, default=lambda: f"ses_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default="usr_thea")
    test_id = Column(String, ForeignKey("tests.id", ondelete="SET NULL"), nullable=True)
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    topic_id = Column(String, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=True, default="Tafelsitzung")
    grade_level = Column(Integer, nullable=False, default=7)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    board_state_json = Column(Text, nullable=True)  # JSON mit Strokes, Tools, Dimensionen
    snapshot_data_url = Column(Text, nullable=True) # Base64 Data URL (Vorschaubild)
    summary_notes = Column(Text, nullable=True)
    # Tafel-Verwaltung (wie Notizen): zuletzt geändert/geöffnet, Herkunft des Namens, archiviert
    updated_at = Column(DateTime, nullable=True)
    last_opened_at = Column(DateTime, nullable=True)
    title_source = Column(String, nullable=False, default="auto")  # 'auto', 'ai', 'user'
    archived_at = Column(DateTime, nullable=True)

    subject = relationship("Subject")
    topic = relationship("Topic")
    test = relationship("Test")
    messages = relationship("TutorMessage", back_populates="session", cascade="all, delete-orphan", order_by="TutorMessage.created_at")
    exercises = relationship("TutorExercise", back_populates="session", cascade="all, delete-orphan", order_by="TutorExercise.created_at")

    __table_args__ = (
        Index("idx_tutor_sessions_subject", "subject_id"),
        Index("idx_tutor_sessions_start", "start_time"),
    )

class TutorMessage(Base):
    __tablename__ = "tutor_messages"

    id = Column(String, primary_key=True, default=lambda: f"msg_{uuid.uuid4().hex[:8]}")
    session_id = Column(String, ForeignKey("tutor_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # 'student' oder 'tutor'
    content = Column(Text, nullable=False)
    board_action_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("TutorSession", back_populates="messages")

    __table_args__ = (
        Index("idx_tutor_messages_session", "session_id"),
        Index("idx_tutor_messages_created", "created_at"),
    )

class TutorExercise(Base):
    __tablename__ = "tutor_exercises"

    id = Column(String, primary_key=True, default=lambda: f"ex_{uuid.uuid4().hex[:8]}")
    session_id = Column(String, ForeignKey("tutor_sessions.id", ondelete="CASCADE"), nullable=False)
    exercise_type = Column(String, nullable=False, default="math_problem")  # 'fill_in_the_blank', 'math_problem', 'math_example', 'text_question', 'physics_diagram', 'formula_derivation'
    title = Column(String, nullable=False)
    topic = Column(String, nullable=True)
    content_json = Column(Text, nullable=False)  # JSON mit Aufgabendaten, Formeln, SVG-Diagramm etc.
    solution_hint = Column(Text, nullable=True)
    pos_x = Column(Integer, default=60)
    pos_y = Column(Integer, default=80)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("TutorSession", back_populates="exercises")

    __table_args__ = (
        Index("idx_tutor_exercises_session", "session_id"),
    )

