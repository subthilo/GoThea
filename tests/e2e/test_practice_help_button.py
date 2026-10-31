"""?-Knopf der Übungen: Anleitung zur Stufe als Text, vorgelesen (js/practice_help.js)."""
from tests.e2e.test_practice import open_practice


def test_help_button_shows_the_instructions_for_this_stage(app_page):
    open_practice(app_page)  # Sachaufgabe, Stufe 0 „Bausteine“
    with app_page.expect_response(lambda r: r.url.endswith("/hilfe/audio/sachaufgabe_0.m4a")) as audio:
        app_page.click(".px-topbar .px-help-btn")
        app_page.wait_for_selector(".px-help")
    assert audio.value.status in (200, 206)
    assert "Zuerst schätzt du" in app_page.inner_text(".px-help")
    # Noch einmal antippen schließt; eine andere Stufe öffnen schließt auch
    app_page.click(".px-topbar .px-help-btn")
    assert app_page.locator(".px-help").count() == 0
    app_page.click(".px-topbar .px-help-btn")
    app_page.wait_for_selector(".px-help")
    app_page.click('.px-stage[data-stage="-1"]')
    app_page.wait_for_selector(".gg-steps")
    assert app_page.locator(".px-help").count() == 0
    app_page.click(".px-topbar .px-help-btn")
    assert "Schritt für Schritt" in app_page.inner_text(".px-help")
    assert app_page.problems.errors == []


def test_practice_board_has_the_help_button_for_its_stage(app_page):
    open_practice(app_page)
    app_page.click('.px-stage[data-stage="3"]')
    app_page.wait_for_selector("#wb-doc-underlay-img.practice-sheet", state="visible")
    app_page.click("#btn-wb-practice-help")
    app_page.wait_for_selector(".px-help")
    assert "R für Rechnung" in app_page.inner_text(".px-help")
    # Normale Tafel: kein ?-Knopf
    app_page.click('.nav-tab[data-tab="dashboard"]')
    assert app_page.locator(".px-help").count() == 0
    assert app_page.problems.errors == []
