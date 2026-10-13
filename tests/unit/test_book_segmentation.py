import os
import tempfile
from pathlib import Path
import pypdf
import pytest
from sqlalchemy.orm import Session

from backend.app.models.material import Material
from backend.app.services.book_segmentation import (
    is_candidate_book,
    extract_chapters_from_pdf_outline,
    auto_segment_if_known,
    auto_detect_and_segment_book,
    segment_book_material,
    trigger_background_book_segmentation,
    FUNDAMENTE_MATHE_7_CHAPTERS
)

def test_is_candidate_book():
    # 1. Direkt als Buch deklariert
    mat_book = Material(
        id="mat_b1",
        kind="Buch",
        mime_type="application/pdf",
        parent_id=None,
        page_count=50,
        title="Biologie 7"
    )
    assert is_candidate_book(mat_book) is True

    # 2. Großes Dokument mit Schulbuch-Keywords
    mat_kw = Material(
        id="mat_b2",
        kind="Arbeitsblatt",
        mime_type="application/pdf",
        parent_id=None,
        page_count=25,
        title="Cornelsen Mathematik Schulbuch Klasse 7"
    )
    assert is_candidate_book(mat_kw) is True

    # 3. Sehr langes PDF (>= 30 Seiten)
    mat_long = Material(
        id="mat_b3",
        kind="Arbeitsblatt",
        mime_type="application/pdf",
        parent_id=None,
        page_count=45,
        title="Dokumentensammlung"
    )
    assert is_candidate_book(mat_long) is True

    # 4. Kein Buch (z. B. Einzelbild oder kurzes Arbeitsblatt)
    mat_sheet = Material(
        id="mat_s1",
        kind="Arbeitsblatt",
        mime_type="application/pdf",
        parent_id=None,
        page_count=2,
        title="Übung Dreisatz"
    )
    assert is_candidate_book(mat_sheet) is False

    # 5. Child-Material (bereits ein Kapitel)
    mat_child = Material(
        id="mat_c1",
        kind="Buchauszug",
        mime_type="application/pdf",
        parent_id="mat_b1",
        page_count=20,
        title="Kapitel 1"
    )
    assert is_candidate_book(mat_child) is False


def test_extract_chapters_from_pdf_outline(tmp_path):
    # Erstelle eine temporäre PDF-Datei mit Lesezeichen / Bookmarks
    pdf_path = tmp_path / "test_book_with_outline.pdf"
    writer = pypdf.PdfWriter()

    # 10 leere Seiten hinzufügen
    for _ in range(10):
        writer.add_blank_page(width=200, height=300)

    # Lesezeichen / Bookmarks einfügen:
    # Kapitel 1 auf PDF-Seite 1 (Index 0)
    # Kapitel 2 auf PDF-Seite 6 (Index 5)
    writer.add_outline_item("Kapitel 1: Grundlagen", page_number=0)
    writer.add_outline_item("Kapitel 2: Vertiefung", page_number=5)

    with open(pdf_path, "wb") as f:
        writer.write(f)

    chapters = extract_chapters_from_pdf_outline(pdf_path, total_pages=10)
    assert len(chapters) == 2

    ch1 = chapters[0]
    assert ch1["unit_number"] == 1
    assert ch1["title"] == "Kapitel 1: Grundlagen"
    assert ch1["start_pdf_page"] == 1
    assert ch1["end_pdf_page"] == 5

    ch2 = chapters[1]
    assert ch2["unit_number"] == 2
    assert ch2["title"] == "Kapitel 2: Vertiefung"
    assert ch2["start_pdf_page"] == 6
    assert ch2["end_pdf_page"] == 10


def test_auto_detect_and_segment_book_with_outline(db_session, tmp_path):
    pdf_path = tmp_path / "digital_textbook.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(12):
        writer.add_blank_page(width=200, height=300)
    writer.add_outline_item("Unit 1: Hello World", page_number=0)
    writer.add_outline_item("Unit 2: Next Steps", page_number=4)
    writer.add_outline_item("Unit 3: Final Project", page_number=8)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    book = Material(
        id="mat_test_book_outline",
        user_id="usr_thea",
        subject_id="sub_english",
        title="English Textbook Class 7",
        kind="Buch",
        filename="digital_textbook.pdf",
        file_path=str(pdf_path),
        file_size=pdf_path.stat().st_size,
        mime_type="application/pdf",
        page_count=12,
        start_page=1,
        end_page=12
    )
    db_session.add(book)
    db_session.commit()

    # Automatische Segmentierung ausführen
    result = auto_detect_and_segment_book(db_session, book)
    assert result is not None
    assert len(result) == 3

    # Überprüfe die generierten Child-Materialien
    children = db_session.query(Material).filter_by(parent_id=book.id).order_by(Material.dossier_order).all()
    assert len(children) == 3

    assert children[0].title == "Unit 1: Hello World"
    assert children[0].start_page == 1
    assert children[0].end_page == 4
    assert children[0].page_count == 4

    assert children[1].title == "Unit 2: Next Steps"
    assert children[1].start_page == 5
    assert children[1].end_page == 8
    assert children[1].page_count == 4

    assert children[2].title == "Unit 3: Final Project"
    assert children[2].start_page == 9
    assert children[2].end_page == 12
    assert children[2].page_count == 4


def test_auto_segment_if_known(db_session, tmp_path):
    pdf_path = tmp_path / "fundamente.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(304):
        writer.add_blank_page(width=200, height=300)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    fundamente_book = Material(
        id="mat_fundamente_test",
        user_id="usr_thea",
        subject_id="sub_math",
        title="Fundamente der Mathematik 7",
        kind="Buch",
        filename="fundamente.pdf",
        file_path=str(pdf_path),
        file_size=pdf_path.stat().st_size,
        mime_type="application/pdf",
        page_count=304,
        start_page=1,
        end_page=304
    )
    db_session.add(fundamente_book)
    db_session.commit()

    segmented = auto_segment_if_known(db_session, fundamente_book)
    assert segmented is not None
    assert len(segmented) == len(FUNDAMENTE_MATHE_7_CHAPTERS)
    assert "Kapitel 1: Zuordnungen" in segmented[1].title
    # Sicherstellen, dass toc_json gespeichert wurde
    assert segmented[1].toc_json is not None
    assert "1.1 Zuordnungen" in segmented[1].toc_json


def test_get_chapter_sections_and_fallback(db_session):
    from backend.app.services.book_segmentation import get_chapter_sections, get_all_book_sections

    book = Material(
        id="mat_fundamente_sample",
        title="Fundamente der Mathematik 7",
        kind="Buch",
        page_count=304,
        start_page=1,
        end_page=304
    )

    chap1 = Material(
        id="mat_fundamente_sample_ch01",
        title="Kapitel 1: Zuordnungen und Proportionalität",
        kind="Buchauszug",
        start_page=11,
        end_page=42,
        page_count=32,
        dossier_order=3,
        parent_id=book.id
    )

    # 1. Fallback für Fundamente der Mathematik Kapitel 1
    secs = get_chapter_sections(chap1, parent_book=book)
    assert len(secs) >= 5
    assert secs[1]["title"] == "1.1 Zuordnungen"
    assert secs[1]["book_page"] == 14
    assert secs[1]["relative_page"] == 4

    # 2. Alle Abschnitte für Gesamtbuch
    all_secs = get_all_book_sections(book)
    assert len(all_secs) > 30
    assert any(s["title"] == "1.1 Zuordnungen" for s in all_secs)


def test_outline_with_nested_sections(tmp_path):
    pdf_path = tmp_path / "book_with_nested_outline.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(20):
        writer.add_blank_page(width=200, height=300)

    # Kapitel 1 (Seite 1) mit Unterabschnitten (Seite 3 und 5)
    writer.add_outline_item("Kapitel 1", page_number=0)
    writer.add_outline_item("1.1 Unterthema A", page_number=2)
    writer.add_outline_item("1.2 Unterthema B", page_number=4)
    # Kapitel 2 (Seite 10)
    writer.add_outline_item("Kapitel 2", page_number=9)
    writer.add_outline_item("2.1 Unterthema C", page_number=12)

    with open(pdf_path, "wb") as f:
        writer.write(f)

    chaps = extract_chapters_from_pdf_outline(pdf_path, total_pages=20)
    assert len(chaps) >= 2
    # Jedes Kapitel oder Bookmark wurde erfasst
    assert any("Kapitel 1" in c["title"] for c in chaps)

