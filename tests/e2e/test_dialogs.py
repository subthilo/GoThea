"""Smoke-Test der Dialoge und Unteransichten: Jeder Dialog öffnet und schließt sich ohne JS-Fehler.

Sicherheitsnetz für das Aufteilen des Frontends in mehrere Dateien – Fehler in der Ladereihenfolge
zeigen sich oft erst beim Klick, nicht schon beim Laden der Seite.
"""
import pytest

from tests.e2e.board_helpers import upload_document


def _settle(page):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(200)


def _unlock_parent_mode(page, pin):
    page.click("#btn-parent-toggle")
    page.fill("#input-parent-pin", pin)
    page.click("#btn-submit-parent-pin")
    page.wait_for_function("document.body.classList.contains('parent-mode-active')", timeout=5000)


def _assert_opens_and_closes(page, open_selector, modal_id, close_selector):
    page.click(open_selector)
    page.wait_for_selector(f"#{modal_id}", state="visible", timeout=5000)
    _settle(page)
    page.click(close_selector)
    page.wait_for_selector(f"#{modal_id}", state="hidden", timeout=5000)


def _expand_first_document(page):
    """Dokumentzeilen sind zugeklappt; die Aktionen stehen erst nach dem Aufklappen bereit."""
    row = page.locator("#tab-uploads .doc-row >> nth=0")
    if "open" not in (row.get_attribute("class") or ""):
        row.locator(".doc-row-head").click(position={"x": 30, "y": 20})
    page.wait_for_selector("#tab-uploads .doc-row.open .doc-row-body", state="visible", timeout=5000)


@pytest.fixture
def parent_page(app_page, parent_pin):
    _unlock_parent_mode(app_page, parent_pin)
    return app_page


@pytest.fixture
def uploads_page(parent_page):
    """Uploads-Seite im Eltern-Modus mit (mindestens) einem mehrseitigen Dokument."""
    upload_document(parent_page, "Dialog-Test", "sub_bio", pages=2, kind="Arbeitsblatt")
    parent_page.click('.nav-tab[data-tab="uploads"]')
    parent_page.wait_for_selector("#tab-uploads .doc-row", timeout=5000)
    _settle(parent_page)
    return parent_page


@pytest.mark.parametrize("which", ["test", "block"])
def test_planner_dialogs(parent_page, which):
    parent_page.click('.nav-tab[data-tab="planner"]')
    _settle(parent_page)
    _assert_opens_and_closes(parent_page, f"#btn-open-{which}-modal", f"modal-{which}", f"#btn-close-{which}-modal")
    assert parent_page.problems.errors == []


def test_subject_detail_and_upload_dialog(parent_page):
    parent_page.click("#dashboard-subjects-grid .subject-card >> nth=0")
    parent_page.wait_for_selector("#tab-subject-detail.active", timeout=5000)
    _settle(parent_page)
    _assert_opens_and_closes(parent_page, "#btn-subject-upload-doc", "modal-material", "#btn-close-material-modal")
    _assert_opens_and_closes(parent_page, "#btn-open-subject-merge-modal", "modal-merge-materials", "#btn-close-merge-modal")
    assert parent_page.problems.errors == []


@pytest.mark.parametrize("button, modal_id, close", [
    (".btn-mat-view", "modal-material-viewer", "#btn-close-viewer-modal"),
    (".btn-mat-edit", "modal-edit-material", "#btn-close-edit-material-modal"),
    (".btn-mat-reorder", "modal-reorder-pages", "#btn-close-reorder-modal"),
])
def test_material_card_dialogs(uploads_page, button, modal_id, close):
    _expand_first_document(uploads_page)
    _assert_opens_and_closes(uploads_page, f"#tab-uploads .doc-row >> nth=0 >> {button}", modal_id, close)
    assert uploads_page.problems.errors == []


def test_merge_dialog_from_uploads(uploads_page):
    _assert_opens_and_closes(uploads_page, "#btn-open-uploads-merge-modal", "modal-merge-materials", "#btn-close-merge-modal")
    assert uploads_page.problems.errors == []


def test_document_opens_in_reader(uploads_page):
    uploads_page.click("#tab-uploads .doc-row >> nth=0 >> .doc-row-open")
    uploads_page.wait_for_selector("#tab-books.active", timeout=5000)
    uploads_page.wait_for_selector("#book-reader-view", state="visible", timeout=5000)
    _settle(uploads_page)
    uploads_page.click("#btn-floating-next")
    uploads_page.wait_for_function(
        "document.getElementById('reader-page-counter-slim').textContent.startsWith('Seite 2')", timeout=5000)
    _settle(uploads_page)
    assert uploads_page.problems.errors == []
