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
