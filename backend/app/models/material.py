from datetime import datetime
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Material(Base):
    __tablename__ = "materials"

    id = Column(String, primary_key=True, default=lambda: f"mat_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default="usr_thea")
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    topic_id = Column(String, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    dossier_id = Column(String, ForeignKey("dossiers.id", ondelete="SET NULL"), nullable=True)
    dossier_order = Column(Integer, nullable=False, default=1)
    parent_id = Column(String, ForeignKey("materials.id", ondelete="CASCADE"), nullable=True)
    title = Column(String, nullable=False)
    kind = Column(String, nullable=False, default="Arbeitsblatt")  # 'Arbeitsblatt', 'Hefterseite', 'Buchauszug', 'Übungszettel', 'Buch'
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False, default=0)
    mime_type = Column(String, nullable=False, default="application/pdf")
    page_count = Column(Integer, nullable=False, default=1)
    start_page = Column(Integer, nullable=True)  # Buch-Seitennummer Start
    end_page = Column(Integer, nullable=True)    # Buch-Seitennummer Ende
    extracted_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    toc_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject")
    topic = relationship("Topic")
    dossier = relationship("Dossier", back_populates="materials")
    parent = relationship("Material", remote_side=[id], back_populates="children")
    children = relationship("Material", back_populates="parent", cascade="all, delete-orphan")
    chunks = relationship("MaterialChunk", back_populates="material", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_materials_subject", "subject_id"),
        Index("idx_materials_topic", "topic_id"),
        Index("idx_materials_dossier", "dossier_id"),
        Index("idx_materials_parent", "parent_id"),
        Index("idx_materials_created", "created_at"),
    )

class MaterialChunk(Base):
    __tablename__ = "material_chunks"

    id = Column(String, primary_key=True, default=lambda: f"chk_{uuid.uuid4().hex[:8]}")
    material_id = Column(String, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)
    content = Column(Text, nullable=False)
    chunk_type = Column(String, nullable=False, default="general")  # 'rule', 'exercise', 'vocabulary', 'general'
    page_number = Column(Integer, nullable=True, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    material = relationship("Material", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunks_material", "material_id"),
    )
