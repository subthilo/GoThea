"""Theas gemalter Hintergrund: erscheint hinter der Startseite, nicht auf anderen Seiten und nicht im Eltern-Modus."""
import pytest

ON = "document.body.classList.contains('paint-bg-on')"

# Malt im Browser ein quadratisches Bild, lädt es hoch und hängt es an den Platz (wie später der Mal-Modus)
UPLOAD = """async (slot) => {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = '#e8a33d'; g.fillRect(0, 0, 256, 256);
  g.fillStyle = '#3d7be8'; g.beginPath(); g.arc(128, 128, 90, 0, 2 * Math.PI); g.fill();
  const blob = await new Promise((r) => c.toBlob(r, 'image/webp', 0.85));
  const form = new FormData();
  form.append('kind', 'background');
  form.append('format', 'square');
  form.append('strokes_json', '[]');
  form.append('slot_key', slot);
  form.append('image', blob, 'bild');
  const res = await apiFetch('/api/v1/paintings', {method: 'POST', body: form});
  return (await res.json()).id;
}"""


@pytest.fixture
def dashboard_painting(app_page):
    painting_id = app_page.evaluate(UPLOAD, "dashboard")
    yield painting_id
    # Der Testserver wird geteilt: andere Tests sollen die Startseite ohne Bild sehen
    app_page.evaluate(f"() => apiFetch('/api/v1/paintings/{painting_id}/archive', {{method: 'POST'}})")


def test_background_shows_behind_dashboard_only_for_thea(app_page, parent_pin, dashboard_painting):
    app_page.reload()
    app_page.wait_for_function(ON, timeout=5000)
    layer = app_page.evaluate("""() => {
      const r = document.getElementById('paint-bg').getBoundingClientRect();
      const img = document.querySelector('.paint-bg-img');
      return {w: r.width, h: r.height, vw: innerWidth, vh: innerHeight, natural: img.naturalWidth,
              src: img.getAttribute('src')};
    }""")
    assert layer["natural"] > 0 and dashboard_painting in layer["src"]
    assert layer["w"] == layer["vw"] and layer["h"] >= layer["vh"]

    # Inhalt scrollt darüber, die Schicht bleibt stehen
    app_page.evaluate("window.scrollTo(0, 600)")
    assert app_page.evaluate("document.getElementById('paint-bg').getBoundingClientRect().top") == 0

    # Seiten ohne eigenes Bild zeigen keins
    app_page.click('.nav-tab[data-tab="timetable"]')
    app_page.wait_for_function(f"!{ON}")
    app_page.click('.nav-tab[data-tab="dashboard"]')
    app_page.wait_for_function(ON)

    # Eltern-Modus bleibt neutral
    app_page.click("#btn-parent-toggle")
    app_page.fill("#input-parent-pin", parent_pin)
    app_page.click("#btn-submit-parent-pin")
    app_page.wait_for_function(f"!{ON}", timeout=5000)
    app_page.click("#btn-parent-toggle")
    app_page.wait_for_function(ON, timeout=5000)
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []


def test_no_background_without_painting(app_page):
    app_page.wait_for_load_state("networkidle")
    assert app_page.evaluate(ON) is False
    assert app_page.problems.errors == []


# ---- Mal-Modus ----
PAINT_DRAW = """(pts) => {
  const c = document.querySelector('.paint-ink');
  const r = c.getBoundingClientRect();
  const fire = (type, [x, y], p) => c.dispatchEvent(new PointerEvent(type, {pointerId: 7, pointerType: 'pen',
    pressure: p, isPrimary: true, clientX: r.left + x, clientY: r.top + y, bubbles: true, cancelable: true}));
  fire('pointerdown', pts[0], 0.7);
  pts.slice(1).forEach((pt) => fire('pointermove', pt, 0.7));
  fire('pointerup', pts[pts.length - 1], 0);
}"""
INK = """() => {
  const c = document.querySelector('.paint-ink');
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let n = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
  return n;
}"""
LINE = [[40 + i * 20, 60 + i * 15] for i in range(15)]


def _paintings_request(method):
    return lambda r: r.request.method == method and "/api/v1/paintings" in r.url and "/image" not in r.url \
        and "?keys=" not in r.url


@pytest.fixture
def clean_dashboard(app_page):
    yield
    app_page.evaluate("""async () => {
      const slot = (await apiJson('/api/v1/paintings?keys=dashboard')).slots.dashboard;
      if (slot) await apiFetch(`/api/v1/paintings/${slot.id}/archive`, {method: 'POST'});
    }""")


def test_brush_button_only_on_paintable_pages_for_thea(app_page, parent_pin):
    fab = app_page.locator("#btn-paint")
    fab.wait_for(state="visible")
    app_page.click('.nav-tab[data-tab="timetable"]')
    fab.wait_for(state="hidden")
    app_page.click('.nav-tab[data-tab="dashboard"]')
    fab.wait_for(state="visible")
    app_page.click("#btn-parent-toggle")
    app_page.fill("#input-parent-pin", parent_pin)
    app_page.click("#btn-submit-parent-pin")
    fab.wait_for(state="hidden")
    app_page.click("#btn-parent-toggle")
    fab.wait_for(state="visible")
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []


def test_paint_save_and_paint_on_later(app_page, clean_dashboard):
    app_page.click("#btn-paint")
    app_page.locator("#paint-mode").wait_for(state="visible")
    box = app_page.locator(".paint-viewport").bounding_box()
    assert abs(box["width"] - box["height"]) < 1 and box["height"] > 600  # Quadrat, so groß wie möglich
    assert app_page.locator(".paint-ghost-page .dash-timetable-card").count() == 1  # Geisterbild der Seite

    # Malen speichert unsichtbar: neues Bild, an der Startseite
    with app_page.expect_response(_paintings_request("POST"), timeout=6000) as resp:
        app_page.evaluate(PAINT_DRAW, LINE)
    assert resp.value.status == 201
    created = resp.value.json()
    assert created["slots"] == ["dashboard"] and created["image_url"]
    assert app_page.evaluate(INK) > 0

    # Fertig → Bild hinter der Startseite
    app_page.click('[data-paint-action="done"]')
    app_page.wait_for_function(ON, timeout=5000)
    assert created["id"] in app_page.get_attribute(".paint-bg-img", "src")

    # Wieder öffnen: die Striche sind da, Weitermalen ändert dasselbe Bild
    app_page.click("#btn-paint")
    app_page.wait_for_function(f"({INK})() > 0", timeout=5000)
    with app_page.expect_response(_paintings_request("PUT"), timeout=6000) as resp:
        app_page.evaluate(PAINT_DRAW, [[400, 100], [300, 300], [100, 500]])
    assert resp.value.ok and resp.value.json()["id"] == created["id"]
    saved = app_page.evaluate(f"apiJson('/api/v1/paintings/{created['id']}')")
    strokes = __import__("json").loads(saved["strokes_json"])
    assert strokes["units"] == 1000 and len(strokes["strokes"]) == 2
    assert all(0 <= p["x"] <= 1000 and 0 <= p["y"] <= 1000 for st in strokes["strokes"] for p in st["points"])

    # Rückgängig nimmt den letzten Strich weg und speichert
    with app_page.expect_response(_paintings_request("PUT"), timeout=6000):
        app_page.click('[data-paint-action="undo"]')
    saved = app_page.evaluate(f"apiJson('/api/v1/paintings/{created['id']}')")
    assert len(__import__("json").loads(saved["strokes_json"])["strokes"]) == 1

    # Geisterbild umschalten: halb → Umrisse → aus → voll
    ghost = app_page.locator(".paint-ghost")
    seen = []
    for _ in range(4):
        seen.append(ghost.get_attribute("data-ghost"))
        app_page.click('[data-paint-action="ghost"]')
    assert sorted(seen) == ["full", "half", "off", "outline"]

    app_page.click('[data-paint-action="done"]')
    app_page.locator("#paint-mode").wait_for(state="hidden")
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []


def test_paint_mode_fits_the_screen_in_both_orientations(app_page, clean_dashboard):
    # iPad Pro 11 und mini, quer und hoch – auch beim Drehen mit offenem Mal-Modus
    app_page.click("#btn-paint")
    app_page.locator("#paint-mode").wait_for(state="visible")
    with app_page.expect_response(_paintings_request("POST"), timeout=6000):
        app_page.evaluate(PAINT_DRAW, LINE)
    for width, height in [(1194, 834), (834, 1194), (1133, 744), (744, 1133)]:
        app_page.set_viewport_size({"width": width, "height": height})
        app_page.wait_for_timeout(150)
        for sel in [".paint-viewport", ".paint-bar-colors", ".paint-bar-tools", '[data-paint-action="done"]']:
            r = app_page.locator(sel).bounding_box()
            assert r["x"] >= 0 and r["y"] >= 0 and r["x"] + r["width"] <= width + 1 \
                and r["y"] + r["height"] <= height + 1, (sel, width, height)
        side = app_page.locator(".paint-viewport").bounding_box()["width"]
        assert side >= min(width, height) * 0.7, (width, height)
        assert app_page.evaluate(INK) > 0  # die Striche wachsen mit
    app_page.click('[data-paint-action="done"]')
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []
