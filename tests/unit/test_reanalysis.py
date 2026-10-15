from pathlib import Path
from unittest.mock import patch

import pypdf

from backend.app.models.material import Material
from backend.app.services import reanalysis
from backend.app.services.book_segmentation import segment_book_material
from backend.app.services.document_analyzer import DocumentAnalysisResult


def _pdf(path: Path, pages: int) -> Path:
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=300)
    with open(path, "wb") as f:
        writer.write(f)
    return path


def _result(kind, subject_id="sub_english", title="Vokabelliste Englisch Klasse 7", **kw):
    return DocumentAnalysisResult(subject_id=subject_id, subject_name="Englisch", topic_id=None, topic_name=None,
                                  kind=kind, title=title, normalized_filename="x.pdf", dossier_title="-",
                                  dossier_kind="-", summary="Neu analysiert", **kw)


def _book(db_session, tmp_path, monkeypatch, book_id, pages=6):
    monkeypatch.setattr(reanalysis, "DATA_DIR", tmp_path)
    pdf = _pdf(tmp_path / f"{book_id}.pdf", pages)
    book = Material(id=book_id, user_id="usr_thea", subject_id="sub_english", title="Alt", kind="Buch",
                    filename=pdf.name, file_path=str(pdf), mime_type="application/pdf", page_count=pages)
    db_session.add(book)
    db_session.commit()
    with patch("backend.app.services.page_renderer.page_renderer.queue_material"):
        segment_book_material(db_session, book, [
            {"unit_number": 1, "title": "Unit 1", "start_pdf_page": 1, "end_pdf_page": 3, "sections": []},
            {"unit_number": 2, "title": "Unit 2", "start_pdf_page": 4, "end_pdf_page": pages, "sections": []},
        ])
    return book


def test_vocabulary_list_loses_wrong_book_chapters(db_session, tmp_path, monkeypatch):
    book = _book(db_session, tmp_path, monkeypatch, "mat_vocab")
    chapter_files = [Path(c.file_path) for c in db_session.query(Material).filter_by(parent_id="mat_vocab")]

    with patch.object(reanalysis, "analyze_document_content",
                      return_value=_result("Vokabelliste", worked_on_paper=False, teacher_graded=False)):
        report = reanalysis.reanalyze_material(db_session, book)

    assert book.kind == "Vokabelliste" and book.subject_id == "sub_english"
    assert book.teacher_graded is False
    assert report.removed_chapters == 2
    assert db_session.query(Material).filter_by(parent_id="mat_vocab").count() == 0
    assert not any(f.exists() for f in chapter_files)
    assert Path(book.file_path).exists()


def test_book_stays_book_unless_explicitly_something_else(db_session, tmp_path, monkeypatch):
    book = _book(db_session, tmp_path, monkeypatch, "mat_real_book", pages=30)
    with patch.object(reanalysis, "analyze_document_content", return_value=_result("Arbeitsblatt", title="Echter Buchtitel")):
        report = reanalysis.reanalyze_material(db_session, book)
    assert book.kind == "Buch" and book.title == "Echter Buchtitel"
    assert report.removed_chapters == 0
    assert db_session.query(Material).filter_by(parent_id="mat_real_book").count() == 2


def test_subject_is_kept_and_signals_are_stored(db_session, tmp_path, monkeypatch):
    pdf = _pdf(tmp_path / "test.pdf", 2)
    mat = Material(id="mat_test_doc", user_id="usr_thea", subject_id="sub_math", title="Test", kind="Klassenarbeit",
                   filename=pdf.name, file_path=str(pdf), mime_type="application/pdf", page_count=2)
    db_session.add(mat)
    db_session.commit()
    with patch.object(reanalysis, "analyze_document_content",
                      return_value=_result("Test", subject_id="sub_geo", title="1. Test Zuordnungen",
                                           solution_pages=[], worked_on_paper=True, teacher_graded=True)):
        reanalysis.reanalyze_material(db_session, mat)
    assert (mat.kind, mat.subject_id, mat.worked_on_paper, mat.teacher_graded) == ("Test", "sub_math", True, True)


def test_chapters_and_timetables_are_skipped(db_session):
    chapter = Material(id="mat_ch", kind="Buchauszug", parent_id="mat_parent", file_path="/tmp/x.pdf")
    plan = Material(id="mat_plan", kind="Stundenplan", file_path="/tmp/y.png")
    with patch.object(reanalysis, "analyze_document_content") as analyze:
        assert reanalysis.reanalyze_material(db_session, chapter) is None
        assert reanalysis.reanalyze_material(db_session, plan) is None
    analyze.assert_not_called()
