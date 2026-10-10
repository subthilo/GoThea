from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Dossier(Base):
    """
    Repräsentiert eine digitale Mappe oder einen Hefter für Schulmaterialien.
    Typen: 'hefter' (z. B. Mathe-Hefter), 'lehrbuch' (z. B. Mathebuch 7. Klasse), 'testsammlung'.
    Enthält eine geordnete Liste von Materialien (Arbeitsblätter, Kapitel, Notizen).
    """
    __tablename__ = "dossiers"

    id = Column(String, primary_key=True, default=lambda: f"dos_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default="usr_thea")
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    topic_id = Column(String, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=False)
    kind = Column(String, nullable=False, default="hefter")  # 'hefter', 'lehrbuch', 'testsammlung', 'uebungsmappe'
    color_code = Column(String, nullable=False, default="#2563eb")
    icon = Column(String, nullable=False, default="📁")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationen
    user = relationship("User")
    subject = relationship("Subject")
    topic = relationship("Topic")
    materials = relationship(
        "Material",
        back_populates="dossier",
        cascade="all, delete-orphan",
        order_by="Material.dossier_order"
    )

    __table_args__ = (
        Index("idx_dossiers_subject", "subject_id"),
        Index("idx_dossiers_topic", "topic_id"),
        Index("idx_dossiers_user", "user_id"),
        Index("idx_dossiers_created", "created_at"),
    )
