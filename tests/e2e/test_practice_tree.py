"""Liste der Eltern: Baum Fach › Thema › Übung, Filter wartend / freigegeben, Freigabe in der App."""
from tests.e2e.test_practice import expand_all, practice_list


def row(ex_id):
    return f'.practice-row[data-id="{ex_id}"]'


def reopen_list(page):
    """Seite neu laden (Liste neu vom Server), Eltern-Modus wieder an, Tab „Üben“ – ohne aufzuklappen."""
    from tests.e2e.conftest import PARENT_PIN
    from tests.e2e.test_dialogs import _unlock_parent_mode
    page.reload()
    page.wait_for_selector('.nav-tab[data-tab="practice"]', state="visible")
    if not page.evaluate("document.body.classList.contains('parent-mode-active')"):
        _unlock_parent_mode(page, PARENT_PIN)
    page.click('.nav-tab[data-tab="practice"]')
    page.wait_for_selector(".practice-node.level-1")


def test_tree_starts_closed_and_opens_subject_and_topic(app_page):
    practice_list(app_page)
    app_page.evaluate("localStorage.removeItem('gothea.practiceOpen')")
    reopen_list(app_page)
    assert app_page.locator(".practice-tree .practice-row").count() == 0          # zugeklappt
    app_page.locator(".practice-node.level-1 > .practice-node-head").first.click()
    assert app_page.locator(".practice-node.level-1.open .practice-node.level-2").count() >= 1
    app_page.locator(".practice-node.level-2 > .practice-node-head").first.click()
    assert app_page.locator(".practice-node.level-2.open .practice-row").count() >= 1
    assert app_page.problems.errors == []


def test_filter_shows_waiting_or_released_only(app_page):
    practice_list(app_page)
    app_page.click('.practice-filter-btn[data-filter="wartend"]')
    app_page.wait_for_selector('.practice-filter-btn.active[data-filter="wartend"]')
    expand_all(app_page)
    assert app_page.locator(".practice-tree .practice-row:not(.practice-draft)").count() == 0
    assert app_page.locator(row("km-messbecher")).count() == 1
    app_page.click('.practice-filter-btn[data-filter="frei"]')
    app_page.wait_for_selector('.practice-filter-btn.active[data-filter="frei"]')
    expand_all(app_page)
    assert app_page.locator(".practice-tree .practice-row.practice-draft").count() == 0
    assert app_page.locator(row("sa-gummibaerchen")).count() == 1
    app_page.click('.practice-filter-btn[data-filter="alle"]')
    assert app_page.problems.errors == []


def test_release_and_withdraw_from_the_list(app_page):
    practice_list(app_page)
    try:
        app_page.click(f'{row("km-messbecher")} .practice-release')
        app_page.wait_for_selector(f'{row("km-messbecher")}:not(.practice-draft)')
        assert app_page.evaluate("apiJson('/api/v1/practice/km-messbecher').then((ex) => ex.status)") == "freigegeben"
    finally:
        app_page.evaluate("apiJson('/api/v1/practice/km-messbecher/freigabe', {method: 'PUT', json: {status: 'entwurf'}})")
    reopen_list(app_page)
    expand_all(app_page)
    assert app_page.locator(f'{row("km-messbecher")}.practice-draft').count() == 1
    assert app_page.problems.errors == []
