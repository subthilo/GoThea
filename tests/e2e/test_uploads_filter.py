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
    app_page.wait_for_selector("#tab-uploads .doc-row", timeout=5000)
    cards = app_page.locator("#uploads-history-list .doc-row")
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


def test_document_row_expands_and_offers_edit(app_page, parent_pin):
    app_page.click("#btn-parent-toggle")
    app_page.fill("#input-parent-pin", parent_pin)
    app_page.click("#btn-submit-parent-pin")
    app_page.wait_for_function("document.body.classList.contains('parent-mode-active')", timeout=5000)
    upload_document(app_page, "Aufklappen QZY", "sub_bio", pages=2, kind="Arbeitsblatt")
    app_page.click('.nav-tab[data-tab="uploads"]')
    app_page.fill("#uploads-filter-input", "qzy")
    row = app_page.locator("#uploads-history-list .doc-row").first
    row.wait_for(timeout=5000)

    # Zugeklappt: Ändern und Reader direkt in der Zeile, Aktionen verborgen
    assert row.locator(".btn-mat-edit").is_visible()
    assert row.locator(".doc-row-open").is_visible()
    assert not row.locator(".btn-mat-reader").is_visible()

    # „Ändern“ öffnet den Dialog, ohne die Zeile aufzuklappen
    row.locator(".btn-mat-edit").click()
    app_page.wait_for_selector("#modal-edit-material", state="visible", timeout=5000)
    assert app_page.input_value("#edit-mat-title") == "Aufklappen QZY"
    app_page.click("#btn-close-edit-material-modal")
    assert "open" not in row.get_attribute("class")

    # Aufklappen zeigt Angaben und Aktionen
    row.locator(".doc-row-name").click()
    assert "open" in row.get_attribute("class")
    assert row.locator(".btn-mat-reader").is_visible()
    assert "Biologie" in row.locator(".doc-row-meta").text_content()
    assert app_page.problems.errors == []
