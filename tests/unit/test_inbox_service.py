import io
import pytest
from pypdf import PdfWriter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models.user import User
from backend.app.models.taxonomy import Subject, Topic
from backend.app.models.dossier import Dossier
from backend.app.models.material import Material
from backend.app.services.inbox_service import (
    is_valid_inbox_file,
    get_inbox_files,
    get_inbox_status,
    process_single_inbox_file,
    process_all_inbox_files,
)

def create_sample_pdf_bytes(text: str = "Biologie Klasse 7: Pflanzenzelle und Vakuole.") -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Base User, Subject, Topic
    user = User(id="usr_thea", name="Thea", grade_level=7, school_type="Gymnasium")
    sub_bio = Subject(id="sub_bio", name="Biologie", color_code="#10b981", icon="🌿")
    sub_math = Subject(id="sub_math", name="Mathematik", color_code="#2563eb", icon="📐")
    top_bio = Topic(id="top_bio_7_cell", subject_id="sub_bio", name="Zellen & Mikroskopie", grade_level=7)
    top_math = Topic(id="top_math_7_rational", subject_id="sub_math", name="Rationale Zahlen", grade_level=7)

    session.add_all([user, sub_bio, sub_math, top_bio, top_math])
    session.commit()

    yield session
    session.close()

def test_is_valid_inbox_file_filtering(tmp_path):
    valid_pdf = tmp_path / "arbeitsblatt.pdf"
    valid_pdf.write_text("dummy")

    ds_store = tmp_path / ".DS_Store"
    ds_store.write_text("hidden")

    temp_download = tmp_path / "buch.pdf.crdownload"
    temp_download.write_text("incomplete")

    sub_dir = tmp_path / "subfolder"
    sub_dir.mkdir()

    assert is_valid_inbox_file(valid_pdf) is True
    assert is_valid_inbox_file(ds_store) is False
    assert is_valid_inbox_file(temp_download) is False
    assert is_valid_inbox_file(sub_dir) is False

def test_get_inbox_files_and_status(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    f1 = inbox / "mathe_blatt1.pdf"
    f1.write_bytes(create_sample_pdf_bytes())

    f2 = inbox / "bio_blatt1.png"
    f2.write_bytes(b"\x89PNG\r\n\x1a\n...")

    # Ignorierte Dateien
    (inbox / ".DS_Store").write_text("junk")
    (inbox / "tmp_upload.tmp").write_text("junk")

    files = get_inbox_files(inbox)
    assert len(files) == 2
    assert [f.name for f in files] == ["bio_blatt1.png", "mathe_blatt1.pdf"]

    status = get_inbox_status(inbox)
    assert status.pending_count == 2
    assert status.errors_count == 0
    assert len(status.files) == 2

def test_process_single_inbox_file_moves_and_creates_dossier(db_session, tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    materials = tmp_path / "materials"
    materials.mkdir()

    pdf_file = inbox / "biologie_pflanzenzelle_uebung.pdf"
    pdf_file.write_bytes(create_sample_pdf_bytes())

    item = process_single_inbox_file(
        db=db_session,
        file_path=pdf_file,
        materials_dir=materials
    )

    # 1. Datei in inbox/ muss WEG sein (verstoffwechselt!)
    assert not pdf_file.exists()

    # 2. Datei in materials/ muss existieren
    assert (materials / f"{item.material_id}.pdf").exists()

    # 3. Datenbank-Prüfungen
    mat = db_session.query(Material).filter_by(id=item.material_id).first()
    assert mat is not None
    assert mat.title == "Biologie Pflanzenzelle Uebung"
    assert mat.subject_id == "sub_bio"
    assert mat.dossier_id is not None
    assert mat.dossier_order == 1

    dossier = db_session.query(Dossier).filter_by(id=mat.dossier_id).first()
    assert dossier is not None
    assert "Biologie" in dossier.title

def test_corrupt_file_quarantined(db_session, tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    materials = tmp_path / "materials"
    materials.mkdir()

    # 0-Byte Datei
    corrupt_file = inbox / "kaputt.pdf"
    corrupt_file.write_bytes(b"")

    res = process_all_inbox_files(
        db=db_session,
        inbox_dir=inbox,
        materials_dir=materials
    )

    assert res.processed_count == 0
    assert res.errors_count == 1
    assert not corrupt_file.exists()

    # Liegt jetzt in _errors
    quarantined = inbox / "_errors" / "kaputt.pdf"
    error_log = inbox / "_errors" / "kaputt.pdf.error.txt"
    assert quarantined.exists()
    assert error_log.exists()
    assert "0 Bytes" in error_log.read_text()

def test_batch_process_empties_inbox(db_session, tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    materials = tmp_path / "materials"
    materials.mkdir()

    # 3 Dateien in die Dropzone werfen
    (inbox / "mathe_blatt1.pdf").write_bytes(create_sample_pdf_bytes())
    (inbox / "mathe_blatt2.pdf").write_bytes(create_sample_pdf_bytes())
    (inbox / "bio_zelle.pdf").write_bytes(create_sample_pdf_bytes())

    res = process_all_inbox_files(
        db=db_session,
        inbox_dir=inbox,
        materials_dir=materials
    )

    assert res.total_detected == 3
    assert res.processed_count == 3
    assert res.errors_count == 0

    # Der Inbox-Ordner muss danach VOLLSTÄNDIG LEER sein!
    remaining_files = get_inbox_files(inbox)
    assert len(remaining_files) == 0

    # Prüfen, dass für Mathe 2 Blätter in derselben Mappe gelandet sind
    mathe_mats = db_session.query(Material).filter_by(subject_id="sub_math").all()
    assert len(mathe_mats) == 2
    assert mathe_mats[0].dossier_id == mathe_mats[1].dossier_id
    assert {mathe_mats[0].dossier_order, mathe_mats[1].dossier_order} == {1, 2}
