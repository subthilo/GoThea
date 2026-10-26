"""Ausmalbild im Mal-Modus: wählen, platzieren, im Feld malen (die Farbe bleibt im Feld), speichern,
verschieben (die Farbe wandert mit), Linien dicker – und nach dem Wiederöffnen ist alles wieder da."""
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

# Farbige Pixel in einem Streifen der Malfläche (x0..x1 in Rastereinheiten, 0..1000)
INK_IN = """([x0, x1]) => {
  const c = document.querySelector('.paint-ink');
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
    assert app_page.locator(".paint-lines svg path").count() >= 1
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
    app_page.click('[data-paint-action="c-place"]')

    # Linien dicker, dann fertig; wieder öffnen: Ausmalbild, Linienstärke und Farbe sind da
    app_page.click('[data-paint-action="c-thick"]')
    app_page.click('[data-paint-action="done"]')
    app_page.locator("#paint-mode").wait_for(state="hidden")
    _open_background(app_page)
    app_page.wait_for_function("coloring.pages.length === 1 && paintMode.surface.strokes.length === 1", timeout=8000)
    assert app_page.evaluate("coloring.pages[0].delta") > 0
    assert app_page.locator(".paint-lines svg path").count() >= 1
    app_page.click('[data-paint-action="done"]')
    app_page.wait_for_load_state("networkidle")
    assert app_page.problems.errors == []

