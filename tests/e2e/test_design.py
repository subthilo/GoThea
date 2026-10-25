"""Thea wählt ihr Farbschema im Profil per Farbtupfer; die Wahl bleibt nach dem Neuladen, der Eltern-Modus bleibt neutral."""
import pytest

THEME = "document.documentElement.getAttribute('data-theme')"
BG = "getComputedStyle(document.documentElement).getPropertyValue('--bg-primary').trim()"


@pytest.fixture
def reset_theme(app_page):
    yield
    # Der Testserver wird geteilt: andere Tests sollen das Standardschema sehen
    app_page.evaluate("() => apiJson('/api/v1/design/theme', {method: 'PUT', json: {theme: 'indigo'}})")


def test_thea_picks_a_colour_and_it_sticks(app_page, parent_pin, reset_theme):
    app_page.click('.nav-tab[data-tab="profile"]')
    dots = app_page.locator("#theme-dots .theme-dot")
    dots.first.wait_for()
    assert dots.count() >= 10
    assert app_page.evaluate(THEME) == "indigo"
    indigo_bg = app_page.evaluate(BG)

    app_page.click('#theme-dots .theme-dot[data-theme="orange"]')
    app_page.wait_for_function(f"{THEME} === 'orange'")
    assert app_page.evaluate(BG) != indigo_bg
    assert app_page.locator('.theme-dot[data-theme="orange"]').get_attribute("aria-pressed") == "true"
    app_page.wait_for_load_state("networkidle")

    # Ohne Browser-Speicher: die Wahl kommt vom Server
    app_page.evaluate("() => localStorage.removeItem('gothea_theme')")
    app_page.reload()
    app_page.wait_for_function(f"{THEME} === 'orange'", timeout=5000)

    # Eltern-Modus zeigt das neutrale Schema, danach wieder Theas Farbe
    app_page.click("#btn-parent-toggle")
    app_page.fill("#input-parent-pin", parent_pin)
    app_page.click("#btn-submit-parent-pin")
    app_page.wait_for_function(f"{THEME} === 'indigo'", timeout=5000)
    app_page.click("#btn-parent-toggle")
    app_page.wait_for_function(f"{THEME} === 'orange'", timeout=5000)
    assert app_page.problems.errors == []


def test_light_scheme_switches_subject_colours(app_page, parent_pin, reset_theme):
    """Helle Schemen: <html data-theme-kind="light">, Fachfarben aus dem zweiten Satz; Eltern-Modus zurück auf dunkel."""
    kind = "document.documentElement.getAttribute('data-theme-kind')"
    maths = "subjectColor('Mathematik')"
    app_page.click('.nav-tab[data-tab="profile"]')
    app_page.locator('#theme-dots .theme-dot[data-theme="vanille"]').wait_for()
    assert app_page.evaluate(kind) == "dark"
    dark_maths = app_page.evaluate(maths)

    app_page.click('#theme-dots .theme-dot[data-theme="vanille"]')
    app_page.wait_for_function(f"{kind} === 'light'")
    assert app_page.evaluate(maths) != dark_maths
    app_page.click('.nav-tab[data-tab="dashboard"]')
    app_page.wait_for_load_state("networkidle")

    app_page.click("#btn-parent-toggle")
    app_page.fill("#input-parent-pin", parent_pin)
    app_page.click("#btn-submit-parent-pin")
    app_page.wait_for_function(f"{kind} === 'dark'", timeout=5000)
    assert app_page.evaluate(maths) == dark_maths
    app_page.click("#btn-parent-toggle")
    app_page.wait_for_function(f"{kind} === 'light'", timeout=5000)
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []
