"""Dokumentliste unter „Upload“: Suche und Fach-Filter finden ein Dokument schnell wieder.

Der Testserver wird von allen Browser-Tests geteilt – daher eindeutige Titel (Kennung QZX).
"""
from tests.e2e.board_helpers import upload_document


def test_uploads_list_filters_by_subject_and_search(app_page, parent_pin):
    app_page.click("#btn-parent-toggle")
    app_page.fill("#input-parent-pin", parent_pin)
    app_page.click("#btn-submit-parent-pin")
    app_page.wait_for_function("document.body.classList.contains('parent-mode-active')", timeout=5000)
    upload_document(app_page, "Zellen QZX", "sub_bio", pages=1, kind="Arbeitsblatt")
    upload_document(app_page, "Bruchrechnung QZX", "sub_math", pages=1, kind="Test")

    app_page.click('.nav-tab[data-tab="uploads"]')
    app_page.wait_for_selector("#tab-uploads .material-card", timeout=5000)
    cards = app_page.locator("#uploads-history-list .material-card")
    app_page.fill("#uploads-filter-input", "qzx")
    assert cards.count() == 2

    app_page.click(".uploads-subject-pill[data-subject='Biologie']")
    assert cards.count() == 1
    assert "Zellen QZX" in cards.first.text_content()
    assert app_page.text_content("#uploads-history-count").startswith("1 von ")

    # Fach erneut antippen hebt den Filter auf; die Suche wirkt allein
    app_page.click(".uploads-subject-pill[data-subject='Biologie']")
    app_page.fill("#uploads-filter-input", "bruchrechnung qzx")
    assert cards.count() == 1
    assert "Bruchrechnung QZX" in cards.first.text_content()

    app_page.fill("#uploads-filter-input", "gibt es nicht")
    app_page.wait_for_selector(".uploads-filter-empty", timeout=5000)
    assert app_page.problems.errors == []
