from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.database import Base

class CompletedTask(Base):
    __tablename__ = "completed_tasks"

    id = Column(String, primary_key=True, default=lambda: f"tsk_{uuid.uuid4().hex[:8]}")
    test_id = Column(String, ForeignKey("tests.id", ondelete="CASCADE"), nullable=False)
    task_identifier = Column(String, nullable=False)  # z. B. '{test_id}_{date}'
    completed_at = Column(DateTime, default=datetime.utcnow)

    test = relationship("Test", back_populates="completed_tasks")

    __table_args__ = (
        UniqueConstraint("test_id", "task_identifier", name="uq_completed_task_test_identifier"),
    )
