import pytest
from sqlalchemy.exc import IntegrityError
from backend.app.models.taxonomy import Subject, Topic

def test_create_subject_model(db_session):
    subject = Subject(
        id="sub_test_chemie",
        name="Chemie",
        color_code="#a855f7",
        icon="🧪",
        min_grade=7,
        max_grade=13,
        is_active=True
    )
    db_session.add(subject)
    db_session.commit()

    retrieved = db_session.query(Subject).filter(Subject.id == "sub_test_chemie").first()
    assert retrieved is not None
    assert retrieved.name == "Chemie"
    assert retrieved.icon == "🧪"

def test_subject_unique_name_constraint(db_session):
    dup = Subject(
        id="sub_dup",
        name="Mathematik",  # Existiert bereits im Seeder
        color_code="#000000",
        icon="🔢"
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_create_topic_with_relationship(db_session):
    math = db_session.query(Subject).filter(Subject.id == "sub_math").first()
    assert math is not None

    topic = Topic(
        id="top_test_quadratisch",
        subject_id=math.id,
        name="Quadratische Funktionen",
        grade_level=9,
        rlp_level_code="F",
        standard_competencies="Nullstellen, Scheitelpunktform"
    )
    db_session.add(topic)
    db_session.commit()

    retrieved = db_session.query(Topic).filter(Topic.id == "top_test_quadratisch").first()
    assert retrieved is not None
    assert retrieved.subject.name == "Mathematik"
    assert retrieved.rlp_level_code == "F"
