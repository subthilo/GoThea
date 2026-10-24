"""Üben, Übungstyp „Ordnen“: Brenner entzünden (Buch S. 22) durchspielen; alles auf einem Bildschirm."""
from tests.e2e.test_practice import practice_list

EX = "ch-brenner-entzuenden"


def open_ordnen(page, stage, exercise=EX):
    practice_list(page)
    page.evaluate(f"window.openPracticeExercise('{exercise}', {stage})")
    page.wait_for_selector(".or-slots")


def steps(page, exercise=EX):
    return page.evaluate(f"apiJson('/api/v1/practice/{exercise}')")["schritte"]


def card(text):
    return f'.or-card[data-card="{text}"]'


def test_look_stage_reveals_steps_in_place(app_page):
    open_ordnen(app_page, -1)
    order = steps(app_page)
    for i in range(len(order)):
        app_page.click(f'.or-slot[data-slot="{i}"]')
    assert app_page.inner_text('.or-slot[data-slot="2"]') == order[2]
    assert "Reihenfolge" in app_page.inner_text(".px-luna")
    assert app_page.problems.errors == []


def test_order_by_tapping_fix_mistakes_and_check(app_page):
    open_ordnen(app_page, 2)
    order = steps(app_page)
    # Zwei vertauscht: Prüfen meldet 2 falsche Plätze
    for text in [order[1], order[0], *order[2:]]:
        app_page.click(card(text))
    app_page.click('[data-action="or-check"]')
    assert app_page.locator(".or-slot.wrong").count() == 2
    assert "2 Schritte" in app_page.inner_text(".px-luna")
    # Platz 1 antippen gibt das Kärtchen zurück; ziehen von Platz 2 auf Platz 1 tauscht
    slot2 = app_page.locator('.or-slot[data-slot="1"]').bounding_box()
    slot1 = app_page.locator('.or-slot[data-slot="0"]').bounding_box()
    app_page.mouse.move(slot2["x"] + 20, slot2["y"] + 10)
    app_page.mouse.down()
    app_page.mouse.move(slot1["x"] + 30, slot1["y"] + 12, steps=8)
    app_page.mouse.up()
    assert app_page.inner_text('.or-slot[data-slot="0"]') == order[0]
    app_page.click('[data-action="or-check"]')
    assert app_page.locator(".or-slot.ok").count() == len(order)
    assert app_page.locator('.px-check[data-stage="3"]').count() == 1
    assert app_page.problems.errors == []


def test_help_stage_fixes_first_and_last_and_distractor_stays(app_page):
    open_ordnen(app_page, 1)
    order = steps(app_page)
    assert app_page.locator(".or-slot.fixed").count() == 2
    assert app_page.locator(".or-card").count() == len(order) - 2
    app_page.evaluate(f"window.openPracticeExercise('{EX}', 3)")
    app_page.wait_for_function("document.querySelectorAll('.or-slot.fixed').length === 0")
    assert app_page.locator(".or-card").count() == len(order) + 2  # zwei Ablenker
    for text in order:
        app_page.click(card(text))
    app_page.click('[data-action="or-check"]')
    assert app_page.locator(".or-slot.ok").count() == len(order)
    assert app_page.locator(".or-card").count() == 2  # die Ablenker bleiben liegen
    assert app_page.problems.errors == []


def test_book_view_shows_the_passage(app_page):
    open_ordnen(app_page, 2)
    app_page.click('[data-action="or-book"]')
    assert "ch-brenner-ablauf_buch.jpg" in app_page.get_attribute(".or-book img", "src")
    app_page.click('[data-action="or-book"]')
    app_page.wait_for_selector(".or-card")
    assert app_page.problems.errors == []


def _overflow(page):
    return page.evaluate("""() => {
        const over = (el) => el ? el.scrollHeight - el.clientHeight : 0;
        return { page: document.scrollingElement.scrollHeight - innerHeight,
                 slots: over(document.querySelector('.or-slots')), pool: over(document.querySelector('.or-pool')) };
    }""")


def test_everything_fits_on_one_screen_in_both_orientations(app_page):
    for width, height in [(1194, 834), (834, 1194), (1133, 744), (744, 1133)]:
        app_page.set_viewport_size({"width": width, "height": height})
        open_ordnen(app_page, 3)
        app_page.click(card(steps(app_page)[0]))
        assert _overflow(app_page) == {"page": 0, "slots": 0, "pool": 0}, (width, height)
        app_page.click('[data-action="back"]')
    assert app_page.problems.errors == []
