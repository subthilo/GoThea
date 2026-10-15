import shutil
from pathlib import Path

import pypdf

from backend.app.models.material import Material
from backend.app.models.material_page import MaterialPage
import pytest

from backend.app.services import page_extraction as pe


@pytest.fixture(autouse=True)
def own_cache(tmp_path, monkeypatch):
    # Leere Test-PDFs sind byte-gleich: ohne eigenen Cache würden Tests ihre Ergebnisse gegenseitig finden
    monkeypatch.setattr(pe, "CACHE_DIR", tmp_path / "page_cache")


def _pdf(path: Path, pages: int) -> Path:
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=300)
    with open(path, "wb") as f:
        writer.write(f)
    return path


def _material(db, mid, path, pages, kind="Arbeitsblatt", parent_id=None):
    m = Material(id=mid, user_id="usr_thea", subject_id="sub_bio", title=mid, kind=kind, filename=path.name,
                 file_path=str(path), mime_type="application/pdf", page_count=pages, parent_id=parent_id)
    db.add(m)
    db.commit()
    return m


class FakeModel:
    def __init__(self):
        self.calls = 0

    def __call__(self, image_b64):
        self.calls += 1
        return {"text": f"# Seite {self.calls}\\nAufgabe 1: «S: 42»", "aufgaben": [{"nummer": "1", "aufgabe": "Rechne"}],
                "hat_handschrift": True, "hat_korrekturen_lehrkraft": False, "ist_loesungsseite": self.calls == 2,
                "lesbarkeit": "gut"}


def test_extract_material_stores_pages_and_document_text(db_session, tmp_path):
    mat = _material(db_session, "mat_ab", _pdf(tmp_path / "ab.pdf", 2), 2)
    model = FakeModel()
    assert pe.extract_material(db_session, mat, ask=model) == 2

    pages = db_session.query(MaterialPage).filter_by(material_id="mat_ab").order_by(MaterialPage.page_number).all()
    assert [p.page_number for p in pages] == [1, 2]
    assert pages[0].has_handwriting and not pages[0].is_solution_page and pages[1].is_solution_page
    assert "«S: 42»" in mat.extracted_text and "--- Seite 2 ---" in mat.extracted_text
    assert pe.missing_pages(db_session, mat) == []


def test_same_file_content_is_never_sent_to_the_model_twice(db_session, tmp_path):
    original = _pdf(tmp_path / "blatt.pdf", 2)
    copy = tmp_path / "prod_upload.pdf"
    shutil.copy(original, copy)       # z. B. dieselbe Datei später in Produktion hochgeladen
    model = FakeModel()
    pe.extract_material(db_session, _material(db_session, "mat_staging", original, 2), ask=model)
    pe.extract_material(db_session, _material(db_session, "mat_prod", copy, 2), ask=model)
    assert model.calls == 2
    assert db_session.query(MaterialPage).filter_by(material_id="mat_prod").count() == 2


def test_needs_extraction_rules():
    assert pe.needs_extraction(Material(kind="Arbeitsblatt"))
    assert pe.needs_extraction(Material(kind="Buchauszug", parent_id="mat_book"))
    assert not pe.needs_extraction(Material(kind="Buch", parent_id=None))      # über die Kapitel
    assert not pe.needs_extraction(Material(kind="Stundenplan"))


def test_queue_rules(monkeypatch):
    service = pe.PageExtractionService()
    monkeypatch.setattr(pe, "OPENAI_API_KEY", "")
    service.queue_material("mat_a")
    assert service._queue.empty()
    monkeypatch.setattr(pe, "OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(pe, "BOOK_EXTRACTION_INTERVAL_SECONDS", 0)
    service.queue_material("mat_book_ch01", pe.PRIORITY_BOOK_BACKFILL)
    assert service._queue.empty()                                               # Buch-Nachholen abgeschaltet
    service.queue_material("mat_a")
    service.queue_material("mat_a")
    assert service._queue.qsize() == 1                                          # keine Dubletten


def test_book_chapters_are_processed_one_page_at_a_time(db_session, tmp_path, monkeypatch):
    chapter = _material(db_session, "mat_ch", _pdf(tmp_path / "ch.pdf", 3), 3, kind="Buchauszug", parent_id="mat_b")
    model = FakeModel()
    monkeypatch.setattr(pe, "OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(pe, "_ask_model", model)
    monkeypatch.setattr(pe, "BOOK_EXTRACTION_INTERVAL_SECONDS", 0.01)
    service = pe.PageExtractionService()
    service._session_factory = lambda: db_session
    monkeypatch.setattr(db_session, "close", lambda: None)

    service._process("mat_ch", pe.PRIORITY_BOOK_BACKFILL)
    assert model.calls == 1 and service._queue.qsize() == 1                    # eine Seite, dann wieder eingereiht
    service._process("mat_ch", pe.PRIORITY_BOOK_BACKFILL)
    service._process("mat_ch", pe.PRIORITY_BOOK_BACKFILL)
    assert pe.missing_pages(db_session, chapter) == []


def test_page_content_endpoint_requires_parent(strict_client, db_session, tmp_path):
    _material(db_session, "mat_ep", _pdf(tmp_path / "ep.pdf", 2), 2)
    assert strict_client.get("/api/v1/materials/mat_ep/pages/1/content").status_code == 403


def test_page_content_endpoint(client, db_session, tmp_path):
    mat = _material(db_session, "mat_ep", _pdf(tmp_path / "ep.pdf", 2), 2)
    assert client.get("/api/v1/materials/mat_ep/pages/1/content").status_code == 409   # ohne API-Key nicht erschließbar
    pe.extract_material(db_session, mat, ask=FakeModel())
    res = client.get("/api/v1/materials/mat_ep/pages/2/content")
    assert res.status_code == 200 and res.json()["is_solution_page"] is True
    assert client.get("/api/v1/materials/mat_ep/pages/3/content").status_code == 404
