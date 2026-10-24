"""Lernplan: Themen eines Tests und „gerade dran“ aus dem Themenkatalog wählen (Eltern-Modus)."""
from tests.e2e.test_dialogs import _unlock_parent_mode


def _planner(page, pin):
    _unlock_parent_mode(page, pin)
    page.click('.nav-tab[data-tab="planner"]')
    page.wait_for_selector("#tab-planner.active")


def test_parents_choose_test_topics_and_change_them(app_page, parent_pin):
    _planner(app_page, parent_pin)
    app_page.click("#btn-open-test-modal")
    app_page.select_option("#input-test-subject", "sub_math")
    app_page.wait_for_selector("#input-test-topics .topic-check")
    app_page.check('#input-test-topics .topic-check:has-text("Rationale Zahlen") input')
    note = "E2E-Themen-Test"
    app_page.fill("#input-test-note", note)
    app_page.click("#btn-submit-test")
    card = app_page.locator(f'.test-card:has-text("{note}")')
    card.wait_for()
    assert card.locator(".topic-chip").all_inner_texts() == ["Rationale Zahlen"]
    # Ändern: zweites Thema dazu, Fach bleibt fest
    card.locator(".btn-edit-test").click()
    app_page.wait_for_selector('#input-test-topics .topic-check:has-text("Rationale Zahlen") input:checked')
    assert app_page.is_disabled("#input-test-subject")
    app_page.check('#input-test-topics .topic-check:has-text("Terme und lineare Gleichungen") input')
    app_page.click("#btn-submit-test")
    app_page.wait_for_function(f"""document.querySelectorAll('.test-card').length &&
        [...document.querySelectorAll('.test-card')].some(c => c.textContent.includes('{note}') && c.querySelectorAll('.topic-chip').length === 2)""")
    # Aufräumen
    app_page.once("dialog", lambda d: d.accept())
    app_page.locator(f'.test-card:has-text("{note}") .btn-del-test[data-id]').click()
    app_page.locator(f'.test-card:has-text("{note}")').wait_for(state="detached")
    assert app_page.problems.errors == []


def test_parents_mark_topics_as_current(app_page, parent_pin):
    _planner(app_page, parent_pin)
    app_page.click("#btn-open-current-topics")
    app_page.select_option("#input-current-subject", "sub_math")
    app_page.wait_for_selector("#input-current-topics .topic-check")
    app_page.check('#input-current-topics .topic-check:has-text("Prozent- und Zinsrechnung") input')
    app_page.click("#btn-submit-current-topics")
    app_page.wait_for_selector('#planner-current-topics .topic-chip:has-text("Prozent- und Zinsrechnung")')
    # Wieder abwählen (der Testserver wird geteilt)
    app_page.click("#btn-open-current-topics")
    app_page.select_option("#input-current-subject", "sub_math")
    app_page.wait_for_selector('#input-current-topics .topic-check:has-text("Prozent- und Zinsrechnung") input:checked')
    app_page.uncheck('#input-current-topics .topic-check:has-text("Prozent- und Zinsrechnung") input')
    app_page.click("#btn-submit-current-topics")
    app_page.locator('#planner-current-topics .topic-chip:has-text("Prozent- und Zinsrechnung")').wait_for(state="detached")
    assert app_page.problems.errors == []
