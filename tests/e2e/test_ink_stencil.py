"""Schablone im Zeichenkern (Ausmalbilder): der Strich bleibt in dem Feld, in dem der Stift aufsetzt –
live und nach dem Neuzeichnen. Ohne Schablone verhält sich der Kern wie bisher."""

SETUP = """(withStencil) => {
  const box = document.createElement('div');
  box.id = 'stencil-test';
  box.style.cssText = 'position:fixed;left:0;top:0;width:400px;height:200px;z-index:9999;background:#fff';
  box.innerHTML = '<canvas class="ink" style="position:absolute;inset:0;touch-action:none"></canvas><canvas class="ov" style="position:absolute;inset:0;pointer-events:none"></canvas>';
  document.body.appendChild(box);
  const ink = box.querySelector('.ink'), ov = box.querySelector('.ov');
  const halves = { links: new Path2D('M0 0H200V200H0Z'), rechts: new Path2D('M200 0H400V200H200Z') };
  const env = {
    viewport: box, inkCanvas: ink, overlayCanvas: ov,
    btnScrollTop: null, scrollTrack: null, scrollThumb: null,
    btnWbZoomIn: null, btnWbZoomOut: null, btnWbZoomReset: null, wbZoomLevelText: null,
    docUnderlay: null, docUnderlayImg: null, tasksLayer: null,
    inkCtx: ink.getContext('2d'), overlayCtx: ov.getContext('2d'),
    stopTutorSpeech: () => {}, scheduleAutoSave: () => {}, sendCanvasUpdate: () => {},
  };
  if (withStencil) {
    env.clipForPoint = (pt) => (pt.x < 200 ? 'links' : 'rechts');
    env.clipPath = (key) => halves[key];
  }
  window.__stencil = createInkSurface(env);
  window.__stencil.resizeCanvases();
  window.__stencil.currentColor = '#e53935';
  window.__stencil.currentBaseWidth = 10;
}"""

DRAW = """() => {
  const c = document.querySelector('#stencil-test .ink');
  const r = c.getBoundingClientRect();
  const fire = (type, x, y, p) => c.dispatchEvent(new PointerEvent(type, {pointerId: 9, pointerType: 'pen',
    pressure: p, isPrimary: true, clientX: r.left + x, clientY: r.top + y, bubbles: true, cancelable: true}));
  fire('pointerdown', 100, 100, 0.7);
  for (let x = 110; x <= 300; x += 10) fire('pointermove', x, 100, 0.7);
  fire('pointerup', 300, 100, 0);
}"""

# Farbige Pixel links bzw. rechts der Mitte (Zeichenfläche in Gerätepixeln)
INK = """() => {
  const c = document.querySelector('#stencil-test .ink');
  const g = c.getContext('2d'), w = c.width, h = c.height;
  const count = (x0, x1) => { const d = g.getImageData(x0, 0, x1 - x0, h).data; let n = 0;
    for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n; };
  return { links: count(0, Math.floor(w / 2) - 2), rechts: count(Math.ceil(w / 2) + 2, w) };
}"""


def _run(page, with_stencil):
    page.evaluate("() => document.getElementById('stencil-test')?.remove()")
    page.evaluate(SETUP, with_stencil)
    page.evaluate(DRAW)
    live = page.evaluate(INK)
    page.evaluate("() => window.__stencil.redrawAllStrokes()")
    return live, page.evaluate(INK), page.evaluate("() => window.__stencil.strokes.map((s) => s.clip ?? null)")


def test_stroke_stays_in_the_field_where_the_pen_lands(app_page):
    live, redrawn, clips = _run(app_page, True)
    assert live["links"] > 0 and live["rechts"] == 0, live
    assert redrawn["links"] > 0 and redrawn["rechts"] == 0, redrawn
    assert clips == ["links"]
    assert app_page.problems.errors == []


def test_without_stencil_the_core_draws_as_before(app_page):
    live, redrawn, clips = _run(app_page, False)
    assert live["links"] > 0 and live["rechts"] > 0
    assert redrawn["links"] > 0 and redrawn["rechts"] > 0
    assert clips == [None]
    assert app_page.problems.errors == []
