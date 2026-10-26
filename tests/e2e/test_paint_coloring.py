"""Ausmalbild im Mal-Modus: wählen, platzieren, im Feld malen (die Farbe bleibt im Feld), speichern,
verschieben (die Farbe wandert mit), Linien dicker – und nach dem Wiederöffnen ist alles wieder da.
Ebenen: ausblenden, Feld-Schalter, Reihenfolge."""
import json

import pytest

# clean_dashboard: Fixture aus test_paintings (räumt die gemalten Bilder des geteilten Testservers weg)
from tests.e2e.test_paintings import PAINT_DRAW, _open_background, _paintings_request, clean_dashboard  # noqa: F401

pytest.importorskip("shapely")

# Rahmen mit Loch, senkrechter Balken in der Mitte: zwei Felder (links, rechts)
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
       '<path fill-rule="evenodd" d="M0 0H100V100H0Z M10 10H90V90H10Z"/><rect x="48" y="10" width="4" height="80"/></svg>')

UPLOAD = """async (svg) => {
  const form = new FormData();
  form.append('name', 'Zwei Felder E2E');
  form.append('file', new Blob([svg], {type: 'image/svg+xml'}), 'zwei.svg');
  const page = await apiJson('/api/v1/coloring-pages', {method: 'POST', body: form});
  for (let i = 0; i < 40; i++) {
    const p = (await apiJson('/api/v1/coloring-pages')).find((x) => x.id === page.id);
    if (p.status === 'berechnet') break;
    await new Promise((r) => setTimeout(r, 250));
  }
  await apiJson(`/api/v1/coloring-pages/${page.id}/freigabe`, {method: 'PUT', json: {freigegeben: true}});
  return page.id;
}"""

# Farbige Pixel in einem Streifen einer Leinwand (x0..x1 in Rastereinheiten, 0..1000): Zeichenkern
# (aktive Ebene) oder Ebenen darüber (Linien der aktiven Ebene und alles davor)
INK_IN = """([x0, x1, sel]) => {
  const c = document.querySelector(sel || '.paint-ink');
  const g = c.getContext('2d'), k = c.width / 1000;
  const d = g.getImageData(Math.round(x0 * k), Math.round(480 * k), Math.round((x1 - x0) * k), Math.round(40 * k)).data;
  let n = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
  return n;
}"""


@pytest.fixture
def coloring_page(app_page, parent_pin):
    app_page.click("#btn-parent-toggle")
    app_page.fill("#input-parent-pin", parent_pin)
    app_page.click("#btn-submit-parent-pin")
    app_page.wait_for_function("document.body.classList.contains('parent-mode-active')")
    page_id = app_page.evaluate(UPLOAD, SVG)
    app_page.click("#btn-parent-toggle")  # zurück in Theas Modus
    app_page.wait_for_function("document.body.classList.contains('thea-mode-active')")
    yield page_id


def _units_to_px(app_page, ux, uy):
    w = app_page.evaluate("paintMode.w")
    return [ux * w / 1000, uy * w / 1000]


@pytest.mark.usefixtures("clean_dashboard")
def test_colour_stays_in_its_field_and_moves_with_the_page(app_page, coloring_page):
    _open_background(app_page)
    app_page.click('[data-paint-action="coloring"]')
    # Der Testserver wird geteilt: genau das eigene Ausmalbild wählen, nicht „das letzte“
    app_page.locator(f'.paint-coloring-choice[data-coloring-id="{coloring_page}"]').click()
    app_page.wait_for_function("coloring.pages.length === 1 && coloring.placing")
    assert app_page.evaluate(INK_IN, [100, 900, ".paint-layer-above"]) > 0  # Linien
    app_page.click('[data-paint-action="c-place"]')  # fertig platziert
    assert app_page.evaluate("coloring.placing") is False

    # Seite: Mitte 500/500, Breite 800 → linkes Feld etwa x 180–484, rechtes 516–820 (Rastereinheiten)
    pts = [_units_to_px(app_page, x, 500) for x in range(300, 720, 20)]
    with app_page.expect_response(_paintings_request("POST"), timeout=8000) as resp:
        app_page.evaluate(PAINT_DRAW, pts)
    assert app_page.evaluate(INK_IN, [250, 470]) > 0       # links gemalt
    assert app_page.evaluate(INK_IN, [540, 800]) == 0      # rechts nichts – die Farbe bleibt im Feld
    painting = app_page.evaluate("(id) => apiJson(`/api/v1/paintings/${id}`)", resp.value.json()["id"])
    saved = json.loads(painting["strokes_json"])
    assert saved["pages"][0]["id"] == coloring_page
    uid = saved["pages"][0]["uid"]
    assert saved["strokes"][0]["clip"].startswith(f"{uid}:")

    # Verschieben: die Farbe wandert mit
    before = app_page.evaluate("paintMode.surface.strokes[0].points[0].x")
    app_page.click('[data-paint-action="c-place"]')
    box = app_page.locator(".paint-placing").bounding_box()
    app_page.evaluate("""([x0, y0, dx]) => {
      const o = document.querySelector('.paint-placing');
      const fire = (type, x) => o.dispatchEvent(new PointerEvent(type, {pointerId: 3, pointerType: 'pen',
        clientX: x, clientY: y0, bubbles: true, cancelable: true}));
      fire('pointerdown', x0); fire('pointermove', x0 + dx / 2); fire('pointermove', x0 + dx); fire('pointerup', x0 + dx);
    }""", [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, 60])
    app_page.wait_for_timeout(100)
    after = app_page.evaluate("paintMode.surface.strokes[0].points[0].x")
    assert abs(after - before - 60) < 1

    # Linien dicker (in der Leiste beim Bearbeiten), dann fertig; wieder öffnen: alles ist da
    app_page.click('[data-paint-action="c-thick"]')
    app_page.click('[data-paint-action="c-place"]')
    app_page.click('[data-paint-action="done"]')
    app_page.locator("#paint-mode").wait_for(state="hidden")
    _open_background(app_page)
    app_page.wait_for_function("coloring.pages.length === 1 && coloringAllStrokes().length === 1", timeout=8000)
    assert app_page.evaluate("coloring.pages[0].delta") > 0
    assert app_page.evaluate(INK_IN, [100, 900, ".paint-layer-above"]) > 0
    app_page.click('[data-paint-action="done"]')
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []


@pytest.mark.usefixtures("clean_dashboard")
def test_no_released_pages_no_button(app_page):
    # Ohne freigegebene Ausmalbilder gibt es den Knopf nicht (eine leere Auswahl sähe aus wie „lädt noch“)
    app_page.route("**/api/v1/coloring-pages", lambda route: route.fulfill(json=[]))
    _open_background(app_page)
    app_page.wait_for_load_state("networkidle")
    assert app_page.locator('[data-paint-action="coloring"]').is_hidden()
    app_page.click('[data-paint-action="done"]')
    assert app_page.problems.errors == []


def _add_page(app_page, page_id):
    app_page.click('[data-paint-action="coloring"]')
    app_page.locator(f'.paint-coloring-choice[data-coloring-id="{page_id}"]').click()
    app_page.wait_for_function("coloring.placing")


def _saved(app_page):
    """Gespeicherter Stand nach dem nächsten Speichern."""
    with app_page.expect_response(lambda r: r.request.method in ("POST", "PUT") and "/api/v1/paintings" in r.url
                                  and "/slots/" not in r.url, timeout=8000) as resp:
        app_page.evaluate("flushPaintSave()")
    painting = app_page.evaluate("(id) => apiJson(`/api/v1/paintings/${id}`)", resp.value.json()["id"])
    return json.loads(painting["strokes_json"])


@pytest.mark.usefixtures("clean_dashboard")
def test_coloring_pages_are_layers(app_page, coloring_page):
    _open_background(app_page)
    # Bearbeiten liegt außerhalb der Malfläche: zwei Finger zoomen dort nicht die Malfläche mit
    assert app_page.evaluate("!paintMode.viewport.contains(document.querySelector('.paint-placing'))")
    _add_page(app_page, coloring_page)
    app_page.click('[data-paint-action="c-place"]')
    stroke = [_units_to_px(app_page, x, 500) for x in range(300, 720, 20)]
    app_page.evaluate(PAINT_DRAW, stroke)
    assert app_page.evaluate("coloring.active") == app_page.evaluate("coloring.pages[0].uid")

    # Ausblenden: Linien und Farbe weg, der Stift malt dort auf dem Hintergrund
    app_page.click('[data-paint-action="c-place"]')
    app_page.click('[data-paint-action="c-hide"]')
    app_page.click('[data-paint-action="c-place"]')
    assert app_page.evaluate("coloring.active") == "bg"
    assert app_page.evaluate(INK_IN, [100, 900, ".paint-layer-above"]) == 0
    assert app_page.evaluate(INK_IN, [100, 900]) == 0
    app_page.evaluate(PAINT_DRAW, stroke)
    assert app_page.evaluate(INK_IN, [540, 800]) > 0  # über die ganze Breite, nicht nur im Feld
    saved = _saved(app_page)
    assert saved["pages"][0]["hidden"] is True
    assert sorted("clip" in st for st in saved["strokes"]) == [False, True]

    # Rückgängig trifft den letzten Strich, auch wenn er auf einer anderen Ebene liegt
    app_page.click('[data-paint-action="undo"]')
    assert app_page.evaluate("coloringAllStrokes().length") == 1

    # Wieder einblenden, Feld-Schalter aus: der Strich geht über beide Felder, bleibt im Umriss
    app_page.click('[data-paint-action="c-place"]')
    app_page.click('[data-paint-action="c-hide"]')
    app_page.click('[data-paint-action="c-free"]')
    app_page.click('[data-paint-action="c-place"]')
    app_page.evaluate(PAINT_DRAW, stroke)
    assert app_page.evaluate(INK_IN, [540, 800]) > 0
    uid = app_page.evaluate("coloring.pages[0].uid")
    assert app_page.evaluate("paintMode.surface.strokes.at(-1).clip") == f"{uid}:o"

    # Zweites Ausmalbild liegt vorn; nach hinten schieben
    _add_page(app_page, coloring_page)
    first, second = app_page.evaluate("coloring.pages.map((p) => p.uid)")
    assert app_page.locator(".paint-layer-choice").count() == 2
    app_page.click('[data-paint-action="c-back"]')
    assert app_page.evaluate("coloring.pages.map((p) => p.uid)") == [second, first]
    saved = _saved(app_page)
    assert [p["uid"] for p in saved["pages"]] == [second, first]
    assert saved["pages"][1]["free"] is True
    app_page.click('[data-paint-action="done"]')
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []
