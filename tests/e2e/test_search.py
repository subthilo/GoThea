"""Lupe: Suche in den Unterlagen, ein Treffer öffnet die Seite im Leser; Lösungen bleiben für Thea verborgen."""
import os
import sqlite3

from tests.e2e.board_helpers import upload_document


def _add_extracted_pages(data_dir, material_id, texts, solution_pages=()):
    """Wie die Seiten-Erschließung: Zeilen in material_pages (die Trigger füllen den Suchindex)."""
    with sqlite3.connect(os.path.join(data_dir, "app_data.db")) as con:
        for n, body in enumerate(texts, start=1):
            con.execute(
                "INSERT INTO material_pages (id, material_id, page_number, content_key, text, is_solution_page) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (f"pg_{material_id}_{n}", material_id, n, f"k{n}", body, n in solution_pages))


def test_search_opens_the_page_in_the_reader(app_page, server_data_dir):
    mat_id = upload_document(app_page, "Physik Hefter", "sub_physics", pages=3)
    _add_extracted_pages(server_data_dir, mat_id, ["Kraftpfeile zeichnen", "Das Hookesche Gesetz: F = D · s",
                                                   "Lösung: Hookesches Gesetz bestätigt"], solution_pages=(3,))
    app_page.click("#btn-open-search")
    app_page.fill("#input-search", "Hookesche")
    app_page.wait_for_selector("#search-results .search-hit", timeout=5000)
    hits = app_page.locator("#search-results .search-hit")
    assert hits.count() == 1  # die Lösungsseite fehlt für Thea
    assert "Seite 2" in hits.first.inner_text()
    assert app_page.locator("#search-results mark").first.inner_text() == "Hookesche"

    hits.first.click()
    app_page.wait_for_selector("#book-reader-view", state="visible", timeout=5000)
    app_page.wait_for_function(
        "document.getElementById('reader-page-counter-slim').textContent.startsWith('Seite 2')", timeout=5000)
    assert app_page.locator("#reader-chapter-title-slim").inner_text() == "Physik Hefter"
    assert app_page.locator("#reader-search-hint").is_visible()
    assert app_page.problems.errors == []


def test_search_without_hits_says_so(app_page):
    app_page.click("#btn-open-search")
    app_page.fill("#input-search", "Quantenchromodynamik")
    app_page.wait_for_function("document.getElementById('search-status').textContent.startsWith('Nichts gefunden')",
                               timeout=5000)
    app_page.keyboard.press("Escape")
    app_page.wait_for_selector("#modal-search", state="hidden", timeout=5000)
    assert app_page.problems.errors == []
