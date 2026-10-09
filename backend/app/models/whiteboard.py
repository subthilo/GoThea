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
    snapshot_data_url = Column(Text, nullable=True) # Base64 Data URL (PNG Preview)
    summary_notes = Column(Text, nullable=True)

    subject = relationship("Subject")
    topic = relationship("Topic")
    test = relationship("Test")

    __table_args__ = (
        Index("idx_tutor_sessions_subject", "subject_id"),
        Index("idx_tutor_sessions_start", "start_time"),
    )
