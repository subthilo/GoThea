"""Üben, Übungstyp „Schubladen“: Reinstoffe und Stoffgemische (Buch S. 19 Nr. 1) durchspielen; ein Bildschirm."""
from tests.e2e.test_practice import practice_list

EX = "ch-reinstoffe-gemische"


def open_sb(page, stage):
    practice_list(page)
    page.evaluate(f"window.openPracticeExercise('{EX}', {stage})")
    page.wait_for_selector(".sb-drawers")


def data(page):
    return page.evaluate(f"apiJson('/api/v1/practice/{EX}')")


def chip(term):
    return f'.sb-chip[data-term="{term}"]'


def drawer(i):
    return f'.sb-drawer[data-drawer="{i}"]'


def test_look_stage_reveals_drawers(app_page):
    open_sb(app_page, -1)
    groups = data(app_page)["gruppen"]
    for i in range(len(groups)):
        app_page.click(drawer(i))
    assert app_page.locator(f"{drawer(0)} .sb-chip").count() == len(groups[0]["begriffe"])
    assert "Schubladen" in app_page.inner_text(".px-luna")
    assert app_page.problems.errors == []


def test_sort_by_tapping_and_dragging_then_fix_and_check(app_page):
    open_sb(app_page, 2)
    groups = data(app_page)["gruppen"]
    items = [(t, gi) for gi, g in enumerate(groups) for t in g["begriffe"]]
    # Erstes Kärtchen per Ziehen, eines absichtlich falsch, der Rest per Antippen
    first, gi0 = items[0]
    box = app_page.locator(chip(first)).bounding_box()
    target = app_page.locator(drawer(gi0)).bounding_box()
    app_page.mouse.move(box["x"] + 10, box["y"] + 10)
    app_page.mouse.down()
    app_page.mouse.move(target["x"] + 40, target["y"] + 60, steps=8)
    app_page.mouse.up()
    wrong_term, wrong_gi = items[1][0], (items[1][1] + 1) % len(groups)
    for t, gi in items[1:]:
        app_page.click(chip(t))
        app_page.click(drawer(wrong_gi if t == wrong_term else gi))
    app_page.click('[data-action="sb-check"]')
    assert app_page.locator(".sb-chip.wrong").count() == 1
    # Aus der Schublade holen und richtig ablegen
    app_page.click(chip(wrong_term))
    app_page.click(drawer(items[1][1]))
    app_page.click('[data-action="sb-check"]')
    assert app_page.locator(".sb-chip.ok").count() == len(items)
    assert app_page.problems.errors == []


def test_find_the_two_mistakes(app_page):
    open_sb(app_page, 3)
    ex = data(app_page)
    right = {t: gi for gi, g in enumerate(ex["gruppen"]) for t in g["begriffe"]}
    misplaced = [t for t, gi in ex["fehler_belegung"].items() if gi != right[t]]
    assert len(misplaced) == 2 and app_page.locator(".sb-pool .sb-chip").count() == 0
    for t in misplaced:
        app_page.click(chip(t))
        app_page.click(drawer(right[t]))
    app_page.click('[data-action="sb-check"]')
    assert app_page.locator(".sb-chip.ok").count() == len(right)
    assert app_page.problems.errors == []


def test_everything_fits_on_one_screen_in_both_orientations(app_page):
    for width, height in [(1194, 834), (834, 1194), (1133, 744), (744, 1133)]:
        app_page.set_viewport_size({"width": width, "height": height})
        open_sb(app_page, 2)
        over = app_page.evaluate("""() => {
            const o = (el) => el ? el.scrollHeight - el.clientHeight : 0;
            return { page: document.scrollingElement.scrollHeight - innerHeight,
                     pool: o(document.querySelector('.sb-pool')), drawers: o(document.querySelector('.sb-drawers')) };
        }""")
        assert over == {"page": 0, "pool": 0, "drawers": 0}, (width, height)
        app_page.click('[data-action="back"]')
    assert app_page.problems.errors == []
