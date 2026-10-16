"""Bücher-Seite als Inhaltsverzeichnis: Buch → Kapitel → Abschnitte (auch verschachtelt) aufklappen,
suchen und eine Stelle direkt im Reader aufschlagen.

Bücher mit Kapiteln entstehen nur durch die Hintergrund-Zerlegung (im Testserver aus), daher liefert der
Browser hier feste API-Antworten für /api/v1/books.
"""
import json
import re

BOOK = {
    "id": "mat_book", "title": "Biosphäre 7/8", "authors": None, "grade_level": 7,
    "subject_id": "sub_bio", "subject_name": "Biologie", "subject_icon": "🌿", "subject_color": "#10b981",
    "total_pages": 60, "chapters_count": 2, "summary": None, "cover_preview_url": None, "segmenting": False,
}


def _chapter(num, start, end, sections):
    cid = f"mat_book_ch{num:02d}"
    return {
        "id": cid, "chapter_number": num, "title": f"Kapitel {num}", "kind": "Buchauszug",
        "topic_id": None, "topic_name": None, "start_page": start, "end_page": end,
        "page_count": end - start + 1, "focus": "", "filename": f"{cid}.pdf", "file_size": 1,
        "file_url": f"/api/v1/materials/{cid}/file", "preview_url": f"/api/v1/materials/{cid}/preview",
        "sections": sections,
    }


DETAIL = {**BOOK, "dossier_id": None, "chapters": [
    _chapter(1, 1, 30, [
        {"title": "1 Lebewesen bestehen aus Zellen", "book_page": 2, "relative_page": 2, "level": 2},
        {"title": "Mikroskopieren", "book_page": 5, "relative_page": 5, "level": 3},
        {"title": "2 Pflanzen", "book_page": 10, "relative_page": 10, "level": 2},
    ]),
    _chapter(2, 31, 60, []),
]}


def _mock_books(page):
    def handle(route):
        body = DETAIL if route.request.url.rstrip("/").endswith("mat_book") else [BOOK]
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
    page.route(re.compile(r".*/api/v1/books(/mat_book)?$"), handle)


def _open_books_tab(page):
    page.evaluate("localStorage.removeItem('gothea_books_open')")
    page.click('.nav-tab[data-tab="books"]')
    page.wait_for_selector(".btree-book-row", timeout=5000)


def test_books_toc_expands_and_opens_nested_section(app_page):
    _mock_books(app_page)
    _open_books_tab(app_page)

    # Einziges Buch ist aufgeklappt, Kapitel sichtbar, Abschnitte noch zu
    app_page.wait_for_selector(".btree-chapter-row", timeout=5000)
    assert app_page.locator(".btree-chapter-row").count() == 2
    assert app_page.locator(".btree-section-row").count() == 0

    # Kapitel 1 aufklappen → oberste Abschnittsebene; Unterpunkt erst nach weiterem Aufklappen
    app_page.click(".btree-chapter-row >> nth=0")
    assert app_page.locator(".btree-section-row").count() == 2
    app_page.click(".btree-node .btree-section-row")
    assert app_page.locator(".btree-subsections .btree-section-row").count() == 1

    # Unterpunkt aufschlagen → Reader auf Seite 5 des Kapitels
    app_page.click(".btree-subsections .btree-section-row")
    app_page.wait_for_selector("#book-reader-view", state="visible", timeout=5000)
    assert app_page.text_content("#reader-page-counter-slim").startswith("Seite 5 von 30")

    # Zurück: Inhaltsverzeichnis bleibt aufgeklappt, gelesenes Kapitel markiert
    app_page.click("#btn-back-to-catalog")
    app_page.wait_for_selector("#book-catalog-view", state="visible", timeout=5000)
    assert app_page.locator(".btree-chapter-row.active").count() == 1
    # Seitenbilder der erfundenen Kapitel gibt es nicht (404) – hier zählen nur JS-Fehler
    assert [e for e in app_page.problems.errors if e.startswith("JS-Fehler")] == []


def test_books_toc_search_shows_matching_section_with_parents(app_page):
    _mock_books(app_page)
    _open_books_tab(app_page)
    app_page.fill("#book-catalog-filter-input", "mikro")
    app_page.wait_for_selector(".btree-subsections .btree-section-row", timeout=5000)
    titles = app_page.locator(".btree-section-title").all_text_contents()
    assert titles == ["1 Lebewesen bestehen aus Zellen", "Mikroskopieren"]

    app_page.fill("#book-catalog-filter-input", "gibt es nicht")
    app_page.wait_for_selector(".btree-empty", timeout=5000)
    assert app_page.problems.errors == []
