from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base

class PageAnnotation(Base):
    __tablename__ = "page_annotations"

    id = Column(String, primary_key=True)  # z. B. ann_mat_book_math_7_ch1_p2
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default="usr_thea")
    material_id = Column(String, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False, default=1)
    strokes_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    material = relationship("Material", backref="page_annotations")

    __table_args__ = (
        Index("idx_annotations_mat_page", "material_id", "page_number", unique=True),
        Index("idx_annotations_user", "user_id"),
    )
