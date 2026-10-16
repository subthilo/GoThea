"""Üben, Stufe 0 „Bausteine“: Übung im Browser durchspielen (Antippen, Ziehen, Prüfen)."""


def open_practice(page, exercise_id="sa-gummibaerchen"):
    page.wait_for_selector('.nav-tab[data-tab="practice"]', state="visible")
    page.click('.nav-tab[data-tab="practice"]')
    page.wait_for_selector(".practice-row")
    page.evaluate(f"window.openPracticeExercise('{exercise_id}')")
    page.wait_for_selector(".px-sheet")


def fill(page, slot, token):
    page.click(f'.px-token[data-token="{token}"]')
    page.click(f'.px-slot[data-slot="{slot}"]')


SOLUTION = {
    "op_links_1": ":3", "op_rechts_1": ":3", "op_links_2": "·10", "op_rechts_2": "·10",
    "mitte_links": "50", "mitte_rechts": "1", "ergebnis": "10",
}


def test_practice_tab_lists_exercises(app_page):
    app_page.wait_for_selector('.nav-tab[data-tab="practice"]', state="visible")
    app_page.click('.nav-tab[data-tab="practice"]')
    app_page.wait_for_selector(".practice-row")
    assert app_page.locator(".practice-row").count() >= 7
    assert app_page.problems.errors == []


def test_solve_rule_of_three_by_tapping(app_page):
    open_practice(app_page)
    # Erst die Schätzfrage, vorher sind die Bausteine gesperrt
    assert app_page.locator(".px-token").first.is_disabled()
    app_page.click('.px-guess-btn[data-guess="mehr"]')
    for slot, token in SOLUTION.items():
        fill(app_page, slot, token)
    app_page.click(".px-answer:text-is('500 g Gummibärchen kosten 10 €.')")
    app_page.click('[data-action="check"]')
    assert app_page.locator(".px-slot.ok").count() == len(SOLUTION)
    assert "passt zu deiner Schätzung" in app_page.inner_text(".px-luna")
    assert app_page.problems.errors == []


def test_wrong_result_is_flagged_with_estimate(app_page):
    open_practice(app_page)
    app_page.click('.px-guess-btn[data-guess="mehr"]')
    for slot, token in {**SOLUTION, "ergebnis": "1"}.items():
        fill(app_page, slot, token)
    app_page.click(".px-answer:text-is('500 g Gummibärchen kosten 10 €.')")
    app_page.click('[data-action="check"]')
    assert app_page.locator('.px-slot.wrong[data-slot="ergebnis"]').count() == 1
    luna = app_page.inner_text(".px-luna")
    assert "Du hattest gesagt: mehr als 3 €" in luna
    # Gestufte Hilfe: erster Tipp ist der Denkanstoß
    app_page.click(".px-hint-btn")
    assert "Welcher Wert" in app_page.inner_text(".px-luna")
    assert app_page.problems.errors == []


def test_drag_token_into_slot(app_page):
    open_practice(app_page)
    app_page.click('.px-guess-btn[data-guess="mehr"]')
    token = app_page.locator('.px-token[data-token="50"]').bounding_box()
    target = app_page.locator('.px-slot[data-slot="mitte_links"]').bounding_box()
    app_page.mouse.move(token["x"] + token["width"] / 2, token["y"] + token["height"] / 2)
    app_page.mouse.down()
    app_page.mouse.move(target["x"] + 10, target["y"] + 10, steps=8)
    app_page.mouse.move(target["x"] + target["width"] / 2, target["y"] + target["height"] / 2, steps=4)
    app_page.mouse.up()
    assert app_page.inner_text('.px-slot[data-slot="mitte_links"]') == "50"
    assert app_page.problems.errors == []


def test_division_task_starts_with_estimate_line(app_page):
    open_practice(app_page, "sa-apfelsaft-flaschen")
    assert app_page.locator('.px-slot[data-slot="ueberschlag"]').count() == 1
    # Keine Schätzfrage, der Überschlag übernimmt; Bausteine sofort nutzbar
    assert app_page.locator(".px-guess-btn").count() == 0
    assert not app_page.locator(".px-token").first.is_disabled()
    assert app_page.problems.errors == []
