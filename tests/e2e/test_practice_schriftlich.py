"""Üben, Übungstyp „Schriftlich rechnen“: jede Stufe einmal durchspielen; alle Verfahren auf einen Bildschirm."""
from tests.e2e.test_practice import practice_list


def open_sr(page, ex_id, stage):
    practice_list(page)
    page.evaluate(f"window.openPracticeExercise('{ex_id}', {stage})")
    page.wait_for_selector(".sr-grid")
    return page.evaluate(f"apiJson('/api/v1/practice/{ex_id}')")


def cell(r, c):
    return f'[data-cell="{r},{c}"]'


def type_into(page, r, c, z):
    page.click(cell(r, c))
    if z:
        page.click(f'.gg-key[data-key="{z}"]')
    else:
        page.click('.gg-key[data-key="back"]')


def grid_text(page):
    return page.evaluate("""() => {
      const rows = {};
      document.querySelectorAll('.sr-cell').forEach((el) => {
        const [r, c] = [parseInt(el.style.gridRow) - 1, parseInt(el.style.gridColumn) - 1];
        if (el.textContent) (rows[r] = rows[r] || {})[c] = el.textContent;
      });
      return rows;
    }""")


def test_watch_stage_shows_every_step(app_page):
    data = open_sr(app_page, "sr-div-852-3", -2)
    assert "8 : 3 = 2" in app_page.inner_text(".px-luna")
    for _ in data["schritte"]:
        app_page.click('[data-action="sr-next"]')
    shown = grid_text(app_page)
    for c in data["gitter"]["zellen"]:
        assert shown[str(c["r"])][str(c["c"])] == c["z"]
    assert app_page.locator('.px-actions [data-action="back"]').count() == 1
    assert app_page.problems.errors == []


def test_tap_stage_asks_each_step(app_page):
    data = open_sr(app_page, "sr-sub-734-281", -1)
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
    for z in "326":  # 623 von rechts nach links, der Cursor läuft selbst weiter
        app_page.click(f'.gg-key[data-key="{z}"]')
    app_page.click('[data-action="sr-check"]')
    assert app_page.locator(".sr-cell.ok").count() == 3
    assert app_page.locator(".gg-scratch").count() == 0  # fertig: keine Tasten, keine Nebenrechnung mehr
    assert app_page.problems.errors == []


def test_all_lines_stage_marks_mistakes_and_offers_tip(app_page):
    data = open_sr(app_page, "sr-mul-243-12", 2)
    todo = [c for c in data["gitter"]["zellen"] if c["art"] not in ("aufgabe", "op", "uebertrag")]
    for c in todo:
        type_into(app_page, c["r"], c["c"], c["z"])
    first = todo[0]
    type_into(app_page, first["r"], first["c"], str((int(first["z"]) + 1) % 10))
    app_page.click('[data-action="sr-check"]')
    assert app_page.locator(".sr-cell.wrong").count() == 1
    app_page.click('[data-action="sr-tip"]')
    assert "Mit der 1" in app_page.inner_text(".px-luna")
    type_into(app_page, first["r"], first["c"], first["z"])
    app_page.click('[data-action="sr-check"]')
    assert app_page.locator(".sr-cell.wrong").count() == 0
    assert app_page.locator('.px-actions [data-stage="3"]').count() == 1
    assert app_page.problems.errors == []


def test_own_layout_may_stand_shifted(app_page):
    data = open_sr(app_page, "sr-add-lk-2a", 3)
    for c in data["gitter"]["zellen"]:
        if c["art"] not in ("op", "uebertrag"):
            type_into(app_page, c["r"], c["c"] + 1, c["z"])  # alles eine Spalte weiter rechts
    app_page.click('[data-action="sr-check"]')
    assert app_page.locator(".sr-cell.wrong").count() == 0
    assert "Richtig" in app_page.inner_text(".px-luna")
    assert app_page.problems.errors == []


def test_find_the_mistake_then_fix_it(app_page):
    data = open_sr(app_page, "sr-sub-lk-3b-2", 4)  # Theas 490,21
    plain = {(c["r"], c["c"]): c["z"] for c in data["gitter"]["zellen"]}
    wrong = {(c["r"], c["c"]): c["z"] for c in data["fehlerbild"]["zellen"]}
    diff = sorted(p for p in set(plain) | set(wrong) if plain.get(p) != wrong.get(p))
    assert len(diff) == 2
    app_page.click(cell(0, 1))  # richtige Stelle: Luna sagt „Such weiter“
    assert "Such weiter" in app_page.inner_text(".px-luna")
    app_page.click(cell(*diff[0]))
    assert "Komma" in app_page.inner_text(".px-luna")
    for r, c in diff:
        type_into(app_page, r, c, plain.get((r, c), ""))
    app_page.click('[data-action="sr-check"]')
    assert "Richtig verbessert" in app_page.inner_text(".px-luna")
    assert app_page.problems.errors == []


def test_every_procedure_fits_on_one_screen(app_page):
    # die höchste (Division mit 11 Zeilen) und die breiteste Rechnung jeder Art
    tasks = ["sr-add-lk-2a", "sr-sub-lk-3b-1", "sr-mul-243-12", "sr-div-mp-2b", "sr-div-ab-5"]
    for width, height in [(1194, 834), (834, 1194), (1133, 744), (744, 1133)]:
        app_page.set_viewport_size({"width": width, "height": height})
        for ex_id in tasks:
            for stage in (-1, 2):
                open_sr(app_page, ex_id, stage)
                fit = app_page.evaluate("""() => {
                  const wrap = document.querySelector('.sr-wrap').getBoundingClientRect();
                  const grid = document.querySelector('.sr-grid').getBoundingClientRect();
                  return { page: document.scrollingElement.scrollHeight - innerHeight,
                           inside: grid.right <= wrap.right + 1 && grid.bottom <= wrap.bottom + 1,
                           cell: parseFloat(getComputedStyle(document.querySelector('.sr-wrap')).getPropertyValue('--cell')) };
                }""")
                assert fit["page"] == 0 and fit["inside"], (ex_id, stage, width, height, fit)
                assert fit["cell"] >= 24, (ex_id, stage, width, height, fit)
                app_page.click('[data-action="back"]')
    assert app_page.problems.errors == []
