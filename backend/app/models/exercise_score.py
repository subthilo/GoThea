from datetime import datetime
import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base


class ExerciseScore(Base):
    __tablename__ = "exercise_scores"

    id = Column(String, primary_key=True, default=lambda: f"exs_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, default="usr_thea", nullable=False)
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    exercise_type = Column(String, nullable=False, default="cloze")  # cloze, math_problem, etc.
    total_items = Column(Integer, default=1, nullable=False)
    correct_items = Column(Integer, default=0, nullable=False)
    mistakes_count = Column(Integer, default=0, nullable=False)
    revealed_count = Column(Integer, default=0, nullable=False)
    accuracy_percent = Column(Float, default=0.0, nullable=False)
    difficulty_level = Column(String, default="mittel", nullable=False)  # leicht, mittel, schwer
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    subject = relationship("Subject", backref="exercise_scores")
