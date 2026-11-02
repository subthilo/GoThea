"""Thea-Modus: „Üben“ startet eine Runde (Akku-Frage → Aufgaben nacheinander → Geschafft), auch von der Fachseite.

Was dran ist, kommt aus dem Lernplan: hier „Sicherheit im Chemieraum“ auf „gerade dran“ (danach wieder aus,
der Testserver wird geteilt).
"""
import sqlite3

import pytest

from tests.e2e.test_practice_zuordnen import _ensure_chemie

TOPIC = "top_dfbb0dd9"  # Thema der Chemie-Übungen


@pytest.fixture
def chemie_current(server_data_dir):
    _ensure_chemie(server_data_dir)
    db_path = f"{server_data_dir}/app_data.db"
    with sqlite3.connect(db_path) as db:
        db.execute("INSERT OR IGNORE INTO topics (id, subject_id, name, grade_level, created_at) "
                   f"VALUES ('{TOPIC}', 'sub_chemie', 'Sicherheit im Chemieraum', 7, '2026-10-24 12:00:00')")
        db.execute(f"UPDATE topics SET current_since = '2026-10-24 12:00:00' WHERE id = '{TOPIC}'")
    yield
    with sqlite3.connect(db_path) as db:
        db.execute(f"UPDATE topics SET current_since = NULL WHERE id = '{TOPIC}'")


def _open_practice(page):
    page.wait_for_selector('.nav-tab[data-tab="practice"]', state="visible")
    page.click('.nav-tab[data-tab="practice"]')


def _look_at_every_term(page):
    """Stufe „Anschauen“: jede Zeile antippen, dann ist die Aufgabe geschafft."""
    page.wait_for_selector(".zo-slot")
    for slot in page.locator(".zo-slot").all():
        slot.click()


def test_round_leads_through_what_is_due(app_page, chemie_current):
    app_page.reload()  # Punkt am Üben-Symbol wird beim Laden berechnet
    app_page.wait_for_selector('.nav-tab[data-tab="practice"].has-due')
    xp_before = int(app_page.inner_text("#game-total-xp"))
    _open_practice(app_page)
    app_page.click('.pr-battery-btn[data-akku="geht_so"]')
    # Erste Aufgabe: Laborgeräte, Stufe „Anschauen“; Fortschritt 1 von 4; nach dem Lösen nur „Weiter“
    app_page.wait_for_selector(".zo-figure img")
    assert app_page.locator(".px-topbar .pr-dot").count() == 4
    # Die Runde bestimmt die Stufe: nur die aktuelle wird angezeigt, keine Knöpfe zum Springen
    assert app_page.locator(".px-topbar button.px-stage").count() == 0
    assert app_page.locator(".px-topbar .px-stage.active").count() == 1
    _look_at_every_term(app_page)
    assert app_page.locator('[data-action="back"][title="Zur Liste"]').count() == 0
    app_page.click('[data-action="round-next"]')
    # Pause und zurück: weiter mit derselben Aufgabe
    app_page.wait_for_selector(".px-topbar .pr-dot.done")
    app_page.click('.px-topbar [data-action="back"]')
    app_page.click('[data-action="round-resume"]')
    for _ in range(3):  # Laborgeräte 2, Grundregeln, Brenner – alle „Anschauen“
        _look_at_every_term(app_page)
        app_page.click('[data-action="round-next"]')
    app_page.wait_for_selector(".pr-done")
    app_page.click('[data-action="round-home"]')
    app_page.wait_for_selector("#tab-dashboard.active")
    # Punkte auf der Startseite gleich aktuell, nicht erst nach Neustart der App
    app_page.wait_for_function(f"+document.getElementById('game-total-xp').textContent > {xp_before}")
    assert app_page.problems.errors == []


def test_nothing_due_says_so(app_page):
    _open_practice(app_page)
    app_page.click('.pr-battery-btn[data-akku="voll"]')
    app_page.wait_for_selector('[data-action="round-home"]')
    assert app_page.locator(".zo-figure, .px-sheet").count() == 0
    assert app_page.problems.errors == []


def test_subject_page_starts_a_round_for_that_subject(app_page, chemie_current):
    app_page.evaluate("window.startPracticeRound('sub_chemie')")
    app_page.wait_for_selector('.pr-luna:has-text("Chemie")')
    app_page.click('.pr-battery-btn[data-akku="geht_so"]')
    app_page.wait_for_selector(".zo-figure img")
    assert app_page.problems.errors == []


def test_subject_page_replaces_an_open_exercise_of_another_subject(app_page, chemie_current):
    from tests.e2e.test_practice import open_practice
    open_practice(app_page)  # Mathe-Übung offen (Eltern-Liste)
    app_page.evaluate("window.startPracticeRound('sub_chemie')")
    app_page.wait_for_selector('.pr-luna:has-text("Chemie")')
    assert app_page.locator(".px-sheet").count() == 0
    assert app_page.problems.errors == []


def test_parents_see_which_battery_thea_chose(app_page):
    from tests.e2e.test_practice import practice_list
    # Runde im Thea-Modus direkt anfragen (wie der Akku-Knopf): eine laufende Runde ginge sonst vor der Liste
    status = app_page.evaluate("fetch('/api/v1/practice/round?akku=fast_leer').then((r) => r.status)")
    assert status == 200
    practice_list(app_page)
    stat = app_page.locator('.practice-battery-stat[data-akku="fast_leer"]')
    assert int(stat.inner_text()) >= 1  # der Testserver ist geteilt: frühere Runden zählen mit
    assert app_page.problems.errors == []


def test_battery_takes_only_the_first_tap(app_page, chemie_current):
    _open_practice(app_page)
    rounds = []
    app_page.on("request", lambda r: rounds.append(r.url) if "/api/v1/practice/round?akku=" in r.url else None)
    # Wie ein ungeduldiges Tippen auf dem iPad: zweimal hintereinander, noch bevor die Übung steht
    app_page.evaluate("""() => { const b = document.querySelectorAll('.pr-battery-btn');
                                 b[1].click(); b[1].click(); b[2].click(); }""")
    assert app_page.locator(".pr-battery-btn.pressed").count() == 1
    app_page.wait_for_selector(".zo-figure img")
    assert len(rounds) == 1
    assert app_page.problems.errors == []
