import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base
from backend.app.models.user import User
from backend.app.models.taxonomy import Subject, Topic
from backend.app.models.dossier import Dossier
from backend.app.models.material import Material

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Base User, Subject, Topic
    user = User(id="usr_thea", name="Thea", grade_level=7, school_type="Gymnasium")
    subject = Subject(id="sub_math", name="Mathematik", color_code="#2563eb", icon="📐")
    topic = Topic(id="top_math_7_rational", subject_id="sub_math", name="Rationale Zahlen", grade_level=7)
    session.add_all([user, subject, topic])
    session.commit()

    yield session
    session.close()

def test_create_dossier_model(db_session):
    dossier = Dossier(
        subject_id="sub_math",
        topic_id="top_math_7_rational",
        title="Hefter: Rationale Zahlen",
        kind="hefter",
        color_code="#2563eb",
        icon="📁",
        description="Alle Mitschriften und Arbeitsblätter zu rationalen Zahlen"
    )
    db_session.add(dossier)
    db_session.commit()
    db_session.refresh(dossier)

    assert dossier.id.startswith("dos_")
    assert dossier.user_id == "usr_thea"
    assert dossier.title == "Hefter: Rationale Zahlen"
    assert dossier.kind == "hefter"
    assert dossier.subject.name == "Mathematik"
    assert dossier.topic.name == "Rationale Zahlen"
    assert dossier.created_at is not None
    assert dossier.updated_at is not None

def test_dossier_material_order_and_cascade(db_session):
    dossier = Dossier(
        subject_id="sub_math",
        title="Mathe Übungsmappe",
        kind="uebungsmappe"
    )
    db_session.add(dossier)
    db_session.commit()

    # Drei Materialien mit unterschiedlicher dossier_order anlegen
    mat_page2 = Material(
        subject_id="sub_math",
        dossier_id=dossier.id,
        dossier_order=2,
        title="Blatt 2: Addition von Brüchen",
        filename="blatt2.pdf",
        file_path="data/materials/blatt2.pdf"
    )
    mat_page1 = Material(
        subject_id="sub_math",
        dossier_id=dossier.id,
        dossier_order=1,
        title="Blatt 1: Einführung Vorzeichen",
        filename="blatt1.pdf",
        file_path="data/materials/blatt1.pdf"
    )
    mat_page3 = Material(
        subject_id="sub_math",
        dossier_id=dossier.id,
        dossier_order=3,
        title="Blatt 3: Multiplikation & Division",
        filename="blatt3.pdf",
        file_path="data/materials/blatt3.pdf"
    )
    db_session.add_all([mat_page2, mat_page1, mat_page3])
    db_session.commit()
    db_session.refresh(dossier)

    # Prüfen, ob die Materialien nach dossier_order sortiert zurückgegeben werden (1, 2, 3)
    assert len(dossier.materials) == 3
    assert dossier.materials[0].title == "Blatt 1: Einführung Vorzeichen"
    assert dossier.materials[1].title == "Blatt 2: Addition von Brüchen"
    assert dossier.materials[2].title == "Blatt 3: Multiplikation & Division"

    # Kaskadierendes Löschen prüfen: Löschen der Mappe löscht auch die zugeordneten Blätter
    dossier_id = dossier.id
    db_session.delete(dossier)
    db_session.commit()

    remaining_mats = db_session.query(Material).filter_by(dossier_id=dossier_id).all()
    assert len(remaining_mats) == 0

def test_material_parent_child_book_chapters(db_session):
    # 1. Master-Buch anlegen
    master_book = Material(
        subject_id="sub_math",
        title="Mathematik – Lehrbuch 7. Klasse",
        kind="Buch",
        filename="mathe_7_buch.pdf",
        file_path="data/materials/mathe_7_buch.pdf",
        page_count=196
    )
    db_session.add(master_book)
    db_session.commit()

    # 2. Kapitel als Kind-Materialien mit parent_id und Seitenzahlen
    chap1 = Material(
        subject_id="sub_math",
        parent_id=master_book.id,
        title="Kapitel 1: Rationale Zahlen",
        kind="Buchauszug",
        filename="mathe_7_kap1.pdf",
        file_path="data/materials/mathe_7_kap1.pdf",
        page_count=18,
        start_page=1,
        end_page=18
    )
    chap2 = Material(
        subject_id="sub_math",
        parent_id=master_book.id,
        title="Kapitel 2: Terme und Gleichungen",
        kind="Buchauszug",
        filename="mathe_7_kap2.pdf",
        file_path="data/materials/mathe_7_kap2.pdf",
        page_count=22,
        start_page=19,
        end_page=40
    )
    db_session.add_all([chap1, chap2])
    db_session.commit()
    db_session.refresh(master_book)

    # Prüfen der Relationen
    assert len(master_book.children) == 2
    assert chap1.parent.title == "Mathematik – Lehrbuch 7. Klasse"
    assert chap1.start_page == 1
    assert chap1.end_page == 18

    # Kaskadierendes Löschen: Löschen des Master-Buchs löscht auch die Kapitel
    book_id = master_book.id
    db_session.delete(master_book)
    db_session.commit()

    remaining_chaps = db_session.query(Material).filter_by(parent_id=book_id).all()
    assert len(remaining_chaps) == 0
