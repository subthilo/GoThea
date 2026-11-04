"""Erschlossene Seiten (material_pages, Grundlage für Luna) und die Lösungssperre folgen dem Dokument,
wenn Seiten umsortiert, gelöscht oder Dokumente zusammengeführt werden."""
import io
import json
import os
from pathlib import Path

from pypdf import PdfWriter

from backend.app.models.material import Material
from backend.app.models.material_page import MaterialPage
from backend.app.schemas.material import MaterialConfirmRequest, MaterialMergeRequest
from backend.app.services import material_ingestion, solution_pages
from backend.app.services.page_extraction import content_key, file_sha256


def _material_with_pages(db, texts):
    writer = PdfWriter()
    for i, _ in enumerate(texts):
        writer.add_blank_page(width=100 + i, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    pre = material_ingestion.pre_analyze_upload(db, "blatt.pdf", buf.getvalue(), "application/pdf")
    mat = material_ingestion.confirm_and_save_material(db, MaterialConfirmRequest(
        upload_token=pre.upload_token, subject_id="sub_bio", title="Blatt", kind="Arbeitsblatt"))
    for n, text in enumerate(texts, start=1):
        db.add(MaterialPage(material_id=mat.id, page_number=n, content_key=f"alt_p{n}", text=text))
    db.commit()
    return mat


def _pages(db, material_id):
    rows = db.query(MaterialPage).filter_by(material_id=material_id).order_by(MaterialPage.page_number).all()
    return [(r.page_number, r.text) for r in rows]


def test_reorder_moves_and_drops_extracted_pages(db_session):
    mat = _material_with_pages(db_session, ["A", "B", "C"])
    material_ingestion.reorder_material_pages(db_session, mat.id, [3, 1])
    assert _pages(db_session, mat.id) == [(1, "C"), (2, "A")]
    rows = db_session.query(MaterialPage).filter_by(material_id=mat.id).order_by(MaterialPage.page_number).all()
    path = Path(mat.file_path)
    assert [r.content_key for r in rows] == [content_key(path, 1), content_key(path, 2)]
    assert db_session.get(Material, mat.id).extracted_text == "--- Seite 1 ---\nC\n\n--- Seite 2 ---\nA"


def test_merge_takes_over_extracted_pages_and_queues_the_rest(db_session, monkeypatch):
    from backend.app.services import page_extraction
    queued = []
    monkeypatch.setattr(page_extraction.page_extraction_service, "queue_material", lambda mid, *a, **k: queued.append(mid))
    first = _material_with_pages(db_session, ["A", "B"])
    second = _material_with_pages(db_session, ["C"])
    merged = material_ingestion.merge_materials(db_session, MaterialMergeRequest(
        material_ids=[first.id, second.id], target_title="Zusammen", delete_sources=True))
    assert _pages(db_session, merged.id) == [(1, "A"), (2, "B"), (3, "C")]
    assert db_session.get(Material, first.id) is None and db_session.get(Material, second.id) is None
    assert db_session.query(MaterialPage).filter(MaterialPage.material_id.in_([first.id, second.id])).count() == 0
    assert queued[-1] == merged.id


def _with_solutions(db, texts, solution_pages, kind="Arbeitsblatt", worked=None):
    mat = _material_with_pages(db, texts)
    mat.solution_pages_json = json.dumps(solution_pages) if solution_pages else None
    mat.kind = kind
    mat.worked_on_paper = worked
    db.commit()
    return mat


def test_reorder_keeps_the_solution_lock_on_its_page(db_session):
    # Lösung (S. 2) nach vorn, S. 3 gelöscht: die Sperre muss auf der neuen S. 1 liegen, nicht auf der Aufgabe
    mat = _with_solutions(db_session, ["Aufgabe", "Lösung", "Rest"], [2, 3])
    material_ingestion.reorder_material_pages(db_session, mat.id, [2, 1])
    assert solution_pages.pages(db_session.get(Material, mat.id)) == {1}
    material_ingestion.reorder_material_pages(db_session, mat.id, [2])
    assert db_session.get(Material, mat.id).solution_pages_json is None


def test_merge_keeps_the_solution_locks_of_every_source(db_session, monkeypatch):
    from backend.app.services import page_extraction
    monkeypatch.setattr(page_extraction.page_extraction_service, "queue_material", lambda *a, **k: None)
    sheet = _with_solutions(db_session, ["A", "Lösung A"], [2], worked=True)
    plain = _with_solutions(db_session, ["B"], [])
    key = _with_solutions(db_session, ["L1", "L2"], [], kind="Lösungsblatt")
    merged = material_ingestion.merge_materials(db_session, MaterialMergeRequest(
        material_ids=[sheet.id, plain.id, key.id], target_title="Zusammen", delete_sources=True))
    assert solution_pages.pages(merged) == {2, 4, 5}
    # nur eine Quelle war bearbeitet – das darf die Lösungen der anderen nicht freigeben
    assert not merged.worked_on_paper


def test_file_hash_notices_a_rewrite_within_the_same_second(tmp_path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"eins")
    before = file_sha256(f)
    mtime = f.stat().st_mtime
    f.write_bytes(b"zwei, laenger")
    os.utime(f, (mtime, mtime))
    assert file_sha256(f) != before

