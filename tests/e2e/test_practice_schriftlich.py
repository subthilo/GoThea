"""Üben, Übungstyp „Schriftlich rechnen“: jede Stufe einmal durchspielen; Schreibregeln; Seite ohne Scrollen."""
from tests.e2e.test_practice import practice_list


def open_sr(page, ex_id, stage):
    practice_list(page)
    page.evaluate(f"window.openPracticeExercise('{ex_id}', {stage})")
    page.wait_for_selector(".sr-grid")
    return page.evaluate(f"apiJson('/api/v1/practice/{ex_id}')")


def box(r, c):
    return f'[data-box="{r},{c}"]'


def enter(page, cell, shift=0):
    """Wie auf dem iPad: Kästchen antippen und tippen; Komma = Komma-Taste, Übertrag = Kästchen zweimal antippen."""
    r, c = cell["r"], cell["c"] + shift
    page.click(box(r, c))
    if cell["platz"] == "uebertrag":
        page.click(box(r, c))
    page.click(f'.gg-key[data-key="{cell["z"]}"]')


def sheet(page):
    """Was auf dem Blatt steht: {(r, c, platz): Zeichen}."""
    found = page.evaluate("""() => [...document.querySelectorAll('.sr-cell')].map((el) => ({
      r: parseInt(el.style.gridRow) - 1, c: parseInt(el.style.gridColumn) - 1,
      ziffer: [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(''),
      uebertrag: el.querySelector('.sr-carry') ? el.querySelector('.sr-carry').textContent : '',
      komma: el.querySelector('.sr-comma') ? ',' : '' }))""")
    out = {}
    for f in found:
        for platz in ("ziffer", "uebertrag", "komma"):
            if f[platz]:
                out[(f["r"], f["c"], platz)] = f[platz]
    return out


def test_watch_stage_shows_every_step(app_page):
    data = open_sr(app_page, "sr-sub-lk-3b-1", -2)
    for _ in data["schritte"]:
        app_page.click('[data-action="sr-next"]')
    shown = sheet(app_page)
    for c in data["gitter"]["zellen"]:
        assert shown.get((c["r"], c["c"], c["platz"])) == c["z"], c
    # Übertrag steht klein im Kästchen der unteren Zahl, nicht in einer eigenen Zeile
    assert app_page.locator(".sr-carry").count() == sum(c["platz"] == "uebertrag" for c in data["gitter"]["zellen"])
    assert app_page.locator('.px-actions [data-action="back"]').count() == 1
    assert app_page.problems.errors == []


def test_comma_sits_on_the_grid_line_and_moves_no_digit(app_page):
    open_sr(app_page, "sr-sub-lk-3b-1", -2)
    for _ in range(20):
        if app_page.locator('[data-action="sr-next"]').count() == 0:
            break
        app_page.click('[data-action="sr-next"]')
    geo = app_page.evaluate("""() => {
      const comma = document.querySelector('.sr-comma').getBoundingClientRect();
      const cell = document.querySelector('.sr-comma').parentElement.getBoundingClientRect();
      const cols = [...document.querySelectorAll('.sr-cell')].map((el) => el.getBoundingClientRect().width);
      return { centre: comma.left + comma.width / 2, line: cell.right, bottom: comma.bottom, cellBottom: cell.bottom,
               widths: [...new Set(cols.map(Math.round))] };
    }""")
    assert abs(geo["centre"] - geo["line"]) < 6           # auf der senkrechten Linie
    assert geo["bottom"] <= geo["cellBottom"] + 4          # unten, nicht darunter
    assert geo["widths"] == [48]                           # alle Kästchen gleich breit
    assert app_page.problems.errors == []


def test_tap_stage_asks_each_step(app_page):
    data = open_sr(app_page, "sr-sub-734-281", -1)
    assert app_page.locator(".gg-scratch").count() == 0  # keine Nebenrechnung
    for st in data["schritte"]:
        wrong = next(o for o in st["optionen"] if o != st["antwort"])
        app_page.click(f'.sr-option[data-option="{wrong}"]')
        assert app_page.locator(".sr-option.wrong").count() == 1
        app_page.click(f'.sr-option[data-option="{st["antwort"]}"]')
        assert st["satz"][:20] in app_page.inner_text(".px-luna")
        app_page.click('[data-action="sr-next"]')
    assert "Geschafft" in app_page.inner_text(".px-luna")
    assert app_page.problems.errors == []


def test_result_stage_runs_in_writing_direction(app_page):
    open_sr(app_page, "sr-add-348-275", 1)
    assert app_page.locator(".gg-scratch").count() == 0
    for z in "326":  # 623 von rechts nach links, der Cursor läuft selbst weiter
        app_page.click(f'.gg-key[data-key="{z}"]')
    app_page.click('[data-action="sr-check"]')
    assert app_page.locator(".sr-cell.ok").count() == 3
    assert app_page.problems.errors == []


def test_all_lines_stage_with_carries_in_the_box(app_page):
    data = open_sr(app_page, "sr-mul-243-12", 2)
    assert app_page.locator(".sr-carry.hint").count() == 1  # Platz für den Übertrag ist angedeutet
    todo = [c for c in data["gitter"]["zellen"] if c["art"] not in ("aufgabe", "op")]
    for c in todo:
        enter(app_page, c)
    first = todo[0]
    enter(app_page, {**first, "z": str((int(first["z"]) + 1) % 10)})
    app_page.click('[data-action="sr-check"]')
    assert app_page.locator(".sr-cell.wrong").count() == 1
    app_page.click('[data-action="sr-tip"]')
    assert "Mit der 1" in app_page.inner_text(".px-luna")
    enter(app_page, first)
    app_page.click('[data-action="sr-check"]')
    assert app_page.locator(".sr-cell.wrong").count() == 0
    assert app_page.locator('.px-actions [data-stage="3"]').count() == 1
    assert app_page.problems.errors == []


def test_own_layout_may_stand_shifted(app_page):
    data = open_sr(app_page, "sr-add-lk-2a", 3)
    assert app_page.locator(".sr-cell.strich").count() == 0  # Striche verrieten den Aufbau
    for c in data["gitter"]["zellen"]:
        if c["art"] not in ("op", "uebertrag"):
            enter(app_page, c, shift=1)  # alles eine Spalte weiter rechts
    app_page.click('[data-action="sr-check"]')
    assert app_page.locator(".sr-cell.wrong").count() == 0
    assert "Richtig" in app_page.inner_text(".px-luna")
    assert app_page.problems.errors == []


def test_find_the_mistake_then_fix_it(app_page):
    data = open_sr(app_page, "sr-sub-lk-3b-2", 4)  # Theas 490,21: nur das Komma steht falsch
    plain = {(c["r"], c["c"], c["platz"]): c["z"] for c in data["gitter"]["zellen"]}
    wrong = {(c["r"], c["c"], c["platz"]): c["z"] for c in data["fehlerbild"]["zellen"]}
    diff = sorted(k for k in set(plain) | set(wrong) if plain.get(k) != wrong.get(k))
    assert [k[2] for k in diff] == ["komma", "komma"]
    app_page.click(box(0, 1))  # richtige Stelle: Luna sagt „Such weiter“
    assert "Such weiter" in app_page.inner_text(".px-luna")
    app_page.click(box(*diff[0][:2]))
    assert "Komma" in app_page.inner_text(".px-luna")
    for r, c, _ in diff:  # Komma-Taste schaltet das Komma am gewählten Kästchen um
        app_page.click(box(r, c))
        app_page.click('.gg-key[data-key=","]')
    app_page.click('[data-action="sr-check"]')
    assert "Richtig verbessert" in app_page.inner_text(".px-luna")
    assert app_page.problems.errors == []


def test_page_stays_put_and_the_sheet_scrolls(app_page):
    tasks = ["sr-add-lk-2a", "sr-sub-lk-3b-1", "sr-mul-243-12", "sr-div-mp-2b", "sr-div-ab-5"]
    for width, height in [(1194, 834), (834, 1194), (1133, 744), (744, 1133)]:
        app_page.set_viewport_size({"width": width, "height": height})
        for ex_id in tasks:
            for stage in (-1, 2):
                open_sr(app_page, ex_id, stage)
                fit = app_page.evaluate("""() => {
                  const wrap = document.querySelector('.sr-wrap');
                  return { page: document.scrollingElement.scrollHeight - innerHeight,
                           cell: parseFloat(getComputedStyle(wrap).getPropertyValue('--cell')),
                           touch: getComputedStyle(wrap).touchAction, overflow: getComputedStyle(wrap).overflowY,
                           keys: !!document.querySelector('.sr-keys') === %s };
                }""" % ("true" if stage == 2 else "false"))
                assert fit["page"] == 0 and fit["keys"], (ex_id, stage, width, height, fit)
                assert fit["cell"] == 48 and fit["touch"] == "pan-x pan-y" and fit["overflow"] == "auto", fit
                app_page.click('[data-action="back"]')
    assert app_page.problems.errors == []


def test_free_stage_on_the_board_is_a_squared_sheet_that_does_not_zoom(app_page):
    # Mathe gibt es im Seeder; die Tafel braucht das Fach der Übung
    open_sr(app_page, "sr-mul-243-12", 4)
    with app_page.expect_response(lambda r: r.url.endswith("/api/v1/boards") and r.request.method == "POST") as created:
        app_page.click('.px-stage[data-stage="5"]')
    board = created.value.json()
    try:
        assert created.value.status == 201 and board["practice_stage"] == 5, board
        app_page.wait_for_selector("#wb-doc-underlay-img.practice-sheet", state="visible")
        size = app_page.evaluate("(() => { const i = document.getElementById('wb-doc-underlay-img'); return [i.naturalWidth, i.naturalHeight]; })()")
        assert size[0] == 1560 and size[1] >= 2 * (96 + 16 * 48)
        # Zusammenziehen (hier: Trackpad mit Strg, derselbe Weg wie zwei Finger) zoomt sonst die Tafel – hier nicht
        zoom = """() => { const vp = document.getElementById('wb-viewport'); const r = vp.getBoundingClientRect();
          vp.dispatchEvent(new WheelEvent('wheel', { deltaY: -400, ctrlKey: true, clientX: r.left + 300,
                                                     clientY: r.top + 300, bubbles: true, cancelable: true }));
          return vp.style.backgroundSize; }"""
        assert app_page.evaluate(zoom) in ("", "24px 24px")
    finally:
        if created.value.status == 201:  # sonst öffnen spätere Tests diese Tafel als letzte
            app_page.evaluate(f"apiFetch('/api/v1/boards/{board['id']}', {{ method: 'DELETE' }})")
    assert app_page.problems.errors == []


def test_other_boards_still_zoom(app_page):
    from tests.e2e.board_helpers import _open_board
    _open_board(app_page)
    size = app_page.evaluate("""() => { const vp = document.getElementById('wb-viewport'); const r = vp.getBoundingClientRect();
      vp.dispatchEvent(new WheelEvent('wheel', { deltaY: -400, ctrlKey: true, clientX: r.left + 300, clientY: r.top + 300,
                                                 bubbles: true, cancelable: true }));
      return vp.style.backgroundSize; }""")
    assert size not in ("", "24px 24px")
    app_page.evaluate("document.getElementById('wb-viewport').dispatchEvent(new WheelEvent('wheel', { deltaY: 4000, ctrlKey: true, bubbles: true, cancelable: true }))")
    assert app_page.problems.errors == []
