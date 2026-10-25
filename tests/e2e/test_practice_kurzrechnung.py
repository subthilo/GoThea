"""Üben, Übungstyp „Kurzrechnung“: Zehnerzahlen mit Überschlag, Brüche antippen und eintippen,
Einmaleins-Check ohne Rückmeldung; alles auf einem Bildschirm."""
from tests.e2e.test_practice import practice_list


def open_kr(page, ex, stage):
    practice_list(page)
    page.evaluate(f"window.openPracticeExercise('{ex}', {stage})")
    page.wait_for_selector(".kr, .kr-eval")


def data(page, ex):
    return page.evaluate(f"apiJson('/api/v1/practice/{ex}')")


def type_number(page, text):
    for ch in text:
        page.click(f'.kr-pad [data-key="{ch}"]')


def type_fraction(page, z, n):
    page.click('.kr-field[data-field="z"]')
    type_number(page, z)
    page.click('.kr-field[data-field="n"]')
    type_number(page, n)


def test_estimate_first_then_comma_hint_then_right(app_page):
    open_kr(app_page, "km-zehnerzahlen-1", 1)
    item = data(app_page, "km-zehnerzahlen-1")["liste"][0]  # 34,29 · 10
    ue = item["ueberschlag"]
    assert app_page.locator(".kr-pad.locked").count() == 1  # erst der Überschlag
    wrong = (ue["richtig"] + 1) % 4
    app_page.click(f'.kr-ue[data-ue="{wrong}"]')
    assert app_page.locator(".kr-ue.wrong").count() == 1
    app_page.click(f'.kr-ue[data-ue="{ue["richtig"]}"]')
    type_number(app_page, "3429")                                 # Komma vergessen
    app_page.click('[data-action="kr-submit"]')
    assert "Komma" in app_page.inner_text(".kr-left .px-luna")
    for _ in range(4):
        app_page.click('.kr-pad [data-key="back"]')
    type_number(app_page, "342,9")
    app_page.click('[data-action="kr-submit"]')
    app_page.wait_for_selector(".kr-dot.done")
    app_page.wait_for_function("document.querySelector('.kr-dot.now') === document.querySelectorAll('.kr-dot')[1]")
    assert app_page.problems.errors == []


def test_tap_stage_marks_wrong_offers(app_page):
    open_kr(app_page, "km-kuerzen-dividieren", -1)
    assert app_page.locator(".kr-left .gg-scratch").count() == 1      # Nebenrechnung auch beim Antippen
    a = data(app_page, "km-kuerzen-dividieren")["liste"][0]["auswahl"]
    wrong = (a["richtig"] + 1) % len(a["angebote"])
    app_page.click(f'.kr-choice[data-choice="{wrong}"]')
    assert app_page.locator(".kr-choice.wrong").count() == 1
    # das angetippte Ergebnis steht in der Gleichung und bleibt markiert stehen
    assert app_page.inner_text(".kr-box-tap.wrong").replace("\n", "/") == a["angebote"][wrong]
    app_page.click(f'.kr-choice[data-choice="{a["richtig"]}"]')
    assert app_page.inner_text(".kr-box-tap.ok").replace("\n", "/") == a["angebote"][a["richtig"]]
    app_page.wait_for_selector(".kr-dot.done")
    assert app_page.problems.errors == []


def test_fraction_not_fully_reduced_goes_on(app_page):
    open_kr(app_page, "km-division-als-bruch", 2)   # 2 : 12
    type_fraction(app_page, "2", "12")
    app_page.click('[data-action="kr-submit"]')
    assert "Geht noch weiter" in app_page.inner_text(".kr-left .px-luna")
    app_page.click('.kr-field[data-field="z"]')
    app_page.click('.kr-pad [data-key="back"]')
    type_number(app_page, "1")
    app_page.click('.kr-field[data-field="n"]')
    app_page.click('.kr-pad [data-key="back"]')
    app_page.click('.kr-pad [data-key="back"]')
    type_number(app_page, "6")
    app_page.click('[data-action="kr-submit"]')
    app_page.wait_for_selector(".kr-dot.done")
    assert app_page.problems.errors == []


def test_solution_after_two_misses_then_whole_set_to_the_end(app_page):
    open_kr(app_page, "km-messbecher", 2)
    items = data(app_page, "km-messbecher")["liste"]
    for _ in range(2):
        type_number(app_page, "9")
        app_page.click('[data-action="kr-submit"]')
        app_page.click('.kr-pad [data-key="back"]')
    app_page.click('[data-action="kr-show"]')
    app_page.click('[data-action="kr-next"]')
    for it in items[1:]:
        app_page.wait_for_selector(".kr-pad:not(.locked)")
        type_number(app_page, it["loesung"])
        app_page.click('[data-action="kr-submit"]')
        app_page.wait_for_function("!document.querySelector('.kr-box.ok')")
    app_page.wait_for_selector(".kr-done")
    assert "Lösung angesehen" in app_page.inner_text(".kr-done")
    assert app_page.problems.errors == []


def test_einmaleins_check_shows_the_right_result_after_a_mistake(app_page):
    open_kr(app_page, "km-einmaleins-check", 2)
    app_page.click('[data-action="kr-start"]')  # Eltern-Modus: erst die Auswertung (noch leer), dann Start
    for i in range(36):
        app_page.wait_for_function(f"document.querySelectorAll('.kr-dot.done, .kr-dot.shown').length === {i}"
                                   " && !!document.querySelector('.kr-pad:not(.locked)')")
        a, b = [int(x) for x in app_page.inner_text(".kr-expr").split("·")]
        wrong = 7 in (a, b)                                      # alle Siebener falsch
        type_number(app_page, str(a * b + 1 if wrong else a * b))
        app_page.click('[data-action="kr-submit"]')
        if wrong:
            assert app_page.inner_text(".kr-given") == str(a * b + 1)   # eigene Antwort durchgestrichen
            assert app_page.inner_text(".kr-box.shown") == str(a * b)   # daneben das richtige Ergebnis
            app_page.click('[data-action="kr-next"]')
    app_page.wait_for_selector(".kr-done")
    assert app_page.problems.errors == []


def assert_fits(page, cases):
    for width, height in [(1194, 834), (834, 1194), (1133, 744), (744, 1133)]:
        page.set_viewport_size({"width": width, "height": height})
        for ex, stage in cases:
            open_kr(page, ex, stage)
            if page.locator('[data-action="kr-start"]').count():
                page.click('[data-action="kr-start"]')
            over = page.evaluate("""() => {
                const o = (el) => el ? el.scrollHeight - el.clientHeight : 0;
                const r = (el) => el ? Math.max(0, el.getBoundingClientRect().bottom - innerHeight) : 0;
                return { page: document.scrollingElement.scrollHeight - innerHeight,
                         left: o(document.querySelector('.kr-left')), right: o(document.querySelector('.kr-right')),
                         actions: r(document.querySelector('.kr-actions')) };
            }""")
            assert over == {"page": 0, "left": 0, "right": 0, "actions": 0}, (ex, stage, width, height, over)
            page.click('[data-action="back"]')
    assert page.problems.errors == []


def test_everything_fits_on_one_screen_in_both_orientations(app_page):
    assert_fits(app_page, [("km-zehnerzahlen-2", 1), ("km-bruch-division-1", 2), ("km-kuerzen-dividieren", -1),
                           ("km-einmaleins-check", 2)])
