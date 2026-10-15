from pathlib import Path
from unittest.mock import patch

import pypdf

from backend.app.models.material import Material
from backend.app.services import page_renderer as pr
from backend.app.services.book_segmentation import segment_book_material


def _pdf(path: Path, pages: int) -> Path:
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=300)
    with open(path, "wb") as f:
        writer.write(f)
    return path


def test_cleanup_and_purge_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "PAGE_CACHE_DIR", tmp_path)
    doc = _pdf(tmp_path / "doc.pdf", 2)
    mtime = int(doc.stat().st_mtime)
    current = tmp_path / f"mat_a_ch01_p1_{mtime}.jpg"
    outdated = tmp_path / f"mat_a_ch01_p1_{mtime - 100}.jpg"
    orphan = tmp_path / "mat_deleted_p3_123.jpg"
    other = tmp_path / f"mat_b_p1_{mtime}.jpg"
    for f in (current, outdated, orphan, other):
        f.write_bytes(b"jpg")

    renderer = pr.PageRenderingService()
    removed = renderer.cleanup_stale_cache({"mat_a_ch01": str(doc), "mat_b": str(doc)})
    assert removed == 2
    assert current.exists() and other.exists()
    assert not outdated.exists() and not orphan.exists()

    assert renderer.purge_material_cache(["mat_a_ch01"]) == 1
    assert not current.exists() and other.exists()


def test_page_count_is_cached_per_file_version(tmp_path):
    doc = _pdf(tmp_path / "doc.pdf", 5)
    renderer = pr.PageRenderingService()
    with patch("pypdf.PdfReader", wraps=pypdf.PdfReader) as reader:
        assert renderer.get_page_count(doc) == 5
        assert renderer.get_page_count(doc) == 5
    assert reader.call_count == 1


def test_background_renders_use_nice(tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "PAGE_CACHE_DIR", tmp_path)
    doc = _pdf(tmp_path / "doc.pdf", 1)
    renderer = pr.PageRenderingService()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        raise RuntimeError("stop")

    with patch.object(pr.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"), \
         patch.object(pr.subprocess, "run", side_effect=fake_run):
        renderer._do_render(doc, 1, tmp_path / "out.jpg", low_priority=True)
        renderer._do_render(doc, 1, tmp_path / "out.jpg", low_priority=False)

    assert calls[0][:3] == ["/usr/bin/nice", "-n", "19"]
    assert calls[1][0] == "/usr/bin/pdftoppm"


def test_startup_scan_skips_books_with_chapters(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "PAGE_CACHE_DIR", tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    book_pdf = _pdf(tmp_path / "book.pdf", 6)
    book = Material(id="mat_scan_book", user_id="usr_thea", subject_id="sub_bio", title="Buch", kind="Buch",
                    filename="book.pdf", file_path=str(book_pdf), mime_type="application/pdf", page_count=6)
    db_session.add(book)
    db_session.commit()
    segment_book_material(db_session, book, [
        {"unit_number": 1, "title": "K1", "start_pdf_page": 1, "end_pdf_page": 3, "sections": []},
        {"unit_number": 2, "title": "K2", "start_pdf_page": 4, "end_pdf_page": 6, "sections": []},
    ])

    renderer = pr.PageRenderingService()
    queued = []
    renderer.queue_page = lambda mat_id, *a, **k: queued.append(mat_id)

    class _Thread:
        def __init__(self, target, **kw): self.target = target
        def start(self): self.target()

    with patch.object(pr.threading, "Thread", _Thread), patch.object(pr.time, "sleep"):
        renderer.queue_all_database_materials(lambda: db_session)

    assert "mat_scan_book" not in queued
    assert queued.count("mat_scan_book_ch01") == 3 and queued.count("mat_scan_book_ch02") == 3


def test_segmentation_queues_chapters_and_purges_rewritten_pages(db_session, tmp_path):
    book_pdf = _pdf(tmp_path / "book2.pdf", 4)
    book = Material(id="mat_seg_queue", user_id="usr_thea", subject_id="sub_bio", title="Buch", kind="Buch",
                    filename="book2.pdf", file_path=str(book_pdf), mime_type="application/pdf", page_count=4)
    db_session.add(book)
    db_session.commit()
    with patch.object(pr.page_renderer, "queue_material") as queue, \
         patch.object(pr.page_renderer, "purge_material_cache") as purge:
        segment_book_material(db_session, book, [{"unit_number": 1, "title": "K1", "start_pdf_page": 1, "end_pdf_page": 4, "sections": []}])
    purge.assert_called_once_with(["mat_seg_queue_ch01"])
    queue.assert_called_once()
    assert queue.call_args.args[0] == "mat_seg_queue_ch01"


def test_delete_book_removes_chapter_files_and_cache(client, db_session, tmp_path, monkeypatch):
    from backend.app.routers import materials as materials_router
    monkeypatch.setattr(materials_router, "DATA_DIR", tmp_path)
    book_pdf = _pdf(tmp_path / "book3.pdf", 4)
    book = Material(id="mat_del_book", user_id="usr_thea", subject_id="sub_bio", title="Buch", kind="Buch",
                    filename="book3.pdf", file_path=str(book_pdf), mime_type="application/pdf", page_count=4)
    db_session.add(book)
    db_session.commit()
    with patch.object(pr.page_renderer, "queue_material"):
        chapters = segment_book_material(db_session, book, [{"unit_number": 1, "title": "K1", "start_pdf_page": 1, "end_pdf_page": 4, "sections": []}])
    chap_file = Path(chapters[0].file_path)

    with patch.object(pr.page_renderer, "purge_material_cache") as purge:
        assert client.delete("/api/v1/materials/mat_del_book").status_code == 204

    assert not book_pdf.exists() and not chap_file.exists()
    assert set(purge.call_args.args[0]) == {"mat_del_book", "mat_del_book_ch01"}
    assert db_session.query(Material).filter_by(parent_id="mat_del_book").count() == 0


def test_images_are_not_parsed_or_queued(db_session, tmp_path):
    from PIL import Image
    img = tmp_path / "plan.png"
    Image.new("RGB", (10, 10)).save(img)
    db_session.add(Material(id="mat_png_plan", user_id="usr_thea", subject_id="sub_bio", title="Plan", kind="Stundenplan",
                            filename="plan.png", file_path=str(img), mime_type="image/png", page_count=1))
    db_session.commit()

    renderer = pr.PageRenderingService()
    assert renderer.get_page_count(img) is None
    queued = []
    renderer.queue_page = lambda mat_id, *a, **k: queued.append(mat_id)

    class _Thread:
        def __init__(self, target, **kw): self.target = target
        def start(self): self.target()

    with patch.object(pr.threading, "Thread", _Thread), patch.object(pr.time, "sleep"):
        renderer.queue_all_database_materials(lambda: db_session)
    assert "mat_png_plan" not in queued
