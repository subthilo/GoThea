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
    _open_practice(app_page)
    app_page.click('.pr-battery-btn[data-akku="geht_so"]')
    # Erste Aufgabe: Laborgeräte, Stufe „Anschauen“; Fortschritt 1 von 2; nach dem Lösen nur „Weiter“
    app_page.wait_for_selector(".zo-figure img")
    assert app_page.locator(".px-topbar .pr-dot").count() == 2
    _look_at_every_term(app_page)
    assert app_page.locator('[data-action="back"][title="Zur Liste"]').count() == 0
    app_page.click('[data-action="round-next"]')
    # Pause und zurück: weiter mit derselben Aufgabe
    app_page.wait_for_selector(".px-topbar .pr-dot.done")
    app_page.click('.px-topbar [data-action="back"]')
    app_page.click('[data-action="round-resume"]')
    _look_at_every_term(app_page)
    app_page.click('[data-action="round-next"]')
    app_page.wait_for_selector(".pr-done")
    app_page.click('[data-action="round-home"]')
    app_page.wait_for_selector("#tab-dashboard.active")
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
