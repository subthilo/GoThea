from datetime import datetime
import uuid
from sqlalchemy import Column, String, Integer, DateTime
from backend.app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: f"usr_{uuid.uuid4().hex[:8]}")
    name = Column(String, nullable=False, default="Thea")
    grade_level = Column(Integer, nullable=False, default=7)
    school_type = Column(String, nullable=False, default="Gymnasium")
    federal_state = Column(String, nullable=False, default="Brandenburg")
    created_at = Column(DateTime, default=datetime.utcnow)
