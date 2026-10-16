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
    # Die Prüfung landet als Versuch im Lernstand
    with app_page.expect_response(lambda r: r.url.endswith("/events") and '"check"' in (r.request.post_data or "")) as resp:
        app_page.click('[data-action="check"]')
    attempt = resp.value.json()
    assert resp.value.status == 200 and attempt["solved"] and attempt["stage"] == 0
    assert app_page.locator(".px-slot.ok").count() == len(SOLUTION)
    assert "passt zu deiner Schätzung" in app_page.inner_text(".px-luna")
    progress = app_page.evaluate("apiJson('/api/v1/practice/progress')")["progress"]
    assert progress["sa-gummibaerchen"]["0"]["solved"]
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


def test_reasoning_task_needs_a_chosen_reasoning(app_page):
    open_practice(app_page, "sa-flugzeug")
    app_page.click('.px-guess-btn[data-guess="weniger"]')
    for slot, token in {"op_links_1": ":6", "op_rechts_1": ":6", "op_links_2": "·5", "op_rechts_2": "·5",
                        "mitte_links": "0,5", "mitte_rechts": "440", "ergebnis": "2200"}.items():
        fill(app_page, slot, token)
    app_page.click(".px-answer:text-is('In 2,5 Stunden fliegt das Flugzeug 2200 km.')")
    # Ohne Begründung lässt sich nicht prüfen
    assert app_page.locator('[data-action="check"]').is_disabled()
    app_page.click(".px-answer:text-is('Je länger das Flugzeug fliegt, desto weiter kommt es.')")
    app_page.click('[data-action="check"]')
    assert "„Je mehr, desto mehr“ reicht nicht" in app_page.inner_text(".px-luna")
    app_page.click(".px-answer:has-text('In der doppelten Zeit')")
    app_page.click('[data-action="check"]')
    assert "Richtig" in app_page.inner_text(".px-luna")
    assert app_page.problems.errors == []


def test_stage_opens_sheet_on_new_board_with_solution_toggle(app_page):
    from tests.e2e.board_helpers import _draw_and_capture_save, _line
    open_practice(app_page)
    with app_page.expect_response(lambda r: r.url.endswith("/api/v1/boards") and r.request.method == "POST") as created:
        app_page.click('.px-stage[data-stage="2"]')
    board = created.value.json()
    assert board["practice_exercise_id"] == "sa-gummibaerchen" and board["practice_stage"] == 2
    app_page.wait_for_function(f"document.getElementById('wb-viewport').dataset.boardId === '{board['id']}'")
    app_page.wait_for_selector("#wb-doc-underlay-img.practice-sheet", state="visible")
    assert app_page.get_attribute("#wb-doc-underlay-img", "src").startswith("data:image/png")
    assert "Stufe 2" in app_page.inner_text("#wb-board-title")

    # Lösung ein- und ausblenden ändert das Blatt
    plain = app_page.get_attribute("#wb-doc-underlay-img", "src")
    app_page.click("#btn-wb-practice-solution")
    assert app_page.get_attribute("#wb-doc-underlay-img", "src") != plain
    app_page.click("#btn-wb-practice-solution")
    assert app_page.get_attribute("#wb-doc-underlay-img", "src") == plain

    # Schreiben wird gespeichert wie auf jeder Tafel
    strokes = _draw_and_capture_save(app_page, _line(100, 420, 300, 430))
    assert len(strokes) == 1

    # Neue freie Tafel: kein Blatt, kein Lösungsknopf
    app_page.evaluate("window.openNewBoardOnWhiteboard('sub_math')")
    app_page.wait_for_function("!document.getElementById('wb-doc-underlay-img').classList.contains('practice-sheet')")
    assert not app_page.is_visible("#btn-wb-practice-solution")

    # Übungstafel wieder öffnen: das Blatt ist wieder da
    app_page.evaluate(f"window.openBoardOnWhiteboard('{board['id']}')")
    app_page.wait_for_selector("#wb-doc-underlay-img.practice-sheet", state="visible")
    assert app_page.problems.errors == []


def _open_practice_board(page, stage=1):
    """Öffnet die Übung auf einer neuen Tafel und wartet, bis genau diese Tafel samt Blatt offen ist
    (beim Laden öffnet die Tafel sonst noch die zuletzt benutzte, evtl. eine Übungstafel eines anderen Tests)."""
    open_practice(page)
    with page.expect_response(lambda r: r.url.endswith("/api/v1/boards") and r.request.method == "POST") as created:
        page.click(f'.px-stage[data-stage="{stage}"]')
    board_id = created.value.json()["id"]
    page.wait_for_function(f"document.getElementById('wb-viewport').dataset.boardId === '{board_id}'")
    page.wait_for_selector("#wb-doc-underlay-img.practice-sheet", state="visible")
    return board_id


def _fake_check(page, body):
    import json
    page.route("**/api/v1/practice/*/check",
               lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(body)))


def test_check_marks_error_and_mark_leaves_when_written_over(app_page):
    from tests.e2e.board_helpers import _draw_and_capture_save, _line
    _open_practice_board(app_page)
    _draw_and_capture_save(app_page, _line(120, 300, 220, 310))
    _fake_check(app_page, {"status": "noch_nicht", "text": "Beim Ergebnis lese ich 1. Das stimmt noch nicht.",
                           "probleme": [], "gelesen": {}, "audio_base64": None,
                           "actions": [{"action": "highlight_box", "coords": {"x_pct": 10, "y_pct": 10, "w_pct": 30, "h_pct": 20}}]})
    app_page.click("#btn-wb-request-hint")
    app_page.wait_for_selector(".wb-luna-mark.wb-luna-box")
    assert "lese ich 1" in app_page.inner_text("#wb-tutor-speech-text")
    assert not app_page.is_visible(".wb-practice-done")
    # Schreiben in den Kasten lässt ihn verschwinden
    box = app_page.locator(".wb-luna-box").bounding_box()
    canvas = app_page.locator("#wb-canvas").bounding_box()
    x, y = box["x"] - canvas["x"] + box["width"] / 2, box["y"] - canvas["y"] + box["height"] / 2
    _draw_and_capture_save(app_page, _line(x - 20, y, x + 20, y + 5))
    assert app_page.locator(".wb-luna-mark").count() == 0
    assert app_page.problems.errors == []


def test_correct_check_offers_next_stage_and_twin(app_page):
    from tests.e2e.board_helpers import _draw_and_capture_save, _line
    _open_practice_board(app_page)
    _draw_and_capture_save(app_page, _line(120, 300, 220, 310))
    _fake_check(app_page, {"status": "richtig", "text": "Richtig! Alles stimmt.", "probleme": [], "gelesen": {},
                           "actions": [], "audio_base64": None})
    app_page.click("#btn-wb-request-hint")
    app_page.wait_for_selector(".wb-practice-done", state="visible")
    best = app_page.locator(".wb-practice-done-btn.best")
    assert best.get_attribute("title") == "Weiter mit Stufe 2"  # auf Anhieb richtig → nächste Stufe
    assert app_page.locator('.wb-practice-done-btn[title="Ähnliche Aufgabe"]').count() == 1
    with app_page.expect_response(lambda r: r.url.endswith("/api/v1/boards") and r.request.method == "POST") as created:
        best.click()
    assert created.value.json()["practice_stage"] == 2
    app_page.wait_for_function("document.getElementById('wb-board-title').textContent.includes('Stufe 2')")
    assert not app_page.is_visible(".wb-practice-done")
    assert app_page.problems.errors == []


def test_list_shows_suggestion_and_marks_solved_stage(app_page):
    app_page.wait_for_selector('.nav-tab[data-tab="practice"]', state="visible")
    app_page.click('.nav-tab[data-tab="practice"]')
    app_page.wait_for_selector(".practice-suggest")
    assert app_page.locator(".practice-group-title").count() >= 2  # nach Abschnitt gruppiert
    # Stufe 0 lösen, zurück zur Liste: Punkt 0 ist gefüllt
    open_practice(app_page)
    app_page.click('.px-guess-btn[data-guess="mehr"]')
    for slot, token in SOLUTION.items():
        fill(app_page, slot, token)
    app_page.click(".px-answer:text-is('500 g Gummibärchen kosten 10 €.')")
    with app_page.expect_response(lambda r: r.url.endswith("/events") and '"check"' in (r.request.post_data or "")):
        app_page.click('[data-action="check"]')
    app_page.click('.px-topbar [data-action="back"]')
    app_page.wait_for_selector('.practice-row[data-id="sa-gummibaerchen"] .practice-dot.done[data-stage="0"]')
    assert app_page.problems.errors == []


def test_stage_dot_opens_practice_board(app_page):
    app_page.wait_for_selector('.nav-tab[data-tab="practice"]', state="visible")
    app_page.click('.nav-tab[data-tab="practice"]')
    app_page.wait_for_selector('.practice-row[data-id="sa-flugzeug"]')
    with app_page.expect_response(lambda r: r.url.endswith("/api/v1/boards") and r.request.method == "POST") as created:
        app_page.click('.practice-row[data-id="sa-flugzeug"] .practice-dot[data-stage="3"]')
    board = created.value.json()
    assert board["practice_exercise_id"] == "sa-flugzeug" and board["practice_stage"] == 3
    app_page.wait_for_selector("#wb-doc-underlay-img.practice-sheet", state="visible")
    assert app_page.problems.errors == []
