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


def test_number_stage_by_keys_advances_and_checks(app_page):
    open_ordnen(app_page, 4)
    order = steps(app_page)
    cards = app_page.evaluate(f"apiJson('/api/v1/practice/{EX}')")["karten"]
    assert app_page.locator(".gg-write-area").count() == 1  # Schreibfeld da
    # Tasten: nach jeder Ziffer weiter zum nächsten Kästchen; zwei Nummern vertauscht
    numbers = [str(order.index(c) + 1) for c in cards]
    numbers[0], numbers[1] = numbers[1], numbers[0]
    for n in numbers:
        app_page.click(f'.gg-key[data-key="{n}"]')
    app_page.click('[data-action="or-check"]')
    assert app_page.locator(".or-num.wrong").count() == 2
    # Kästchen antippen, Löschen, richtige Nummer
    for i, c in enumerate(cards[:2]):
        app_page.click(f'.or-num >> nth={i}')
        app_page.click('.gg-key[data-key="back"]')
        app_page.click(f'.gg-key[data-key="{order.index(c) + 1}"]')
    app_page.click('[data-action="or-check"]')
    assert app_page.locator(".or-num.ok").count() == len(order)
    assert app_page.problems.errors == []


def test_number_stage_fits_on_one_screen(app_page):
    for width, height in [(1194, 834), (834, 1194), (1133, 744), (744, 1133)]:
        app_page.set_viewport_size({"width": width, "height": height})
        open_ordnen(app_page, 4)
        over = app_page.evaluate("""() => ({ page: document.scrollingElement.scrollHeight - innerHeight,
            list: (el => el.scrollHeight - el.clientHeight)(document.querySelector('.or-number-list')) })""")
        assert over == {"page": 0, "list": 0}, (width, height)
        app_page.click('[data-action="back"]')
    assert app_page.problems.errors == []


def test_number_stage_reads_written_digits_and_learns_them(app_page):
    from tests.e2e.test_practice import WRITE_DIGITS_JS
    open_ordnen(app_page, 4)
    order = steps(app_page)
    cards = app_page.evaluate(f"apiJson('/api/v1/practice/{EX}')")["karten"]
    app_page.wait_for_selector(".gg-write-ink")
    # Erstes Kästchen mit dem Stift, danach springt es weiter; den Rest tippen
    first = str(order.index(cards[0]) + 1)
    app_page.evaluate(WRITE_DIGITS_JS, first)
    app_page.wait_for_function(f"document.querySelector('.or-num').textContent === '{first}'")
    assert "active" in app_page.get_attribute(".or-num >> nth=1", "class")
    for c in cards[1:]:
        app_page.click(f'.gg-key[data-key="{order.index(c) + 1}"]')
    with app_page.expect_response(lambda r: r.url.endswith("/handwriting") and r.request.method == "POST") as learned:
        app_page.click('[data-action="or-check"]')
    sent = learned.value.request.post_data_json["samples"]  # die Antwort enthält alle gespeicherten Muster
    assert {s["label"] for s in sent} == {first}
    assert app_page.problems.errors == []
