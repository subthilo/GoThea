from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Table
from sqlalchemy.orm import relationship
from backend.app.database import Base

# Welche Themen ein Test abfragt (von den Eltern aus dem Themenkatalog gewählt); daraus ergibt sich,
# was Thea vor dem Test übt
test_topics = Table(
    "test_topics", Base.metadata,
    Column("test_id", String, ForeignKey("tests.id", ondelete="CASCADE"), primary_key=True),
    Column("topic_id", String, ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)


class Test(Base):
    __tablename__ = "tests"
    __test__ = False  # Verhindert, dass pytest das ORM-Modell als Test-Klasse interpretiert

    id = Column(String, primary_key=True, default=lambda: f"tst_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default="usr_thea")
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String, nullable=False, default="Klassenarbeit")  # 'Test', 'Klassenarbeit', 'Klausur'
    date = Column(String, nullable=False)  # Format: 'YYYY-MM-DD'
    note = Column(String, nullable=True)   # Themen oder Notizen
    source_origin = Column(String, default="manual")  # 'manual', 'iserv_caldav', 'iserv_tasks'
    external_uid = Column(String, nullable=True)      # CalDAV UID
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject")
    topics = relationship("Topic", secondary=test_topics, order_by="Topic.name")
    completed_tasks = relationship("CompletedTask", back_populates="test", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_tests_date", "date"),
        Index("idx_tests_external_uid", "external_uid"),
    )
