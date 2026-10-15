"""Dokumente mit erschlossenen Seiten und Notizen lassen sich löschen (auch beim Zusammenführen)."""
from backend.app.models.annotation import PageAnnotation
from backend.app.models.material import Material
from backend.app.models.material_page import MaterialPage
from backend.app.schemas.material import MaterialMergeRequest
from backend.app.services import material_ingestion
from tests.unit.test_page_content_follows_edits import _material_with_pages


def test_deleting_a_document_removes_its_pages_and_notes(client, db_session):
    mat = _material_with_pages(db_session, ["A", "B"])
    db_session.add(PageAnnotation(id=f"ann_{mat.id}_p1", material_id=mat.id, page_number=1, strokes_json="[]"))
    db_session.commit()
    assert client.delete(f"/api/v1/materials/{mat.id}").status_code == 204
    assert db_session.query(MaterialPage).filter_by(material_id=mat.id).count() == 0
    assert db_session.query(PageAnnotation).filter_by(material_id=mat.id).count() == 0


def test_merging_with_source_deletion_works_for_extracted_documents(db_session):
    first = _material_with_pages(db_session, ["A"])
    second = _material_with_pages(db_session, ["B"])
    material_ingestion.merge_materials(db_session, MaterialMergeRequest(material_ids=[first.id, second.id]))
    assert db_session.get(Material, first.id) is None and db_session.get(Material, second.id) is None
