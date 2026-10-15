"""
Referenztests für den Zeichenkern der Tafel (Pencil-Verhalten, Stand Okt 2026).

Sie schicken Pointer-Events wie Safari auf dem iPad an #wb-canvas und prüfen, was gezeichnet und
gespeichert wird. Das echte Schreibgefühl ersetzen sie nicht, aber sie fangen grobe Brüche ab:
Stift zeichnet mit Druck, Handballen/Finger zeichnet im Nur-Stift-Modus nicht, zwei Finger zeichnen
nie, Objekt-Radierer entfernt Striche, Gespeichertes kommt nach dem Neuladen wieder.
Die Tafel ist zwischen den Tests dieselbe; geprüft wird deshalb immer die Veränderung.
"""
from tests.e2e.board_helpers import INK_PIXELS_JS, _draw, _draw_and_capture_save, _line, _open_board


def _saved_strokes_now(page):
    """Erzwingt einen Speichervorgang über einen kleinen Strich und gibt dessen Zustand zurück (ohne ihn)."""
    strokes = _draw_and_capture_save(page, _line(30, 30, 34, 34, steps=2))
    return strokes[:-1]


def _no_save_within(page, ms=2500):
    saves = []
    page.on("request", lambda r: saves.append(r) if r.method == "PUT" and r.url.endswith("/state") else None)
    page.wait_for_timeout(ms)
    return not saves


def test_pen_stroke_is_drawn_and_saved_with_pressure(app_page):
    _open_board(app_page)
    before_pixels = app_page.evaluate(INK_PIXELS_JS)

    strokes = _draw_and_capture_save(app_page, _line(200, 200, 420, 260), pressure=0.7)

    stroke = strokes[-1]
    assert stroke["tool"] == "pen"
    assert len(stroke["points"]) >= 10
    assert all(abs(p["pressure"] - 0.7) < 0.01 for p in stroke["points"])
    assert app_page.evaluate(INK_PIXELS_JS) > before_pixels
    assert app_page.problems.errors == []


def test_single_finger_does_not_draw_in_pen_only_mode(app_page):
    _open_board(app_page)
    before_pixels = app_page.evaluate(INK_PIXELS_JS)

    _draw(app_page, _line(200, 300, 420, 340), pointer_type="touch", pressure=0.5)

    assert _no_save_within(app_page)
    assert app_page.evaluate(INK_PIXELS_JS) == before_pixels


def test_finger_draws_without_pen_only_mode_but_two_fingers_never(app_page):
    _open_board(app_page)
    app_page.click("#btn-wb-pen-only")  # Nur-Stift-Modus aus

    strokes = _draw_and_capture_save(app_page, _line(200, 400, 420, 440), pointer_type="touch", pressure=0.5, ids=(11,))
    assert strokes[-1]["points"][0]["pointerType"] == "touch"

    before_pixels = app_page.evaluate(INK_PIXELS_JS)
    _draw(app_page, _line(200, 480, 420, 520), pointer_type="touch", pressure=0.5, ids=(21, 22))
    assert _no_save_within(app_page)
    # Der erste Finger setzt kurz einen Punkt, der zweite bricht ab und zeichnet neu (Kantenglättung
    # kann um wenige Pixel abweichen) – entscheidend: keine zusätzliche Tinte
    assert app_page.evaluate(INK_PIXELS_JS) <= before_pixels


def test_object_eraser_removes_a_whole_stroke(app_page):
    _open_board(app_page)
    drawn = _draw_and_capture_save(app_page, _line(500, 150, 500, 350))

    app_page.click('.wb-tool-btn[data-tool="object_eraser"]')
    after = _draw_and_capture_save(app_page, _line(450, 250, 550, 250))

    assert len(after) == len(drawn) - 1


def test_saved_board_comes_back_after_reload(app_page):
    _open_board(app_page)
    saved = _draw_and_capture_save(app_page, _line(250, 600, 450, 620))

    app_page.reload()
    app_page.wait_for_load_state("networkidle")
    _open_board(app_page)

    assert len(_saved_strokes_now(app_page)) == len(saved)
    assert app_page.problems.errors == []
