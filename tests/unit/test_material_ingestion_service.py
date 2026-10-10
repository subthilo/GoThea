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
    assert detect_kind_from_filename_and_text("mathe_test_probe.pdf", "") == "Übungszettel"
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
