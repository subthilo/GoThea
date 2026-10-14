from backend.app.models.annotation import PageAnnotation
from backend.app.models.material import Material

def test_page_annotation_model_creation(db_session):
    mat = db_session.query(Material).first()
    if not mat:
        mat = Material(
            id="mat_annot_test",
            user_id="usr_thea",
            subject_id="sub_math",
            title="Annot Test",
            filename="test.pdf",
            file_path="/tmp/test.pdf",
            page_count=3
        )
        db_session.add(mat)
        db_session.commit()

    ann = PageAnnotation(
        id=f"ann_{mat.id}_p1",
        user_id="usr_thea",
        material_id=mat.id,
        page_number=1,
        strokes_json='[{"tool": "pen", "color": "#000"}]'
    )
    db_session.merge(ann)
    db_session.commit()

    loaded = db_session.query(PageAnnotation).filter_by(material_id=mat.id, page_number=1).first()
    assert loaded is not None
    assert '{"tool": "pen"' in loaded.strokes_json
