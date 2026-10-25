"""Üben, Stufe 0 „Bausteine“: Übung im Browser durchspielen (Antippen, Ziehen, Prüfen)."""


def practice_list(page):
    """Die Liste aller Übungen gibt es nur im Eltern-Modus (Thea bekommt eine Runde: test_practice_round.py)."""
    from tests.e2e.conftest import PARENT_PIN
    from tests.e2e.test_dialogs import _unlock_parent_mode
    page.wait_for_selector('.nav-tab[data-tab="practice"]', state="visible")
    if not page.evaluate("document.body.classList.contains('parent-mode-active')"):
        _unlock_parent_mode(page, PARENT_PIN)
    page.click('.nav-tab[data-tab="practice"]')
    page.wait_for_selector(".practice-node")
    if not page.locator('.practice-filter-btn.active[data-filter="alle"]').count():
        page.click('.practice-filter-btn[data-filter="alle"]')
        page.wait_for_selector('.practice-filter-btn.active[data-filter="alle"]')
    expand_all(page)


def expand_all(page):
    """Baum Fach › Thema › Übung ganz aufklappen (Zeilen entstehen erst beim Aufklappen)."""
    page.wait_for_selector(".practice-node")
    page.evaluate("""() => {
        let head, n = 0;  // begrenzt: klappt ein Knoten nicht auf, hängt der Test nicht
        while (n++ < 500 && (head = document.querySelector('.practice-node:not(.open) > .practice-node-head'))) head.click();
    }""")
    page.wait_for_selector(".practice-row")


def open_practice(page, exercise_id="sa-gummibaerchen"):
    practice_list(page)
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
    practice_list(app_page)
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
    practice_list(app_page)
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
    practice_list(app_page)
    app_page.wait_for_selector('.practice-row[data-id="sa-flugzeug"]')
    with app_page.expect_response(lambda r: r.url.endswith("/api/v1/boards") and r.request.method == "POST") as created:
        app_page.click('.practice-row[data-id="sa-flugzeug"] .practice-dot[data-stage="3"]')
    board = created.value.json()
    assert board["practice_exercise_id"] == "sa-flugzeug" and board["practice_stage"] == 3
    app_page.wait_for_selector("#wb-doc-underlay-img.practice-sheet", state="visible")
    assert app_page.problems.errors == []


def _guided_answer(page, *values):
    """Wie auf dem iPad: Kästchen antippen (nur auswählbar), Zahl mit den Tasten eingeben, prüfen."""
    blanks = page.locator(".gg-step.current .gg-blank")
    assert blanks.count() == len(values)
    for i, v in enumerate(values):
        blanks.nth(i).click()
        for _ in range(len(blanks.nth(i).input_value())):
            page.click('.gg-key[data-key="back"]')
        for ch in v:
            page.click(f'.gg-key[data-key="{ch}"]')
    page.click('[data-action="gg-check"]')


def test_reasoning_path_step_by_step(app_page):
    practice_list(app_page)
    app_page.wait_for_selector('.practice-row[data-id="sa-gummibaerchen"] .practice-dot[data-stage="-1"]')
    app_page.click('.practice-row[data-id="sa-gummibaerchen"] .practice-dot[data-stage="-1"]')
    app_page.wait_for_selector(".gg-step.current")
    assert app_page.locator(".gg-step").count() == 1  # nur der erste Satz

    _guided_answer(app_page, "3")
    assert app_page.locator(".gg-step").count() == 2
    # Fehler markiert nur das Kästchen; danach gibt es einen Tipp
    _guided_answer(app_page, "3", "60")
    assert app_page.locator(".gg-step.current .gg-blank.wrong").count() == 1
    app_page.click('[data-action="gg-tip"]')
    assert "Wie oft passt 50 in 150" in app_page.inner_text(".px-luna")
    _guided_answer(app_page, "3", "50")
    # Nächster Satz nur mit den Zahlentasten (ohne Schreiben): Tippfehler, löschen, richtig
    for key in ("7", "back", "1"):
        app_page.click(f'.gg-key[data-key="{key}"]')
    assert app_page.input_value(".gg-step.current .gg-blank") == "1"
    app_page.click('[data-action="gg-check"]')
    assert app_page.locator(".gg-step").count() == 4
    _guided_answer(app_page, "10")
    _guided_answer(app_page, "10")
    with app_page.expect_response(lambda r: r.url.endswith("/events") and '"richtig"' in (r.request.post_data or "")) as resp:
        _guided_answer(app_page, "10,00")  # Komma und Nullen zählen wie 10
    assert resp.value.json()["solved"] and resp.value.json()["stage"] == -1
    assert "Geschafft" in app_page.inner_text(".px-luna")
    assert app_page.locator(".gg-step.done").count() == 6
    # Weiter mit den Bausteinen (Stufe 0)
    app_page.click('.gg .px-check[data-stage="0"]')
    app_page.wait_for_selector(".px-sheet")
    assert app_page.problems.errors == []


# Schreibt Ziffern als Stift-Striche ins Schreibfeld (Formen aus js/digit_ink.js, leicht schräg)
WRITE_DIGITS_JS = """
(text) => {
  const c = document.querySelector(".gg-write-ink");
  const r = c.getBoundingClientRect();
  let id = 10;
  [...text].forEach((ch, k) => {
    const strokes = DigitInk.SHAPES[ch][0];
    strokes.forEach((s) => {
      const pts = s.points.map((p) => [20 + k * 70 + (p.x * 0.62 + 0.08 * (1 - p.y)) * 90, 20 + p.y * 95]);
      const fire = (type, [x, y]) => c.dispatchEvent(new PointerEvent(type, { pointerId: id, pointerType: "pen",
        pressure: 0.6, isPrimary: true, clientX: r.left + x, clientY: r.top + y, bubbles: true, cancelable: true }));
      fire("pointerdown", pts[0]);
      pts.slice(1).forEach((p) => fire("pointermove", p));
      fire("pointerup", pts[pts.length - 1]);
      id++;
    });
  });
}
"""


def test_scratch_pad_for_written_side_calculations(app_page):
    """Nebenrechnung: Stift-Striche bleiben Striche (keine Erkennung), vorgeschriebene Rechnung je Satz."""
    practice_list(app_page)
    app_page.evaluate("window.openPracticeExercise('sa-muenzrolle', -1)")
    app_page.wait_for_selector(".gg-scratch .gg-write-ink")
    assert app_page.inner_text(".gg-write-print") == ""
    app_page.click('.gg-step.current .gg-blank')
    app_page.evaluate(WRITE_DIGITS_JS, "37")
    app_page.wait_for_timeout(700)  # früher las hier die Erkennung
    assert app_page.input_value(".gg-step.current .gg-blank") == ""
    ink = "document.querySelector('.gg-write-ink').getContext('2d').getImageData(0,0,300,150).data.some(v => v)"
    assert app_page.evaluate(ink) is True
    # Werkzeuge: Breite wählen (gemerkt), Radierer, „Alles löschen“ führt zurück zum Stift
    active = "[...document.querySelectorAll('.gg-scratch-tools .active')].map(b => b.dataset.padTool || b.dataset.padSize)"
    assert app_page.evaluate(active) == ["pen", "4"]
    app_page.click('[data-pad-size="7"]')
    app_page.click('[data-pad-tool="pixel_eraser"]')
    assert app_page.evaluate(active) == ["pixel_eraser", "7"]
    assert app_page.evaluate("localStorage.getItem('gothea.scratchWidth')") == "7"
    app_page.click('.gg-scratch-tools [data-pad="clear"]')
    assert app_page.evaluate(ink) is False
    assert app_page.evaluate(active) == ["pen", "7"]
    app_page.click('[data-pad-size="4"]')
    for values in [("375",), ("10", "5"), ("37,5",), ("3",)]:
        _guided_answer(app_page, *values)
    # Satz mit Nebenrechnung: steht vorgeschrieben in den Kästchen, das Feld ist leer
    assert app_page.locator(".gg-write-print span").count() == len("37,5 · 3")
    assert app_page.evaluate(ink) is False
    _guided_answer(app_page, "112,5")
    assert app_page.inner_text(".gg-write-print") == ""
    assert app_page.problems.errors == []


def test_reasoning_path_with_side_calculation_fits_on_one_screen(app_page):
    for width, height in [(1194, 834), (834, 1194), (1133, 744), (744, 1133)]:
        app_page.set_viewport_size({"width": width, "height": height})
        practice_list(app_page)
        app_page.evaluate("window.openPracticeExercise('sa-muenzrolle', -1)")
        app_page.wait_for_selector(".gg-scratch")
        for values in [("375",), ("10", "5"), ("37,5",), ("3",)]:
            _guided_answer(app_page, *values)
        over = app_page.evaluate("document.scrollingElement.scrollHeight - innerHeight")
        assert over == 0, (width, height)
        assert app_page.locator(".gg-scratch .gg-write-area").bounding_box()["height"] >= 280
        app_page.click('[data-action="back"]')
    assert app_page.problems.errors == []
