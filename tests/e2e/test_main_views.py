"""Smoke-Test der Hauptansichten: Jede Ansicht öffnet sich ohne JS-Fehler und ohne fehlgeschlagene API-Aufrufe."""
import pytest

MAIN_TABS = ["dashboard", "timetable", "books", "whiteboard", "practice", "planner", "uploads", "profile"]


def test_start_page_loads_without_errors(app_page):
    assert app_page.locator("#tab-dashboard").get_attribute("class").split().count("active") == 1
    assert app_page.problems.errors == []


@pytest.mark.parametrize("tab", MAIN_TABS)
def test_main_tab_opens_without_errors(app_page, tab):
    app_page.click(f'.nav-tab[data-tab="{tab}"]')
    app_page.wait_for_load_state("networkidle")
    pane = app_page.locator(f"#tab-{tab}")
    assert "active" in pane.get_attribute("class").split()
    assert pane.is_visible()
    assert app_page.problems.errors == []


def test_parent_mode_unlocks_with_pin(app_page, parent_pin):
    app_page.click("#btn-parent-toggle")
    app_page.fill("#input-parent-pin", parent_pin)
    app_page.click("#btn-submit-parent-pin")
    app_page.wait_for_function("document.body.classList.contains('parent-mode-active')", timeout=5000)
    assert app_page.problems.errors == []


def test_api_helper_sends_parent_token_only_in_parent_mode(app_page, parent_pin):
    status_js = "() => apiJson('/api/v1/auth/parent/status').then(d => d.is_parent)"
    assert app_page.evaluate(status_js) is False
    app_page.click("#btn-parent-toggle")
    app_page.fill("#input-parent-pin", parent_pin)
    app_page.click("#btn-submit-parent-pin")
    app_page.wait_for_function("document.body.classList.contains('parent-mode-active')", timeout=5000)
    assert app_page.evaluate(status_js) is True
    assert app_page.problems.errors == []
