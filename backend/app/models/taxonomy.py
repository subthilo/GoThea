from datetime import datetime
import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(String, primary_key=True, default=lambda: f"sub_{uuid.uuid4().hex[:8]}")
    name = Column(String, unique=True, nullable=False)
    color_code = Column(String, nullable=False, default="#2563eb")
    icon = Column(String, nullable=False, default="📚")
    min_grade = Column(Integer, default=1)
    max_grade = Column(Integer, default=13)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    topics = relationship("Topic", back_populates="subject", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(String, primary_key=True, default=lambda: f"top_{uuid.uuid4().hex[:8]}")
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    grade_level = Column(Integer, nullable=False, default=7)
    rlp_level_code = Column(String, nullable=True)  # 'A' bis 'H'
    standard_competencies = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject", back_populates="topics")

    __table_args__ = (
        UniqueConstraint("subject_id", "grade_level", "name", name="uq_topic_subject_grade_name"),
    )
