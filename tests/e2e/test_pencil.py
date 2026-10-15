"""
Referenztests für den Zeichenkern der Tafel (Pencil-Verhalten, Stand Okt 2026).

Sie schicken Pointer-Events wie Safari auf dem iPad an #wb-canvas und prüfen, was gezeichnet und
gespeichert wird. Das echte Schreibgefühl ersetzen sie nicht, aber sie fangen grobe Brüche ab:
Stift zeichnet mit Druck, Handballen/Finger zeichnet im Nur-Stift-Modus nicht, zwei Finger zeichnen
nie, Objekt-Radierer entfernt Striche, Gespeichertes kommt nach dem Neuladen wieder.
Die Tafel ist zwischen den Tests dieselbe; geprüft wird deshalb immer die Veränderung.
"""
import json

SAVE_TIMEOUT_MS = 6000

DRAW_JS = """
(args) => {
  const c = document.getElementById("wb-canvas");
  const r = c.getBoundingClientRect();
  const fire = (type, id, x, y, pressure) => c.dispatchEvent(new PointerEvent(type, {
    pointerId: id, pointerType: args.type, pressure: pressure, isPrimary: id === args.ids[0],
    clientX: r.left + x, clientY: r.top + y, bubbles: true, cancelable: true }));
  for (const id of args.ids) fire("pointerdown", id, args.pts[0][0], args.pts[0][1], args.pressure);
  for (const [x, y] of args.pts.slice(1)) for (const id of args.ids) fire("pointermove", id, x, y, args.pressure);
  const last = args.pts[args.pts.length - 1];
  for (const id of args.ids) fire("pointerup", id, last[0], last[1], 0);
}
"""

INK_PIXELS_JS = """
() => {
  const c = document.getElementById("wb-canvas");
  const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
  let n = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
  return n;
}
"""


def _line(x0, y0, x1, y1, steps=12):
    return [[x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps] for i in range(steps + 1)]


def _open_board(page):
    page.click('.nav-tab[data-tab="whiteboard"]')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)  # Canvas-Größe nach dem Tab-Wechsel


def _draw(page, pts, pointer_type="pen", pressure=0.7, ids=(1,)):
    page.evaluate(DRAW_JS, {"pts": pts, "type": pointer_type, "pressure": pressure, "ids": list(ids)})


def _draw_and_capture_save(page, pts, **kw):
    """Zeichnet und liefert die gespeicherten Striche aus dem folgenden Auto-Save."""
    with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith("/state"), timeout=SAVE_TIMEOUT_MS) as resp:
        _draw(page, pts, **kw)
    assert resp.value.ok
    return json.loads(json.loads(resp.value.request.post_data)["board_state_json"])


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
