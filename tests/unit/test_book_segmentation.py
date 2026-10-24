from pathlib import Path
import pypdf

from backend.app.models.material import Material
from backend.app.services.book_segmentation import (
    is_candidate_book,
    extract_chapters_from_pdf_outline,
    auto_segment_if_known,
    auto_detect_and_segment_book,
    get_chapter_sections,
    get_all_book_sections,
    FUNDAMENTE_MATHE_7_CHAPTERS,
    PHYSIK_PLUS_7_CHAPTERS,
    DEUTSCHBUCH_7_CHAPTERS,
    DEUTSCHBUCH_AH_7_CHAPTERS
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



def _make_blank_book(db_session, tmp_path, book_id, title, subject_id, pages):
    pdf_path = tmp_path / f"{book_id}.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=300)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    book = Material(
        id=book_id,
        user_id="usr_thea",
        subject_id=subject_id,
        title=title,
        kind="Buch",
        filename=pdf_path.name,
        file_path=str(pdf_path),
        file_size=pdf_path.stat().st_size,
        mime_type="application/pdf",
        page_count=pages,
        start_page=1,
        end_page=pages
    )
    db_session.add(book)
    db_session.commit()
    return book


def test_known_chapter_tables_are_consistent():
    for chapters in (PHYSIK_PLUS_7_CHAPTERS, DEUTSCHBUCH_7_CHAPTERS, DEUTSCHBUCH_AH_7_CHAPTERS):
        prev_end = None
        for chap in chapters:
            start_pdf, end_pdf = chap["start_pdf_page"], chap["end_pdf_page"]
            assert end_pdf - start_pdf == chap["book_end_page"] - chap["book_start_page"]
            if prev_end is not None:
                assert start_pdf == prev_end + 1
            prev_end = end_pdf
            for sec in chap["sections"]:
                assert chap["book_start_page"] <= sec["book_page"] <= chap["book_end_page"]
                assert sec["relative_page"] == sec["book_page"] - chap["book_start_page"] + 1


def test_auto_segment_physik_plus(db_session, tmp_path):
    book = _make_blank_book(db_session, tmp_path, "mat_physik_test", "Physik Plus 7", "sub_math", 108)

    segmented = auto_segment_if_known(db_session, book)
    assert [c.page_count for c in segmented] == [30, 16, 53, 3]
    assert segmented[0].start_page == 5
    assert "Darstellen von Kräften" in segmented[0].toc_json

    # Gesamtbuch-Abschnitte zeigen auf absolute PDF-Seiten
    all_secs = get_all_book_sections(book)
    mechanik = next(s for s in all_secs if s["title"] == "Mechanik")
    assert mechanik["relative_page"] == 7
    federkraft = next(s for s in all_secs if s["title"].startswith("1.2 "))
    assert federkraft["relative_page"] == 10


def test_auto_segment_deutschbuch(db_session, tmp_path):
    book = _make_blank_book(db_session, tmp_path, "mat_deutsch_test", "Deutschbuch 7", "sub_math", 383)

    segmented = auto_segment_if_known(db_session, book)
    assert len(segmented) == len(DEUTSCHBUCH_7_CHAPTERS)
    assert segmented[0].page_count == 24

    secs = get_chapter_sections(segmented[11], parent_book=book)
    assert secs[0]["title"].startswith("12.1 ")


def test_deutsch_workbook_gets_its_own_table_not_the_textbooks(db_session, tmp_path):
    # Der Titel enthält „Deutschbuch“ – früher bekam das Arbeitsheft deshalb die Kapitel des Schülerbuchs
    book = _make_blank_book(db_session, tmp_path, "mat_deutsch_ah", "Deutschbuch Gymnasium Arbeitsheft 7",
                            "sub_math", 108)
    segmented = auto_segment_if_known(db_session, book)
    assert [c.title for c in segmented][1:5] == ["Schreiben", "Lesen – Umgang mit Texten und Medien",
                                                 "Grammatik", "Rechtschreibung"]
    assert sum(c.page_count for c in segmented) == 108
    grammatik = segmented[3]
    assert (grammatik.start_page, grammatik.end_page, grammatik.page_count) == (34, 66, 33)
    assert grammatik.id == "mat_deutsch_ah_ch03"

    secs = get_chapter_sections(grammatik, parent_book=book)
    konjunktiv = next(s for s in secs if s["title"] == "Verben – Konjunktiv")
    assert (konjunktiv["book_page"], konjunktiv["relative_page"]) == (46, 13)

    # Gesamtbuch: Buchseite 4 (Schreiben) ist PDF-Seite 6
    schreiben = next(s for s in get_all_book_sections(book) if s["title"] == "Schreiben")
    assert (schreiben["book_page"], schreiben["relative_page"]) == (4, 6)


def test_resegmenting_moves_extracted_pages_and_notes_with_their_book_page(db_session, tmp_path):
    from backend.app.models.annotation import PageAnnotation
    from backend.app.models.material_page import MaterialPage
    from backend.app.services.book_segmentation import resegment_keeping_pages, segment_book_material

    # So auf Staging: das Arbeitsheft wurde nach der Tabelle des Schülerbuchs eingeteilt
    book = _make_blank_book(db_session, tmp_path, "mat_ah", "Deutschbuch Gymnasium Arbeitsheft 7", "sub_math", 108)
    segment_book_material(db_session, book, DEUTSCHBUCH_7_CHAPTERS)
    # alte „Kapitel 2“ = PDF 40–57: Seite 12 = PDF 51 = Buchseite 49 („Teste dich! Konjunktiv“)
    db_session.add(MaterialPage(material_id="mat_ah_ch02", page_number=12, content_key="alt", text="Konjunktiv-Test"))
    db_session.add(PageAnnotation(id="ann_mat_ah_ch02_p12", material_id="mat_ah_ch02", page_number=12,
                                  strokes_json='[{"x": 1}]'))
    db_session.commit()

    preview = resegment_keeping_pages(db_session, book, DEUTSCHBUCH_7_CHAPTERS, DEUTSCHBUCH_AH_7_CHAPTERS,
                                      dry_run=True)
    assert preview["notizen_ziel"] == [(51, (5, 16))]  # Grammatik (Ordnung 5), Seite 16
    assert db_session.query(MaterialPage).filter_by(material_id="mat_ah_ch02").count() == 1  # Vorschau ändert nichts

    resegment_keeping_pages(db_session, book, DEUTSCHBUCH_7_CHAPTERS, DEUTSCHBUCH_AH_7_CHAPTERS)
    moved = db_session.query(MaterialPage).filter_by(text="Konjunktiv-Test").one()
    assert (moved.material_id, moved.page_number) == ("mat_ah_ch03", 16)
    assert moved.content_key != "alt"
    note = db_session.query(PageAnnotation).one()
    assert (note.id, note.material_id, note.page_number) == ("ann_mat_ah_ch03_p16", "mat_ah_ch03", 16)
    assert "--- Seite 16 ---\nKonjunktiv-Test" in db_session.get(Material, "mat_ah_ch03").extracted_text
    assert db_session.get(Material, "mat_ah_ch02").title == "Lesen – Umgang mit Texten und Medien"


def test_workbook_without_table_is_left_to_the_ai(db_session, tmp_path):
    book = _make_blank_book(db_session, tmp_path, "mat_physik_ah", "Physik plus 7 Arbeitsheft", "sub_math", 40)
    assert auto_segment_if_known(db_session, book) is None
    assert get_all_book_sections(book) == []


def test_force_resegments_existing_chapters(db_session, tmp_path):
    book = _make_blank_book(db_session, tmp_path, "mat_physik_force", "Physik Plus 7", "sub_math", 108)
    first = auto_detect_and_segment_book(db_session, book)
    chap = first[0]

    # Veralteten Stand simulieren (z. B. alte, falsche Kapiteltabelle)
    chap.page_count = 1
    Path(chap.file_path).write_bytes(b"")
    db_session.commit()

    unchanged = auto_detect_and_segment_book(db_session, book)
    assert unchanged[0].page_count == 1

    refreshed = auto_detect_and_segment_book(db_session, book, force=True)
    assert refreshed[0].page_count == 30
    assert len(pypdf.PdfReader(refreshed[0].file_path).pages) == 30


def test_non_book_kinds_are_never_segmented():
    for kind in ("Vokabelliste", "Test", "Klassenarbeit", "Mitschrift", "Hefterseite", "Sonstiges"):
        mat = Material(id="mat_x", kind=kind, mime_type="application/pdf", parent_id=None,
                       page_count=60, title="Vokabelliste Englisch Klasse 7")
        assert is_candidate_book(mat) is False, kind
