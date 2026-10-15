"""Verhalten des Upload-Wegs (Web-Upload: Voranalyse + Bestätigung; Inbox; Dokument-Analyse),
festgehalten vor dem Entflechten der langen Funktionen. Die KI ist hier immer ersetzt."""
import io
import json
from unittest.mock import MagicMock, patch

import pytest
from pypdf import PdfWriter

from backend.app.models.dossier import Dossier
from backend.app.models.material import Material, MaterialChunk
from backend.app.schemas.material import MaterialConfirmRequest
from backend.app.services import inbox_service, material_ingestion
from backend.app.services.document_analyzer import DocumentAnalysisResult, analyze_document_content


def _pdf(pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def queued(monkeypatch):
    """Zeichnet auf, was nach dem Speichern an Renderer, Segmentierung und Erschließung geht."""
    calls = {"render": [], "segment": [], "extract": []}
    from backend.app.services import book_segmentation, page_extraction, page_renderer
    monkeypatch.setattr(page_renderer.page_renderer, "queue_material",
                        lambda mid, path, mime, pages, *a, **k: calls["render"].append((mid, pages)))
    monkeypatch.setattr(book_segmentation, "trigger_background_book_segmentation",
                        lambda mid: calls["segment"].append(mid))
    monkeypatch.setattr(page_extraction.page_extraction_service, "queue_material",
                        lambda mid, *a, **k: calls["extract"].append(mid))
    return calls


def _ai_result(**kw):
    base = dict(subject_id="sub_bio", subject_name="Biologie", topic_id=None, topic_name=None, kind="Arbeitsblatt",
                title="KI-Titel", normalized_filename="x.pdf", dossier_title="Mappe", dossier_kind="hefter",
                summary="KI-Zusammenfassung", solution_pages=[2], worked_on_paper=True, teacher_graded=False)
    base.update(kw)
    return DocumentAnalysisResult(**base)


@pytest.fixture
def fake_ai(monkeypatch):
    """Voranalyse mit „KI“: liefert das gesetzte Ergebnis."""
    from backend.app.services import document_analyzer, llm
    holder = {}
    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(document_analyzer, "analyze_document_content", lambda *a, **k: holder["result"])
    return holder


# --- Voranalyse ---------------------------------------------------------------------------------

def test_pre_analysis_heuristic_marks_large_pdfs_as_book(db_session):
    res = material_ingestion.pre_analyze_upload(db_session, "mathe_uebung.pdf", _pdf(20), "application/pdf")
    assert res.predicted_kind == "Buch"
    assert res.page_count == 20


def test_pre_analysis_heuristic_recognises_timetables(db_session):
    res = material_ingestion.pre_analyze_upload(db_session, "stundenplan_7b.pdf", _pdf(), "application/pdf")
    assert res.predicted_kind == "Stundenplan"
    assert res.predicted_subject_id == "sub_orga"
    assert res.predicted_topic_id is None
    assert res.predicted_title == "Stundenplan 7b"  # Titel enthält das Wort schon → kein Präfix
    res2 = material_ingestion.pre_analyze_upload(db_session, "wochen_uebersicht.pdf", _pdf(), "application/pdf")
    assert res2.predicted_kind != "Stundenplan"


def test_pre_analysis_with_ai_passes_signals_and_applies_book_rule(db_session, fake_ai):
    fake_ai["result"] = _ai_result(topic_id="top_x")
    res = material_ingestion.pre_analyze_upload(db_session, "scan.pdf", _pdf(20), "application/pdf")
    assert (res.predicted_subject_id, res.predicted_topic_id, res.predicted_kind) == ("sub_bio", "top_x", "Buch")
    assert res.predicted_title == "KI-Titel"
    assert res.preview_snippet == "KI-Zusammenfassung"
    assert (res.solution_pages, res.worked_on_paper, res.teacher_graded) == ([2], True, False)


def test_pre_analysis_with_ai_keeps_the_fixed_subject(db_session, fake_ai):
    fake_ai["result"] = _ai_result(subject_id="sub_math", topic_id="top_x", kind="Stundenplan")
    res = material_ingestion.pre_analyze_upload(db_session, "notizen.pdf", _pdf(), "application/pdf",
                                                subject_id_hint="sub_bio")
    assert res.predicted_subject_id == "sub_bio"
    assert res.predicted_topic_id is None          # Thema gehört zu einem anderen Fach
    assert res.predicted_kind == "Mitschrift"      # kein Stundenplan über die Fachseite: Art aus dem Dateinamen


# --- Bestätigung --------------------------------------------------------------------------------

def _confirm(db, filename, pages=1, **kw):
    pre = material_ingestion.pre_analyze_upload(db, filename, _pdf(pages), "application/pdf")
    req = dict(upload_token=pre.upload_token, subject_id="sub_bio", topic_id=None, title="Titel", kind="Arbeitsblatt")
    req.update(kw)
    return material_ingestion.confirm_and_save_material(db, MaterialConfirmRequest(**req))


def test_confirm_stores_file_and_queues_rendering_and_extraction(db_session, queued):
    mat = _confirm(db_session, "blatt.pdf", pages=2, solution_pages=[2], worked_on_paper=True)
    assert mat.id.startswith("mat_") and mat.filename == f"{mat.id}.pdf"
    assert mat.mime_type == "application/pdf" and mat.page_count == 2
    assert json.loads(mat.solution_pages_json) == [2] and mat.worked_on_paper is True
    assert queued == {"render": [(mat.id, 2)], "segment": [], "extract": [mat.id]}


def test_confirm_of_a_book_renders_first_pages_and_segments(db_session, queued):
    mat = _confirm(db_session, "buch.pdf", pages=25, kind="Buch", title="Schulbuch")
    assert queued == {"render": [(mat.id, 3)], "segment": [mat.id], "extract": []}


def test_confirm_of_a_timetable_files_it_under_organisation(db_session, queued):
    first = _confirm(db_session, "plan.pdf", kind="Stundenplan", title="Klasse 7b")
    second = _confirm(db_session, "plan2.pdf", kind="Stundenplan", title="Stundenplan neu")
    assert (first.subject_id, first.topic_id, first.kind) == ("sub_orga", None, "Stundenplan")
    assert first.title == "Stundenplan: Klasse 7b" and second.title == "Stundenplan neu"
    dossier = db_session.query(Dossier).filter_by(id=first.dossier_id).one()
    assert dossier.title == "Stundenplan & Organisation" and dossier.subject_id == "sub_orga"
    assert second.dossier_id == first.dossier_id
    assert (first.dossier_order, second.dossier_order) == (1, 2)


def test_confirm_splits_text_into_chunks(db_session, queued, monkeypatch):
    monkeypatch.setattr(material_ingestion, "extract_pdf_data", lambda b: (1, "Merke: Zellen\n\nAufgabe 1: Zeichne?"))
    mat = _confirm(db_session, "blatt.pdf")
    chunks = db_session.query(MaterialChunk).filter_by(material_id=mat.id).order_by(MaterialChunk.chunk_index).all()
    assert [c.chunk_type for c in chunks] == ["rule", "exercise"]
    assert mat.extracted_text.startswith("Merke")


# --- Inbox --------------------------------------------------------------------------------------

def _inbox_file(tmp_path, name, data):
    inbox = tmp_path / "inbox"
    inbox.mkdir(exist_ok=True)
    f = inbox / name
    f.write_bytes(data)
    return f


def test_inbox_large_pdf_becomes_a_book_in_a_textbook_folder(db_session, tmp_path, queued):
    f = _inbox_file(tmp_path, "mathe_buch.pdf", _pdf(25))
    item = inbox_service.process_single_inbox_file(db_session, f, materials_dir=tmp_path / "materials")
    mat = db_session.query(Material).filter_by(id=item.material_id).one()
    assert mat.kind == "Buch"
    dossier = db_session.query(Dossier).filter_by(id=mat.dossier_id).one()
    assert (dossier.title, dossier.kind) == (f"Lehrbuch: {mat.title}", "lehrbuch")
    assert queued == {"render": [(mat.id, 3)], "segment": [mat.id], "extract": []}


def test_inbox_file_gets_chunks_signals_and_extraction(db_session, tmp_path, queued, monkeypatch):
    monkeypatch.setattr(material_ingestion, "extract_pdf_data", lambda b: (2, "Merke: Zellen\n\nAufgabe 1: Zeichne?"))
    monkeypatch.setattr(inbox_service, "analyze_document_content",
                        lambda **k: _ai_result(normalized_filename="Bio_Zellen.pdf"))
    f = _inbox_file(tmp_path, "scan.pdf", _pdf(2))
    item = inbox_service.process_single_inbox_file(db_session, f, materials_dir=tmp_path / "materials")
    mat = db_session.query(Material).filter_by(id=item.material_id).one()
    assert mat.filename == "Bio_Zellen.pdf" and mat.file_path.endswith(f"{mat.id}.pdf")
    assert mat.summary == "KI-Zusammenfassung"
    assert json.loads(mat.solution_pages_json) == [2]
    assert db_session.query(MaterialChunk).filter_by(material_id=mat.id).count() == 2
    assert queued == {"render": [(mat.id, 2)], "segment": [], "extract": [mat.id]}


# --- Dokument-Analyse ---------------------------------------------------------------------------

def _analyze_with_ai(db, tmp_path, payload, filename="scan.pdf", text=""):
    pdf = tmp_path / filename
    pdf.write_bytes(_pdf())
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = json.dumps(payload)
    with patch("backend.app.config.OPENAI_API_KEY", "sk-test"), patch("openai.OpenAI") as cls:
        cls.return_value.chat.completions.create.return_value = response
        return analyze_document_content(db=db, file_path=pdf, extracted_text=text, mime_type="application/pdf")


def test_ai_timetable_goes_to_organisation(db_session, tmp_path):
    res = _analyze_with_ai(db_session, tmp_path, {"dokumentart": "Stundenplan", "inhaltlicher_titel": "Klasse 7b",
                                                 "erkannte_faecher": ["Mathematik"]})
    assert (res.subject_id, res.kind, res.title) == ("sub_orga", "Stundenplan", "Stundenplan: Klasse 7b")
    assert (res.dossier_title, res.dossier_kind) == ("Stundenplan & Organisation", "organisation")
    assert res.normalized_filename == "Organisation_Stundenplan_Stundenplan_Klasse_7b.pdf"
    assert res.summary == "Stundenplan mit 1 erkannten Schulfächern."


def test_ai_subject_alias_is_mapped(db_session, tmp_path):
    res = _analyze_with_ai(db_session, tmp_path, {"fach": "Erdkunde", "dokumentart": "Arbeitsblatt",
                                                 "inhaltlicher_titel": "Vulkane"})
    assert res.subject_id == "sub_geo"
    assert res.normalized_filename.startswith("Geografie_") and res.normalized_filename.endswith("_Arbeitsblatt_Vulkane.pdf")


def test_heuristic_timetable_goes_to_organisation(db_session, tmp_path):
    pdf = tmp_path / "stundenplan_7b.pdf"
    pdf.write_bytes(_pdf())
    res = analyze_document_content(db=db_session, file_path=pdf, extracted_text="", mime_type="application/pdf")
    assert (res.subject_id, res.kind, res.topic_name) == ("sub_orga", "Stundenplan", "Stundenplan")
    assert res.normalized_filename.startswith("Organisation_Stundenplan_") and res.normalized_filename.endswith(".pdf")
    assert res.dossier_title == "Stundenplan & Organisation"
