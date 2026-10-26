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
    # Der Testserver wird geteilt: alle gemalten Bilder wegräumen (Hintergründe und Kacheln jeder Art)
    app_page.evaluate("""async () => {
      for (const slot of ['dashboard', 'dashboard/tile/x']) {
        for (const p of await apiJson(`/api/v1/paintings/slots/${slot}/history`)) {
          if (!p.archived) await apiFetch(`/api/v1/paintings/${p.id}/archive`, {method: 'POST'});
        }
      }
    }""")


def _open_background(page):
    page.click("#btn-paint")
    page.click('[data-paint-choose="background"]')
    page.locator("#paint-mode").wait_for(state="visible")


def _open_tile(page, key):
    """Wie auf dem iPad: Pinsel antippen, dann das Feld über der Kachel antippen."""
    page.tap("#btn-paint")
    page.locator(".paint-chooser").wait_for(state="visible")
    page.tap(f'.paint-pick[data-paint-pick="{key}"]')
    page.locator("#paint-mode").wait_for(state="visible")


GHOST_FIT = """(sel) => {
  const v = document.querySelector('.paint-viewport').getBoundingClientRect();
  const g = document.querySelector(sel).getBoundingClientRect();
  return {left: g.left - v.left, right: v.right - g.right, top: g.top - v.top, bottom: v.bottom - g.bottom};
}"""


def _assert_ghost_fits(page, sel):
    # Das Bild bedeckt Bildschirm bzw. Kachel: die liegen ganz im Bild, mittig, an zwei Seiten bündig
    f = page.evaluate(GHOST_FIT, sel)
    assert min(f.values()) > -1, f
    assert abs(f["left"] - f["right"]) < 2 and abs(f["top"] - f["bottom"]) < 2, f
    assert min(f["left"] + f["right"], f["top"] + f["bottom"]) < 2, f


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
    _open_background(app_page)
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
    _open_background(app_page)
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
        mode = ghost.get_attribute("data-ghost")
        seen.append(mode)
        # „aus“ blendet auch die Rahmen für quer und hoch aus (stören beim Ausmalen)
        assert app_page.locator(".paint-frame").first.is_visible() == (mode != "off"), mode
        app_page.click('[data-paint-action="ghost"]')
    assert sorted(seen) == ["full", "half", "off", "outline"]

    app_page.click('[data-paint-action="done"]')
    app_page.locator("#paint-mode").wait_for(state="hidden")
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []


def test_slow_saves_do_not_pile_up(app_page, clean_dashboard):
    # Auf dem iPad dauerte ein Speichern 5–11 s; jede Malpause legte eine weitere Aufnahme in die Kette,
    # das Bild erschien erst Minuten nach dem Haken (26.10.). Jetzt wartet höchstens die neueste.
    _open_background(app_page)
    with app_page.expect_response(_paintings_request("POST"), timeout=6000) as resp:
        app_page.evaluate(PAINT_DRAW, LINE)
    painting_id = resp.value.json()["id"]
    # Speichern im Browser verlangsamen (eine Verzögerung in page.route hielte auch die Testschritte an)
    app_page.evaluate("""() => {
      window.__puts = 0;
      const orig = window.fetch;
      window.fetch = async (url, opts) => {
        if (opts && opts.method === 'PUT' && String(url).includes('/api/v1/paintings/')) {
          window.__puts++;
          await new Promise((r) => setTimeout(r, 1500));
        }
        return orig(url, opts);
      };
    }""")
    for i in range(6):  # sechs Striche mit Malpause, schneller als ein Speichern dauert
        app_page.evaluate(PAINT_DRAW, [[100 + i * 40, 100], [100 + i * 40, 400]])
        app_page.evaluate("() => { flushPaintSave(); }")  # nicht auf das Speichern warten
    app_page.click('[data-paint-action="done"]')
    app_page.wait_for_function(f"document.querySelector('.paint-bg-img').src.includes('{painting_id}')", timeout=8000)
    app_page.evaluate("paintMode.pending")
    assert app_page.evaluate("window.__puts") <= 2
    saved = app_page.evaluate(f"apiJson('/api/v1/paintings/{painting_id}')")
    assert len(__import__("json").loads(saved["strokes_json"])["strokes"]) == 7
    assert app_page.problems.errors == []


def test_paint_mode_fits_the_screen_in_both_orientations(app_page, clean_dashboard):
    # iPad Pro 11 und mini, quer und hoch – auch beim Drehen mit offenem Mal-Modus
    _open_background(app_page)
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


def test_color_mixer_mixes_like_paint_and_keeps_the_color(app_page, clean_dashboard):
    # Acht eigene Farben (das Höchste) – die Leiste muss trotzdem auf den Bildschirm passen
    full = [f"#1{i}2{i}3{i}" for i in range(8)]
    app_page.evaluate("(c) => apiJson('/api/v1/design/paint-colors', {method: 'PUT', json: {colors: c}})", full)
    try:
        _open_background(app_page)
        app_page.locator(".paint-swatches-own .paint-swatch[data-paint-color]").nth(7).wait_for()
        app_page.click('[data-paint-action="mixer"]')
        mixer = app_page.locator(".paint-mixer")
        assert mixer.is_visible()
        for width, height in [(1194, 834), (834, 1194), (1133, 744), (744, 1133)]:
            app_page.set_viewport_size({"width": width, "height": height})
            app_page.wait_for_timeout(150)
            for sel in [".paint-bar-colors", ".paint-bar-tools", ".paint-mixer"]:
                r = app_page.locator(sel).bounding_box()
                assert r["x"] >= 0 and r["y"] >= 0 and r["x"] + r["width"] <= width + 1 \
                    and r["y"] + r["height"] <= height + 1, (sel, width, height)

        # Topf 1 wählen, Blau hinein; danach ist Topf 2 dran: Gelb – heraus kommt Grün, nicht Grau
        app_page.click('.paint-mixer-pot[data-pot="0"]')
        app_page.click('.paint-bar-colors [data-paint-color="#1e88e5"]')
        app_page.click('.paint-bar-colors [data-paint-color="#fdd835"]')
        app_page.locator(".paint-mixer-ratio").fill("50")
        r, g, b = app_page.evaluate("() => mixerRgb(mixerResult())")
        assert g > r + 40 and g > b + 40, (r, g, b)
        # Der Pinsel hat seine Farbe behalten, solange gemischt wird
        assert app_page.evaluate("paintMode.color") not in ("#1e88e5", "#fdd835")

        with app_page.expect_response(lambda res: "/api/v1/design/paint-colors" in res.url) as resp:
            app_page.click('[data-paint-action="m-take"]')
        saved = resp.value.json()["paint_colors"]
        mixed = app_page.evaluate("paintMode.color")
        assert saved[0] == mixed and len(saved) == 8 and full[7] not in saved
        assert not mixer.is_visible()
        assert app_page.locator(f'.paint-swatches-own [data-paint-color="{mixed}"].active').count() == 1
        app_page.click('[data-paint-action="done"]')
        app_page.wait_for_load_state("networkidle")
        assert app_page.problems.errors == []
    finally:
        app_page.evaluate("() => apiJson('/api/v1/design/paint-colors', {method: 'PUT', json: {colors: []}})")


# ---- Kacheln ----
TILE = '#dashboard-subjects-grid [data-paint-tile="{}"]'
KEY = "dashboard/tile/{}"


def test_choosing_marks_tiles_and_a_tap_does_not_open_the_subject(app_page, clean_dashboard):
    app_page.click("#btn-paint")
    app_page.locator(".paint-chooser").wait_for(state="visible")
    assert app_page.evaluate("document.body.classList.contains('paint-choosing')")
    assert app_page.locator(".paint-pick").count() == app_page.locator("#tab-dashboard [data-paint-tile]").count()
    # Abbrechen: nichts passiert, die Seite bleibt
    app_page.tap('[data-paint-choose="cancel"]')
    assert not app_page.evaluate("document.body.classList.contains('paint-choosing')")
    assert app_page.locator(".paint-pick").count() == 0
    assert app_page.locator("#tab-dashboard.active").count() == 1
    # Daneben tippen bricht ebenfalls ab
    app_page.tap("#btn-paint")
    app_page.tap(".paint-pick-shield", position={"x": 5, "y": 5})
    assert app_page.locator(".paint-pick").count() == 0 and app_page.locator("#paint-mode:visible").count() == 0

    # Kachel antippen öffnet den Mal-Modus für die Kachel (nicht das Fach)
    _open_tile(app_page, KEY.format("sub_math"))
    assert app_page.locator("#tab-dashboard.active").count() == 1
    box = app_page.locator(".paint-viewport").bounding_box()
    assert abs(box["width"] - box["height"]) < 1  # Kachelart quadrat
    assert app_page.locator(".paint-ghost-tile .subject-tile-name").inner_text() == "Mathematik"
    assert app_page.locator('[data-paint-action="preview"]').is_visible()
    app_page.click('[data-paint-action="done"]')
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []


def test_subject_tile_picture_stays_on_its_subject(app_page, clean_dashboard):
    # Mathe bekommt ein eigenes Bild
    _open_tile(app_page, KEY.format("sub_math"))
    with app_page.expect_response(_paintings_request("POST"), timeout=6000) as resp:
        app_page.evaluate(PAINT_DRAW, LINE)
    math = resp.value.json()
    assert math["slots"] == ["dashboard/tile/sub_math"] and math["kind"] == "tile" and math["format"] == "quadrat"
    app_page.click('[data-paint-action="done"]')
    app_page.wait_for_function(f"document.querySelector('{TILE.format('sub_math')}').classList.contains('has-paint')")
    assert app_page.locator(f"{TILE.format('sub_bio')}.has-paint").count() == 0

    # Biologie bekommt ein eigenes; keine andere Fach-Kachel übernimmt eins davon
    _open_tile(app_page, KEY.format("sub_bio"))
    assert app_page.locator('[data-paint-action="scope"]').count() == 0  # „für alle“ gibt es nicht mehr
    with app_page.expect_response(_paintings_request("POST"), timeout=6000) as resp:
        app_page.evaluate(PAINT_DRAW, LINE[:6])
    assert resp.value.json()["slots"] == ["dashboard/tile/sub_bio"]
    app_page.click('[data-paint-action="done"]')
    app_page.wait_for_function(f"document.querySelector('{TILE.format('sub_bio')}').classList.contains('has-paint')")
    assert app_page.locator(f"{TILE.format('sub_physics')}.has-paint").count() == 0
    style = lambda sel: app_page.evaluate(f"document.querySelector('{sel}').style.getPropertyValue('--paint-img')")
    assert math["id"] in style(TILE.format("sub_math"))
    assert app_page.problems.errors == []


def test_subject_page_background_and_cards(app_page, clean_dashboard):
    app_page.evaluate("openSubjectDetail('sub_math')")
    app_page.locator("#tab-subject-detail.active").wait_for()
    app_page.wait_for_load_state("networkidle")
    assert app_page.get_attribute("#tab-subject-detail", "data-paint") == "subject-detail/sub_math"
    _open_tile(app_page, "subject-detail/sub_math/tile/tafel")
    box = app_page.locator(".paint-viewport").bounding_box()
    assert abs(box["width"] / box["height"] - 2.4) < 0.05  # Kachelart karte
    with app_page.expect_response(_paintings_request("POST"), timeout=6000) as resp:
        app_page.evaluate(PAINT_DRAW, LINE[:5])
    assert resp.value.json()["slots"] == ["subject-detail/sub_math/tile/tafel"]
    app_page.click('[data-paint-action="done"]')
    app_page.wait_for_function("document.querySelector('[data-paint-tile=\"tafel\"]').classList.contains('has-paint')")

    _open_background(app_page)
    with app_page.expect_response(_paintings_request("POST"), timeout=6000) as resp:
        app_page.evaluate(PAINT_DRAW, LINE)
    assert resp.value.json()["slots"] == ["subject-detail/sub_math"]
    app_page.click('[data-paint-action="done"]')
    app_page.wait_for_function(ON, timeout=5000)

    # Andere Fachseite: kein eigenes Bild, nichts gemeinsames → ohne Bild
    app_page.evaluate("openSubjectDetail('sub_bio')")
    app_page.wait_for_function(f"!{ON}", timeout=5000)
    assert app_page.locator('[data-paint-tile="tafel"].has-paint').count() == 0
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []


def test_ghost_sits_where_the_picture_will_be(app_page, clean_dashboard):
    """Geisterbild = so, wie Seite bzw. Kachel später über dem Bild liegt (Bild randlos eingepasst)."""
    for w, h in [(1194, 834), (834, 1194)]:
        app_page.set_viewport_size({"width": w, "height": h})
        _open_background(app_page)
        _assert_ghost_fits(app_page, ".paint-ghost-page")
        app_page.click('[data-paint-action="done"]')
        for key in [KEY.format("sub_math"), "dashboard/tile/stundenplan"]:
            _open_tile(app_page, key)
            _assert_ghost_fits(app_page, ".paint-ghost-tile")
            app_page.click('[data-paint-action="done"]')
            app_page.locator("#paint-mode").wait_for(state="hidden")
    assert app_page.problems.errors == []


RECTS = """() => [...document.querySelectorAll(
  '#tab-dashboard .section-title, #tab-dashboard .subject-app-tile, .subject-tile-name, .dash-tt-title, .dash-tt-empty, .header')]
  .map((e) => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.height)]; })"""


def test_painted_surfaces_do_not_move_the_layout(app_page):
    # Sonst passte das Geisterbild (ohne Bild aufgenommen) nicht mehr zur Seite mit Bild
    app_page.wait_for_load_state("networkidle")
    before = app_page.evaluate(RECTS)
    app_page.evaluate("""() => {
      document.body.classList.add('paint-bg-on');
      document.querySelectorAll('[data-paint-tile]').forEach((el) => {
        el.classList.add('has-paint'); el.style.setProperty('--paint-img', 'none'); });
    }""")
    assert app_page.evaluate(RECTS) == before
    app_page.evaluate("applyPaintings()")


def test_ghost_tiles_lie_exactly_over_the_real_tiles(app_page, clean_dashboard):
    for w, h in [(1194, 834), (834, 1194)]:
        app_page.set_viewport_size({"width": w, "height": h})
        _open_background(app_page)
        # Geisterbild zurückrechnen: Bildschirmpunkt = (Punkt im Bild − Versatz) / Maßstab
        off = app_page.evaluate("""() => {
          const v = document.querySelector('.paint-viewport').getBoundingClientRect();
          const g = document.querySelector('.paint-ghost-page').getBoundingClientRect();
          const k = g.width / innerWidth;
          const back = (el) => { const r = el.getBoundingClientRect();
            return [(r.left - g.left) / k, (r.top - g.top) / k]; };
          const all = (sel) => [...document.querySelectorAll(sel)].filter((el) => el.getClientRects().length);
          const ghost = [...all('.paint-ghost .subject-app-tile'), ...all('.paint-ghost .nav-tab')].map(back);
          const real = [...all('#tab-dashboard .subject-app-tile'), ...all('.app-container > .header .nav-tab')]
            .filter((el) => !el.closest('.paint-ghost'))  // der Klon trägt dieselben IDs und Klassen
            .map((el) => { const r = el.getBoundingClientRect(); return [r.left, r.top]; });
          if (ghost.length !== real.length) return [ghost.length, real.length, 'Anzahl'];
          return ghost.map((p, i) => Math.max(Math.abs(p[0] - real[i][0]), Math.abs(p[1] - real[i][1])));
        }""")
        assert off and max(off) < 1.5, (w, h, off)
        app_page.click('[data-paint-action="done"]')
        app_page.locator("#paint-mode").wait_for(state="hidden")
    assert app_page.problems.errors == []


def test_done_closes_at_once_and_saving_finishes_in_the_background(app_page, clean_dashboard):
    """Großes Bild auf dem iPad: Speichern dauert Sekunden – der Haken schließt trotzdem sofort (26.10.)."""
    held = []
    app_page.route("**/api/v1/paintings", lambda route: held.append(route) if route.request.method == "POST"
                   else route.continue_())
    _open_background(app_page)
    app_page.evaluate(PAINT_DRAW, LINE)
    for _ in range(40):  # die Speicherung startet nach kurzer Pause und hängt dann fest
        if held:
            break
        app_page.wait_for_timeout(100)
    assert held, "Speichern wurde nicht gestartet"
    app_page.click('[data-paint-action="done"]')
    app_page.locator("#paint-mode").wait_for(state="hidden", timeout=1000)  # sofort zu
    assert app_page.evaluate(ON) is False                                    # Bild noch nicht da
    held[0].continue_()
    app_page.wait_for_function(ON, timeout=8000)                             # nach dem Speichern sichtbar
    app_page.unroute("**/api/v1/paintings")
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []
