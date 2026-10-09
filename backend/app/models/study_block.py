from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.database import Base

class StudyBlock(Base):
    __tablename__ = "study_blocks"

    id = Column(String, primary_key=True, default=lambda: f"blk_{uuid.uuid4().hex[:8]}")
    date = Column(String, nullable=False)  # Format: 'YYYY-MM-DD'
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)  # NULL = ganzer Tag frei
    type = Column(String, nullable=False, default="all")  # 'all' oder 'subject'
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject")

    __table_args__ = (
        UniqueConstraint("date", "subject_id", name="uq_study_block_date_subject"),
    )
