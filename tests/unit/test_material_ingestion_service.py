import pytest
from backend.app.services.material_ingestion import (
    clean_title_from_filename,
    detect_kind_from_filename_and_text,
    chunk_text,
    classify_chunk,
)

def test_clean_title_from_filename():
    assert clean_title_from_filename("bio_pflanzenzelle_01.pdf") == "Bio Pflanzenzelle 01"
    assert clean_title_from_filename("mathe-bruchrechnung.pdf") == "Mathe Bruchrechnung"
    assert clean_title_from_filename("   .pdf") == "Unbenanntes Material"

def test_detect_kind_from_filename_and_text():
    assert detect_kind_from_filename_and_text("hefter_mitschrift.pdf", "") == "Hefterseite"
    assert detect_kind_from_filename_and_text("buch_kapitel_3.pdf", "") == "Buchauszug"
    assert detect_kind_from_filename_and_text("mathe_test_probe.pdf", "") == "Test"
    assert detect_kind_from_filename_and_text("bio_klassenarbeit_1.pdf", "") == "Klassenarbeit"
    assert detect_kind_from_filename_and_text("arbeitsblatt_01.pdf", "") == "Arbeitsblatt"

def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []

def test_chunk_text_and_classification():
    text = (
        "Merke: Eine Pflanze benötigt Licht zur Fotosynthese.\n\n"
        "Aufgabe 1: Zeichne eine Tierzelle und beschrifte die Teile.\n\n"
        "Vokabel: Cell = Zelle."
    )
    chunks = chunk_text(text)
    assert len(chunks) == 3

    assert chunks[0]["chunk_type"] == "rule"
    assert "Fotosynthese" in chunks[0]["content"]

    assert chunks[1]["chunk_type"] == "exercise"
    assert "Aufgabe 1" in chunks[1]["content"]

    assert chunks[2]["chunk_type"] == "vocabulary"
    assert "Cell" in chunks[2]["content"]

def test_pre_analyze_upload_with_subject_hint(db_session):
    from backend.app.services.material_ingestion import pre_analyze_upload
    from backend.app.models.taxonomy import Subject, Topic

    sub_bio = db_session.query(Subject).filter(Subject.name.ilike("%biologie%")).first()
    assert sub_bio is not None

    # Filename suggests math, but subject_id_hint forces Biology
    res = pre_analyze_upload(
        db=db_session,
        filename="mathe_dreiecke_uebung.pdf",
        file_bytes=b"Zellaufbau und Mikroskopieren",
        content_type="application/pdf",
        subject_id_hint=sub_bio.id
    )
    assert res.predicted_subject_id == sub_bio.id
    # Topic should be one from Biology if matched
    if res.predicted_topic_id:
        topic = db_session.query(Topic).filter_by(id=res.predicted_topic_id).first()
        assert topic.subject_id == sub_bio.id
