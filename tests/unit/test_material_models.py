import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base
from backend.app.models.user import User
from backend.app.models.taxonomy import Subject, Topic
from backend.app.models.material import Material, MaterialChunk

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Base User, Subject, Topic
    user = User(id="usr_thea", name="Thea", grade_level=7, school_type="Gymnasium")
    subject = Subject(id="sub_bio", name="Biologie", color_code="#10b981", icon="🌿")
    topic = Topic(id="top_bio_7_cell", subject_id="sub_bio", name="Zellen & Mikroskopie", grade_level=7)
    session.add_all([user, subject, topic])
    session.commit()

    yield session
    session.close()

def test_create_material_model(db_session):
    mat = Material(
        subject_id="sub_bio",
        topic_id="top_bio_7_cell",
        title="Aufbau der Pflanzenzelle",
        kind="Arbeitsblatt",
        filename="pflanzenzelle_uebung.pdf",
        file_path="data/staging/materials/mat_123.pdf",
        file_size=204850,
        mime_type="application/pdf",
        page_count=2,
        extracted_text="Chloroplasten und Zellwand...",
        summary="Übungsblatt zur Zellbiologie"
    )
    db_session.add(mat)
    db_session.commit()
    db_session.refresh(mat)

    assert mat.id.startswith("mat_")
    assert mat.user_id == "usr_thea"
    assert mat.title == "Aufbau der Pflanzenzelle"
    assert mat.subject.name == "Biologie"
    assert mat.topic.name == "Zellen & Mikroskopie"
    assert mat.page_count == 2
    assert mat.created_at is not None

def test_material_chunks_cascade_delete(db_session):
    mat = Material(
        subject_id="sub_bio",
        title="Tier- und Pflanzenzellen",
        filename="zellen.pdf",
        file_path="data/staging/materials/mat_456.pdf",
        file_size=10240,
        mime_type="application/pdf"
    )
    db_session.add(mat)
    db_session.commit()
    db_session.refresh(mat)

    chunk1 = MaterialChunk(
        material_id=mat.id,
        chunk_index=0,
        content="Definition der Vakuole und Zellmembran",
        chunk_type="rule",
        page_number=1
    )
    chunk2 = MaterialChunk(
        material_id=mat.id,
        chunk_index=1,
        content="Aufgabe 1: Beschrifte die Organellen",
        chunk_type="exercise",
        page_number=2
    )
    db_session.add_all([chunk1, chunk2])
    db_session.commit()

    # Verknüpfung prüfen
    assert len(mat.chunks) == 2
    assert mat.chunks[0].chunk_type == "rule"
    assert mat.chunks[1].chunk_type == "exercise"

    # Löschen von Material muss Chunks kaskadierend mitlöschen
    mat_id = mat.id
    db_session.delete(mat)
    db_session.commit()

    remaining_chunks = db_session.query(MaterialChunk).filter_by(material_id=mat_id).all()
    assert len(remaining_chunks) == 0
