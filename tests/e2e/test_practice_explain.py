"""Erklär-Stufe der Sachaufgaben (js/practice_explain.js): Satz für Satz, Leuchten, Abfrage, geschafft."""
from tests.e2e.test_practice import practice_list

EX = "sa-gummibaerchen"


def open_explain(page, exercise_id=EX):
    practice_list(page)
    page.evaluate(f"window.openPracticeExercise('{exercise_id}', -2)")
    page.wait_for_selector(".pe-say")


def _until(page, selector, limit=80):
    """„Weiter“ tippen, bis selector erscheint (springt durch die Sätze, dann durch die Schritte)."""
    for _ in range(limit):
        if page.locator(selector).count():
            return
        page.click('[data-pe="next"]')
    raise AssertionError(f"{selector} kam nicht")


def test_explanation_reads_sentence_by_sentence_and_lights_what_it_talks_about(app_page):
    open_explain(app_page)
    assert app_page.inner_text(".pe-say p") == "Wir lesen zuerst die Aufgabe."
    assert app_page.locator(".pe-display").count() == 0  # nur die Aufgabe ist da
    app_page.click('[data-pe="next"]')
    assert app_page.inner_text(".pe-say p") == "Die Zuordnung ist proportional."
    assert app_page.inner_text(".pe-task mark") == "Die Zuordnung ist proportional."
    # Weiter bis „150 g Gummibärchen kosten 3 €“: Textstelle und beide Tabellenfelder leuchten
    for _ in range(10):
        if app_page.inner_text(".pe-say p") == "150 g Gummibärchen kosten 3 €.":
            break
        app_page.click('[data-pe="next"]')
    marked = " ".join(app_page.locator(".pe-task mark").all_inner_texts())
    assert "150 g Gummibärchen 3 €" in marked
    assert app_page.locator(".pe-cell.lit").all_inner_texts() == ["150", "3"]
    assert app_page.problems.errors == []


def test_quiz_at_the_end_counts_the_stage_as_solved(app_page):
    open_explain(app_page)
    _until(app_page, ".pe-quiz")
    for _ in range(3):
        for i in range(3):
            app_page.click(f'.pe-answer[data-pe-pick="{i}"]')
            if app_page.locator(".pe-answer.ok").count():
                break
        question = app_page.inner_text(".pe-quiz-head")
        app_page.click('[data-pe="next"]')
        if app_page.locator(".pe-done").count():
            break
        if app_page.locator(".pe-quiz-head").count() and app_page.inner_text(".pe-quiz-head") == question:
            app_page.click('[data-pe="next"]')  # Luna las noch: erst gesprungen, jetzt weiter
        if app_page.locator(".pe-done").count():
            break
    app_page.wait_for_selector(".pe-done")
    progress = app_page.evaluate("apiJson('/api/v1/practice/progress')")["progress"]
    assert progress[EX]["-2"]["solved"]
    # Danach geht es mit dem Gedankengang weiter
    app_page.click('.pe-done [data-stage="-1"]')
    app_page.wait_for_selector(".gg-steps")
    assert app_page.problems.errors == []


def test_calculation_task_builds_the_calculation_piece_by_piece(app_page):
    open_explain(app_page, "sa-apfelsaft-flaschen")
    _until(app_page, ".pe-calc")
    assert app_page.locator(".pe-calc span").all_inner_texts() == ["2100 : 0,7"]
    assert app_page.problems.errors == []


def test_explanation_fits_on_one_screen_in_both_orientations(app_page):
    for width, height in [(1194, 834), (834, 1194), (1080, 810), (744, 1133)]:
        app_page.set_viewport_size({"width": width, "height": height})
        open_explain(app_page, "sa-flugzeug")
        _until(app_page, ".pe-card.answer")
        over = app_page.evaluate("document.scrollingElement.scrollHeight - innerHeight")
        assert over <= 0, (width, height, over)
        app_page.click('.px-topbar [data-action="back"]')
    assert app_page.problems.errors == []


def test_physics_explanation_shows_figure_units_and_fits(app_page):
    """Kneifzange (7.11.): die Zahlen stehen nur im Bild – das Bild steht unter der Aufgabe, alles passt."""
    for width, height in [(1194, 834), (834, 1194), (1080, 810), (744, 1133)]:
        app_page.set_viewport_size({"width": width, "height": height})
        open_explain(app_page, "ph-kneifzange")
        app_page.wait_for_function("document.querySelector('.pe-figure img')?.complete")
        assert app_page.evaluate("document.querySelector('.pe-figure img').naturalWidth") > 0
        _until(app_page, ".pe-card.answer")
        over = app_page.evaluate("document.scrollingElement.scrollHeight - innerHeight")
        assert over <= 0, (width, height, over)
        if (width, height) == (1194, 834):
            app_page.screenshot(path="/tmp/pe_kneifzange.png")
        app_page.click('.px-topbar [data-action="back"]')
    open_explain(app_page, "ph-federkonstante")
    _until(app_page, ".pe-calc")
    assert app_page.locator(".pe-calc span").all_inner_texts() == ["1 N : 2 cm"]
    assert app_page.problems.errors == []
