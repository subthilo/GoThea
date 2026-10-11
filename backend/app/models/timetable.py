from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

class TimetableSlot(Base):
    __tablename__ = "timetable_slots"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), default="usr_thea", nullable=False)
    day_of_week = Column(String, nullable=False)   # "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"
    period = Column(Integer, nullable=False)       # 1 bis 8
    period_label = Column(String, nullable=True)   # "1.", "2.", "6.1", "6.2", etc.
    start_time = Column(String, nullable=True)     # "07:45"
    end_time = Column(String, nullable=True)       # "08:30"
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=True)
    subject_code = Column(String, nullable=True)   # "D", "Ma", "Fr", "Bio", "Ph", etc.
    subject_name = Column(String, nullable=False)  # "Deutsch", "Mathematik"
    custom_title = Column(String, nullable=True)   # "*Mittag", "*GT-Mittag"
    teacher = Column(String, nullable=True)        # "DÜCK", "HORN", "PAYS"
    room = Column(String, nullable=True)           # "201", "303", "gewo"
    week_type = Column(String, default="both")     # "both", "A", "B"
    is_double_period = Column(Boolean, default=False)
    is_break = Column(Boolean, default=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject")
