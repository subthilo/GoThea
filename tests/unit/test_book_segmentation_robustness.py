import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pypdf

from backend.app.models.material import Material
from backend.app.services import book_segmentation as bs
from backend.app.services.document_analyzer import DocumentAnalysisResult


def _make_book(db_session, tmp_path, book_id="mat_bio_test", pages=40, title="Biobuch"):
    pdf_path = tmp_path / f"{book_id}.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=300)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    book = Material(id=book_id, user_id="usr_thea", subject_id="sub_bio", title=title, kind="Buch",
                    filename=pdf_path.name, file_path=str(pdf_path), mime_type="application/pdf", page_count=pages)
    db_session.add(book)
    db_session.commit()
    return book


def _spec(n, title, start, end):
    return {"unit_number": n, "title": title, "start_pdf_page": start, "end_pdf_page": end,
            "book_start_page": start, "book_end_page": end, "sections": []}


def test_parallel_segmentations_of_same_book_are_serialized():
    active, max_active = 0, 0
    guard = threading.Lock()

    def slow_segment(db, book, force=False):
        nonlocal active, max_active
        with guard:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.2)
        with guard:
            active -= 1
        return []

    book = MagicMock(id="mat_parallel")
    with patch.object(bs, "_auto_detect_and_segment_book_unlocked", side_effect=slow_segment):
        threads = [threading.Thread(target=bs.auto_detect_and_segment_book, args=(None, book)) for _ in range(3)]
        for t in threads:
            t.start()
        time.sleep(0.05)
        assert bs.is_segmentation_running("mat_parallel")
        for t in threads:
            t.join()

    assert max_active == 1
    assert not bs.is_segmentation_running("mat_parallel")


def test_background_trigger_skips_running_segmentation():
    with bs._segmentation_locks_guard:
        bs._segmentations_running.add("mat_busy")
    try:
        with patch.object(bs.threading, "Thread") as thread_cls:
            bs.trigger_background_book_segmentation("mat_busy")
        thread_cls.assert_not_called()
    finally:
        with bs._segmentation_locks_guard:
            bs._segmentations_running.discard("mat_busy")


def test_books_endpoints_never_segment_synchronously(client, db_session, tmp_path):
    _make_book(db_session, tmp_path, book_id="mat_unsegmented")
    with patch("backend.app.routers.books.trigger_background_book_segmentation") as trigger, \
         patch("backend.app.routers.books.auto_detect_and_segment_book") as sync_segment:
        assert client.get("/api/v1/books").status_code == 200
        detail = client.get("/api/v1/books/mat_unsegmented")
    assert detail.status_code == 200
    assert detail.json()["chapters"][0]["title"].startswith("Gesamtlehrbuch")
    sync_segment.assert_not_called()
    trigger.assert_any_call("mat_unsegmented")


def test_ai_chapters_are_numbered_sequentially(tmp_path):
    pdf = tmp_path / "scan.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(30):
        writer.add_blank_page(width=200, height=300)
    with open(pdf, "wb") as f:
        writer.write(f)

    # KI nummeriert uneinheitlich (Einführung als 0, doppelte 1)
    chapters = [{"unit_number": 0, "title": "Einführung", "start_pdf_page": 6, "end_pdf_page": 7},
                {"unit_number": 1, "title": "Die Zelle", "start_pdf_page": 8, "end_pdf_page": 20},
                {"unit_number": 1, "title": "Lebensräume", "start_pdf_page": 21, "end_pdf_page": 30}]
    mock_client = MagicMock()
    choice = MagicMock()
    choice.message.content = json.dumps({"chapters": chapters})
    mock_client.chat.completions.create.return_value = MagicMock(choices=[choice])

    with patch("backend.app.config.OPENAI_API_KEY", "sk-fake"), \
         patch("openai.OpenAI", return_value=mock_client), \
         patch("backend.app.services.material_ingestion.render_material_page_as_image", return_value=(b"x", "image/jpeg")):
        result = bs.extract_chapters_with_ai(pdf, 30, title_hint="Biobuch")

    assert [c["unit_number"] for c in result] == [1, 2, 3]


def test_resegmentation_removes_stale_chapters(db_session, tmp_path):
    book = _make_book(db_session, tmp_path, book_id="mat_stale")
    bs.segment_book_material(db_session, book, [_spec(1, "A", 1, 10), _spec(2, "B", 11, 20), _spec(3, "C", 21, 40)])
    third_file = Path(db_session.query(Material).filter_by(id="mat_stale_ch03").one().file_path)
    assert third_file.exists()

    bs.segment_book_material(db_session, book, [_spec(1, "A", 1, 20), _spec(2, "B", 21, 40)], force=True)

    children = db_session.query(Material).filter_by(parent_id="mat_stale").order_by(Material.dossier_order).all()
    assert [(c.title, c.page_count) for c in children] == [("A", 20), ("B", 20)]
    assert not third_file.exists()


def test_pre_analyze_with_fixed_subject_still_uses_ai_title(client):
    ai_result = DocumentAnalysisResult(
        subject_id="sub_math", subject_name="Mathematik", topic_id="top_x", topic_name="X",
        kind="Buch", title="Biosphäre 7/8 Berlin/Brandenburg", normalized_filename="x.pdf",
        dossier_title="Biologie", dossier_kind="lehrbuch", summary="Biologie-Lehrbuch für Klasse 7/8."
    )
    with patch("backend.app.config.OPENAI_API_KEY", "sk-fake"), \
         patch("backend.app.services.document_analyzer.analyze_document_content", return_value=ai_result):
        res = client.post(
            "/api/v1/materials/pre-analyze",
            data={"subject_id": "sub_bio"},
            files={"file": ("Biobuch.pdf", b"%PDF-1.4 dummy", "application/pdf")},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["predicted_title"] == "Biosphäre 7/8 Berlin/Brandenburg"
    assert data["predicted_subject_id"] == "sub_bio"
    assert data["predicted_topic_id"] is None
