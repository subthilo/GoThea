"""Üben, Übungstyp „Zuordnen“: Brenner aus dem Chemiebuch durchspielen (Entwürfe: tests/integration)."""

BRENNER = "ch-brenner"


def open_brenner(page, pin, stage):
    page.wait_for_selector('.nav-tab[data-tab="practice"]', state="visible")
    page.click('.nav-tab[data-tab="practice"]')
    page.wait_for_selector(f'.practice-row[data-id="{BRENNER}"]')
    page.evaluate(f"window.openPracticeExercise('{BRENNER}', {stage})")
    page.wait_for_selector(".zo-figure img")


def terms(page):
    return page.evaluate(f"apiJson('/api/v1/practice/{BRENNER}')")["felder"]


def test_look_stage_reveals_each_term(app_page, parent_pin):
    open_brenner(app_page, parent_pin, -1)
    fields = terms(app_page)
    assert app_page.locator(".zo-spot").count() == len(fields) == 11
    app_page.click('.zo-spot[data-spot="10"]')
    assert app_page.inner_text('.zo-slot[data-row="10"]') == "Stellschraube für Gaszufuhr"
    for f in fields:
        app_page.click(f'.zo-slot[data-row="{f["nr"]}"]')
    assert "alle Begriffe" in app_page.inner_text(".px-luna")
    app_page.click('.px-check[data-stage="1"]')
    app_page.wait_for_selector(".zo-token")
    assert app_page.problems.errors == []


def test_assign_terms_by_tapping_and_dragging(app_page, parent_pin):
    open_brenner(app_page, parent_pin, 1)
    fields = terms(app_page)
    # Ziffer im Bild, dann Begriff
    app_page.click('.zo-spot[data-spot="1"]')
    app_page.click(f'.zo-token[data-token="{fields[0]["begriff"]}"]')
    # Ziehen auf eine Zeile
    token = app_page.locator(f'.zo-token[data-token="{fields[1]["begriff"]}"]').bounding_box()
    row = app_page.locator('.zo-slot[data-row="2"]').bounding_box()
    app_page.mouse.move(token["x"] + 10, token["y"] + 10)
    app_page.mouse.down()
    app_page.mouse.move(row["x"] + 20, row["y"] + 10, steps=8)
    app_page.mouse.up()
    assert app_page.inner_text('.zo-slot[data-row="2"]') == fields[1]["begriff"]
    # Begriff, dann Zeile – zwei vertauscht
    rest = fields[2:]
    for f, target in zip(rest, [rest[1], rest[0]] + rest[2:]):
        app_page.click(f'.zo-token[data-token="{f["begriff"]}"]')
        app_page.click(f'.zo-slot[data-row="{target["nr"]}"]')
    app_page.click('[data-action="zo-check"]')
    assert app_page.locator(".zo-slot.wrong").count() == 2
    assert "2 Begriffe stimmen noch nicht" in app_page.inner_text(".px-luna")
    # Richtig tauschen: Zeile antippen (markiert), noch mal (leert), Begriff setzen
    for f in rest[:2]:
        app_page.click(f'.zo-slot[data-row="{f["nr"]}"]')
        app_page.click(f'.zo-token[data-token="{f["begriff"]}"]')
    app_page.click('[data-action="zo-check"]')
    assert app_page.locator(".zo-slot.ok").count() == 11
    assert app_page.locator('.px-check[data-stage="2"]').count() == 1
    assert app_page.problems.errors == []


def test_book_view_shows_the_original_figure(app_page, parent_pin):
    open_brenner(app_page, parent_pin, 2)
    assert app_page.locator(".zo-token").count() == 15  # 11 Begriffe + 4 Ablenker
    app_page.click('[data-action="zo-book"]')
    assert "ch-brenner_original.jpg" in app_page.get_attribute(".zo-book img", "src")
    app_page.click('[data-action="zo-book"]')
    app_page.wait_for_selector(".zo-spot")
    assert app_page.problems.errors == []


def _overflow(page):
    return page.evaluate("""() => {
        const over = (el) => el ? el.scrollHeight - el.clientHeight : 0;
        return { page: document.scrollingElement.scrollHeight - innerHeight,
                 rows: over(document.querySelector('.zo-rows')), bank: over(document.querySelector('.zo-bank')) };
    }""")


def test_everything_fits_on_one_screen_in_both_orientations(app_page, parent_pin):
    # Quer und hoch, auch auf dem kleinsten iPad (mini): kein Scrollen, weder Seite noch Liste noch Wortbank
    for width, height in [(1194, 834), (834, 1194), (1133, 744), (744, 1133)]:
        app_page.set_viewport_size({"width": width, "height": height})
        open_brenner(app_page, parent_pin, 2)
        app_page.click(f'.zo-token[data-token="{terms(app_page)[0]["begriff"]}"]')
        app_page.click('.zo-slot[data-row="2"]')
        assert _overflow(app_page) == {"page": 0, "rows": 0, "bank": 0}, (width, height)
        box = app_page.locator(".zo-figure").bounding_box()
        assert box["width"] > 450, (width, height, box)
        app_page.click('[data-action="back"]')
    assert app_page.problems.errors == []
