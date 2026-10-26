// ============================================================================
// Ausmalbilder im Mal-Modus (Konzept-Doc, Tab „Ausmalbilder“)
// ============================================================================
// Jedes Ausmalbild ist eine eigene Ebene mit seinen Linien und seiner Farbe; ganz unten liegt der
// Hintergrund. Weiter oben liegende Ausmalbilder verdecken mit Farbe und Linien, was darunter liegt,
// unbemalte Felder bleiben durchsichtig. Der Stift malt auf der obersten sichtbaren Ebene, auf der er
// aufsetzt: der Zeichenkern fragt beim Aufsetzen über die Schablone (clipForPoint/clipPath) nach dem
// Feld; dabei wird diese Ebene die aktive. Feld-Schalter je Ausmalbild: an = der Strich bleibt im Feld,
// aus = er bleibt nur im Umriss des Ausmalbilds und liegt hinter den Linien.
//
// Darstellung ohne Änderung am Zeichenkern: der Kern hält und zeichnet nur die Striche der aktiven Ebene
// (surface.strokes = deren Liste); alles darunter liegt auf einer eigenen Leinwand unter seiner, die
// Linien der aktiven Ebene und alles darüber auf einer darüber. So radiert der Radierer nur in der
// aktiven Ebene, und Linien bleiben beim Malen über der Farbe.
//
// Bearbeiten (Hand-Knopf): eigene Ebene über der Bühne (nicht in der Malfläche – sonst zoomte der Kern
// bei zwei Fingern mit). Ein Finger/Stift verschiebt, zwei Finger drehen und skalieren (Mac: Mausrad,
// mit Umschalttaste drehen); unten die Leiste der Ausmalbilder: auswählen, ein-/ausblenden, Feld-
// Schalter, nach hinten/vorn, Linien dünner/dicker/Farbe, entfernen.
//
// Platzierung in Rastereinheiten des Bildes (wie die Striche): Mitte cx/cy, Breite size, Drehung rot (Grad).
// Reihenfolge von coloring.pages = Ebenen von hinten nach vorn.
// Schlüssel eines Strichs: "<uid>:<Feld-ID>"; "<uid>:o" = im Umriss (Feld-Schalter aus); "<uid>:x" = auf
// der Linie (malt nichts); ohne Schlüssel oder "bg" = Hintergrund.
// Verschiebt Thea ein Ausmalbild später, wandert ihre Farbe darin mit.

const COLORING_LINE_DELTAS = [-1.2, -0.6, 0, 1, 2.5, 5];  // dünner/dicker, Einheiten des Ausmalbilds
const COLORING_LINE_FALLBACK = "#111111";
const COLORING_SETTLE_MS = 150;  // nach Zoomen/Verschieben die Ebenen scharf neu zeichnen

// Startfarbe der Linien: die Schriftfarbe des Schemas – hell auf dunklen, dunkel auf hellen Schemen
// (schwarze Linien verschwänden auf dunklem Grund)
function coloringDefaultLineColor() {
  const c = getComputedStyle(document.documentElement).getPropertyValue("--text-primary").trim();
  return /^#[0-9a-f]{6}$/i.test(c) ? c : COLORING_LINE_FALLBACK;
}
const COLORING_MIN_SIZE = 60;   // kleinste Breite in Rastereinheiten

const coloring = {
  pages: [],           // { uid, id, v, cx, cy, size, rot, color, delta, hidden?, free? }
  shapes: new Map(),   // id → { width, height, bleed, ink, outline, fields: [{ id, path, box }] }
  catalog: new Map(),  // id → Ausmalbild aus der Liste (Vorschaubild für die Leiste)
  layers: new Map(),   // "bg" bzw. uid → Striche dieser Ebene (Punkte der Malfläche)
  active: "bg",        // Ebene, deren Striche gerade im Zeichenkern liegen
  pxCache: new Map(),  // Schlüssel → Path2D in Punkten der Malfläche
  selected: null,
  placing: false,
  scale: 1,            // Punkte der Malfläche je Rastereinheit
  hit: document.createElement("canvas").getContext("2d"),
  scratch: [document.createElement("canvas"), document.createElement("canvas")],
  rendered: null,      // { scale, panX, panY } der zuletzt scharf gezeichneten Ebenen
  settleTimer: null,
  pointers: new Map(),
  frame: 0,
};

// Den Knopf „Ausmalbild“ gibt es nur, wenn es freigegebene Ausmalbilder gibt (sonst sähe Thea eine leere
// Auswahl, die wie „lädt noch“ aussieht)
async function coloringRefreshAvailable() {
  const btn = paintMode.el && paintMode.el.querySelector('[data-paint-action="coloring"]');
  if (!btn) return;
  btn.hidden = true;
  try {
    const list = await apiJson("/api/v1/coloring-pages");
    list.forEach((pg) => coloring.catalog.set(pg.id, pg));
    btn.hidden = !list.length;
    coloringRenderStrip();
  } catch (err) {
    console.warn("Ausmalbilder nicht geladen:", err);
  }
}

function coloringReset() {
  coloring.pages = [];
  coloring.selected = null;
  coloring.placing = false;
  coloring.pxCache.clear();
  coloring.pointers.clear();
  coloringSetStrokes([]);
}

function coloringUnitsHeight() {
  return PAINT_UNITS / (paintMode.target ? paintMode.target.aspect : 1);
}

// ---- Ebenen ----
function coloringLayerOf(stroke) {
  const key = stroke && typeof stroke.clip === "string" ? stroke.clip : "";
  const uid = key.includes(":") ? key.split(":")[0] : "";
  return uid && coloring.pages.some((p) => p.uid === uid) ? uid : "bg";
}

function coloringLayer(id) {
  if (!coloring.layers.has(id)) coloring.layers.set(id, []);
  return coloring.layers.get(id);
}

// Alle Striche auf ihre Ebenen verteilen; der Kern hält danach die der aktiven Ebene
function coloringSetStrokes(strokes) {
  coloring.layers = new Map([["bg", []]]);
  coloring.pages.forEach((p) => coloring.layers.set(p.uid, []));
  strokes.forEach((st) => coloringLayer(coloringLayerOf(st)).push(st));
  coloring.active = "bg";
  if (paintMode.surface) paintMode.surface.strokes = coloringLayer("bg");
}

// Alle Striche, von hinten nach vorn (zum Speichern und Skalieren)
function coloringAllStrokes() {
  return ["bg", ...coloring.pages.map((p) => p.uid)].flatMap((id) => coloring.layers.get(id) || []);
}

function coloringActivate(id) {
  if (coloring.active === id && paintMode.surface.strokes === coloringLayer(id)) return;
  coloring.active = id;
  paintMode.surface.strokes = coloringLayer(id);
  paintMode.surface.redrawAllStrokes();
  coloringRenderLayers();
}

// ---- Formen laden ----
function coloringBox(d) {
  const nums = d.match(/-?\d+(\.\d+)?/g) || [];
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i + 1 < nums.length; i += 2) {
    const x = +nums[i], y = +nums[i + 1];
    if (x < x0) x0 = x; if (x > x1) x1 = x;
    if (y < y0) y0 = y; if (y > y1) y1 = y;
  }
  return [x0, y0, x1, y1];
}

async function coloringFetchShapes(id, v) {
  if (coloring.shapes.has(id)) return coloring.shapes.get(id);
  const data = await apiJson(`/api/v1/coloring-pages/${encodeURIComponent(id)}/shapes?v=${v || 0}`);
  const shapes = {
    width: data.width, height: data.height, bleed: data.bleed || 0, inkD: data.ink,
    ink: new Path2D(data.ink), outline: new Path2D(data.outline),
    fields: data.fields.map((f) => ({ id: f.id, path: new Path2D(f.d), box: coloringBox(f.d) })),
  };
  coloring.shapes.set(id, shapes);
  return shapes;
}

// Ausmalbilder eines gespeicherten Bildes laden und seine Striche auf die Ebenen verteilen; schon während
// des Ladens Gemaltes bleibt obenauf
async function coloringLoad(pages, strokes) {
  const list = Array.isArray(pages) ? pages : [];
  await Promise.all(list.map((p) => coloringFetchShapes(p.id, p.v).catch((err) => console.warn("Ausmalbild fehlt:", err))));
  strokes = strokes.concat(coloringAllStrokes());
  coloring.pages = list.filter((p) => coloring.shapes.has(p.id)).map((p) => ({ ...p }));
  coloring.selected = null;
  coloring.placing = false;
  coloring.pxCache.clear();
  coloringSetStrokes(strokes);
}

// ---- Geometrie ----
// Ausmalbild (eigenes 1000er-Raster) → Ziel (k = Punkte je Rastereinheit des Bildes; 1 = Rastereinheiten)
function coloringMatrix(p, k) {
  const s = coloring.shapes.get(p.id);
  return new DOMMatrix().scaleSelf(k, k).translateSelf(p.cx, p.cy).rotateSelf(p.rot)
    .scaleSelf(p.size / s.width, p.size / s.width).translateSelf(-s.width / 2, -s.height / 2);
}

// Pfad eines Strich-Schlüssels (null = Hintergrund, ohne Begrenzung). pages: die aktuellen oder die
// einer Momentaufnahme fürs Speichern
function coloringBuildClip(key, k, pages = coloring.pages) {
  if (key == null || key === "bg") return null;
  const path = new Path2D();
  const [uid, fid] = String(key).split(":");
  const page = pages.find((p) => p.uid === uid);
  if (!page || fid === "x") return path;  // leer: malt nichts
  const shapes = coloring.shapes.get(page.id);
  if (fid === "o") {
    path.addPath(shapes.outline, coloringMatrix(page, k));
    return path;
  }
  const field = shapes.fields.find((f) => String(f.id) === fid);
  if (field) path.addPath(field.path, coloringMatrix(page, k));
  return path;
}

// Schablone für den Zeichenkern: Ebene und Feld unter dem Stift (Punkte der Malfläche). Macht die Ebene
// zur aktiven – der Kern legt den neuen Strich danach in deren Liste.
function coloringClipForPoint(pt) {
  if (!coloring.pages.length || coloring.placing) return null;
  for (let i = coloring.pages.length - 1; i >= 0; i--) {
    const p = coloring.pages[i];
    if (p.hidden) continue;
    const s = coloring.shapes.get(p.id);
    const q = coloringMatrix(p, coloring.scale).inverse().transformPoint(new DOMPoint(pt.x, pt.y));
    if (!coloring.hit.isPointInPath(s.outline, q.x, q.y, "evenodd")) continue;
    coloringActivate(p.uid);
    if (p.free) return `${p.uid}:o`;
    for (const f of s.fields) {
      const b = f.box;
      if (q.x < b[0] || q.x > b[2] || q.y < b[1] || q.y > b[3]) continue;
      if (coloring.hit.isPointInPath(f.path, q.x, q.y, "evenodd")) return `${p.uid}:${f.id}`;
    }
    return `${p.uid}:x`;
  }
  coloringActivate("bg");
  return null;
}

function coloringClipPath(key) {
  if (!coloring.pages.length) return null;
  if (!coloring.pxCache.has(key)) coloring.pxCache.set(key, coloringBuildClip(key, coloring.scale));
  return coloring.pxCache.get(key);
}

// ---- Zeichnen der Ebenen ----
// Linien eines Ausmalbilds; ctx steht auf Punkten mit k Punkten je Rastereinheit
function coloringDrawPageLines(ctx, p, k) {
  const s = coloring.shapes.get(p.id);
  if (!s) return;
  const delta = Math.max(p.delta || 0, -s.bleed * 0.9);
  ctx.save();
  const m = coloringMatrix(p, k);
  ctx.transform(m.a, m.b, m.c, m.d, m.e, m.f);
  ctx.fillStyle = p.color;
  ctx.fill(s.ink, "evenodd");
  if (delta) {
    // Dünner: der Rand wird weggeradiert – deshalb zeichnet coloringDrawLayer Linien auf eine eigene Fläche
    ctx.lineJoin = "round";
    ctx.lineWidth = Math.abs(delta) * 2;
    ctx.strokeStyle = p.color;
    if (delta < 0) ctx.globalCompositeOperation = "destination-out";
    ctx.stroke(s.ink);
  }
  ctx.restore();
}

function coloringScratch(i, w, h, m) {
  const c = coloring.scratch[i];
  if (c.width !== w || c.height !== h) {
    c.width = w;
    c.height = h;
  }
  const ctx = c.getContext("2d");
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, w, h);
  ctx.setTransform(m);
  return ctx;
}

// Eine Ebene (Striche und/oder Linien) auf eine eigene Fläche zeichnen und dann übernehmen: Radierer und
// dünnere Linien wirken so nur in dieser Ebene. m = Transformation Malfläche → Pixel des Ziels;
// clipFor(key) liefert die Begrenzung eines Strichs in derselben Einheit wie die Striche.
function coloringDrawLayer(target, m, strokes, page, k, clipFor) {
  const w = target.canvas.width, h = target.canvas.height;
  const ctx = coloringScratch(0, w, h, m);
  strokes.forEach((st) => {
    ctx.save();
    const path = clipFor(st.clip);
    if (path) ctx.clip(path, "evenodd");
    paintMode.surface.renderStrokeToContext(ctx, { ...st, clip: undefined });
    ctx.restore();
  });
  if (page) {
    const lines = coloringScratch(1, w, h, m);
    coloringDrawPageLines(lines, page, k);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(lines.canvas, 0, 0);
  }
  target.save();
  target.setTransform(1, 0, 0, 1, 0, 0);
  target.drawImage(ctx.canvas, 0, 0);
  target.restore();
}

// Sichtbare Ebenen [from, to) von hinten nach vorn; von linesOnly nur die Linien (deren Striche hält der Kern)
function coloringDrawLayers(target, m, layers, pages, k, clipFor, from = 0, to = Infinity, linesOnly = null) {
  const order = [{ id: "bg", page: null }, ...pages.filter((p) => !p.hidden).map((p) => ({ id: p.uid, page: p }))];
  order.slice(from, to).forEach(({ id, page }) => {
    const strokes = id === linesOnly ? [] : (layers.get(id) || []);
    if (strokes.length || page) coloringDrawLayer(target, m, strokes, page, k, clipFor);
  });
}

// Leinwände unter und über dem Zeichenkern neu zeichnen (scharf, in der aktuellen Lage)
function coloringRenderLayers() {
  const below = paintMode.layerBelow, above = paintMode.layerAbove, s = paintMode.surface;
  if (!below || !s) return;
  const visible = coloring.pages.filter((p) => !p.hidden);
  if (coloring.active !== "bg" && !visible.some((p) => p.uid === coloring.active)) {
    // Die aktive Ebene wurde ausgeblendet oder entfernt: der Kern übernimmt den Hintergrund
    coloring.active = "bg";
    s.strokes = coloringLayer("bg");
    s.redrawAllStrokes();
  }
  const ink = paintMode.viewport.querySelector(".paint-ink");
  [below, above].forEach((c) => {
    if (c.width !== ink.width || c.height !== ink.height) {
      c.width = ink.width;
      c.height = ink.height;
    }
    c.style.width = ink.style.width;
    c.style.height = ink.style.height;
    c.style.transform = "";
    c.getContext("2d").clearRect(0, 0, c.width, c.height);
  });
  const dpr = s.dpr;
  const m = new DOMMatrix([dpr * s.scale, 0, 0, dpr * s.scale, s.panX * dpr, s.panY * dpr]);
  coloring.rendered = { scale: s.scale, panX: s.panX, panY: s.panY };
  const idx = coloring.active === "bg" ? 0 : 1 + visible.findIndex((p) => p.uid === coloring.active);
  const clip = (key) => coloringClipPath(key);
  coloringDrawLayers(below.getContext("2d"), m, coloring.layers, coloring.pages, coloring.scale, clip, 0, idx);
  coloringDrawLayers(above.getContext("2d"), m, coloring.layers, coloring.pages, coloring.scale, clip, idx,
    Infinity, coloring.active);
}

// Der Kern hat verschoben oder gezoomt (er setzt dabei die Lage der Linien-Ebene): die Leinwände sofort
// per CSS mitbewegen, nach einer kurzen Pause scharf neu zeichnen
function coloringFollowView() {
  const r = coloring.rendered, s = paintMode.surface;
  if (!r || !paintMode.layerBelow) return;
  if (r.scale === s.scale && r.panX === s.panX && r.panY === s.panY) return;
  const f = s.scale / r.scale;
  const t = `translate(${s.panX - r.panX * f}px, ${s.panY - r.panY * f}px) scale(${f})`;
  paintMode.layerBelow.style.transform = t;
  paintMode.layerAbove.style.transform = t;
  clearTimeout(coloring.settleTimer);
  coloring.settleTimer = setTimeout(coloringRenderLayers, COLORING_SETTLE_MS);
}

// Fürs fertige Bild: ctx steht auf Rastereinheiten des Bildes; Striche in Rastereinheiten
function coloringRenderImage(ctx, strokes, pages) {
  const clips = new Map();  // jedes Feld nur einmal als Pfad bauen (viele Striche liegen im selben Feld)
  const clipFor = (key) => {
    if (!clips.has(key)) clips.set(key, coloringBuildClip(key, 1, pages));
    return clips.get(key);
  };
  const layers = new Map([["bg", []]]);
  strokes.forEach((st) => {
    const uid = typeof st.clip === "string" && st.clip.includes(":") ? st.clip.split(":")[0] : "";
    const id = uid && pages.some((p) => p.uid === uid) ? uid : "bg";
    if (!layers.has(id)) layers.set(id, []);
    layers.get(id).push(st);
  });
  coloringDrawLayers(ctx, ctx.getTransform(), layers, pages, 1, clipFor);
}

// ---- Rahmen, Leiste, Knöpfe ----
function coloringRender() {
  const layer = paintMode.linesLayer;
  if (!layer) return;
  const w = paintMode.w, h = paintMode.h;
  layer.style.width = `${w}px`;
  layer.style.height = `${h}px`;
  // Rahmen um das gewählte Ausmalbild beim Bearbeiten (die Ebene zoomt mit, der Kern bewegt sie)
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("width", w);
  svg.setAttribute("height", h);
  const p = coloring.placing && coloringSelectedPage();
  if (p && !p.hidden) {
    const s = coloring.shapes.get(p.id), m = coloringMatrix(p, coloring.scale);
    const g = document.createElementNS(ns, "g");
    g.setAttribute("transform", `matrix(${m.a} ${m.b} ${m.c} ${m.d} ${m.e} ${m.f})`);
    const frame = document.createElementNS(ns, "rect");
    frame.setAttribute("width", s.width);
    frame.setAttribute("height", s.height);
    frame.setAttribute("class", "paint-coloring-frame");
    frame.setAttribute("vector-effect", "non-scaling-stroke");
    g.appendChild(frame);
    svg.appendChild(g);
  }
  layer.replaceChildren(svg);
  const place = paintMode.el.querySelector('[data-paint-action="c-place"]');
  place.hidden = !coloring.pages.length;
  place.classList.toggle("active", coloring.placing);
  paintMode.el.querySelector(".paint-placing").hidden = !coloring.placing;
  coloringRenderStrip();
  coloringRenderLayers();
}

// Leiste beim Bearbeiten: Ausmalbilder von hinten (links) nach vorn (rechts), Werkzeuge für das gewählte
function coloringRenderStrip() {
  const bar = paintMode.el && paintMode.el.querySelector(".paint-layers-bar");
  if (!bar) return;
  bar.hidden = !coloring.placing;
  if (!coloring.placing) return;
  const sel = coloringSelectedPage();
  const list = bar.querySelector(".paint-layer-list");
  list.replaceChildren(...coloring.pages.map((p) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "paint-layer-choice";
    b.dataset.paintAction = "c-select";
    b.dataset.coloringUid = p.uid;
    b.classList.toggle("selected", p === sel);
    b.classList.toggle("is-hidden", !!p.hidden);
    const pg = coloring.catalog.get(p.id);
    b.title = pg ? pg.name : "Ausmalbild";
    b.setAttribute("aria-label", b.title);
    b.innerHTML = pg && pg.thumb_url ? `<img src="${pg.thumb_url}" alt="">` : icon("Ausmalbild");
    return b;
  }));
  const set = (action, iconName, title, active) => {
    const btn = bar.querySelector(`[data-paint-action="${action}"]`);
    if (iconName) btn.innerHTML = icon(iconName);
    if (title) {
      btn.title = title;
      btn.setAttribute("aria-label", title);
    }
    btn.classList.toggle("active", !!active);
    btn.disabled = !sel;
  };
  set("c-hide", sel && sel.hidden ? "Verbergen" : "Anzeigen", sel && sel.hidden ? "Einblenden" : "Ausblenden");
  set("c-free", sel && sel.free ? "Pinsel" : "Ausmalbild",
    sel && sel.free ? "Frei malen – Farbe geht über die Felder" : "Farbe bleibt im Feld", false);
  ["c-back", "c-front", "c-thin", "c-thick", "c-color", "c-remove"].forEach((a) => set(a));
  const i = sel ? coloring.pages.indexOf(sel) : -1;
  bar.querySelector('[data-paint-action="c-back"]').disabled = i <= 0;
  bar.querySelector('[data-paint-action="c-front"]').disabled = i < 0 || i === coloring.pages.length - 1;
}

function coloringSerialize() {
  return coloring.pages.map(({ uid, id, v, cx, cy, size, rot, color, delta, hidden, free }) =>
    ({ uid, id, v, cx: +cx.toFixed(2), cy: +cy.toFixed(2), size: +size.toFixed(2), rot: +rot.toFixed(2), color, delta,
      ...(hidden ? { hidden: true } : {}), ...(free ? { free: true } : {}) }));
}

// ---- Platzieren ----
function coloringSelectedPage() {
  return coloring.pages.find((p) => p.uid === coloring.selected) || coloring.pages[coloring.pages.length - 1] || null;
}

// Änderung der Lage: die Farbe in diesem Ausmalbild wandert mit
function coloringMove(p, change) {
  const before = coloringMatrix(p, coloring.scale);
  change(p);
  p.size = Math.max(COLORING_MIN_SIZE, p.size);
  const after = coloringMatrix(p, coloring.scale);
  const t = after.multiply(before.inverse());
  const grow = Math.sqrt(Math.abs(t.a * t.d - t.b * t.c)) || 1;
  coloringLayer(p.uid).forEach((st) => {
    st.points.forEach((pt) => {
      const q = t.transformPoint(new DOMPoint(pt.x, pt.y));
      pt.x = q.x;
      pt.y = q.y;
    });
    st.width *= grow;
    st.bbox = paintMode.surface.computeBoundingBox(st.points);
  });
  coloring.pxCache.clear();
  if (!coloring.frame) {
    coloring.frame = requestAnimationFrame(() => {
      coloring.frame = 0;
      paintMode.surface.redrawAllStrokes();
      coloringRender();
    });
  }
}

function coloringVirtualPoint(e) {
  const r = paintMode.viewport.getBoundingClientRect();
  const s = paintMode.surface;
  return { x: (e.clientX - r.left - s.panX) / s.scale, y: (e.clientY - r.top - s.panY) / s.scale };
}

function coloringPageAt(v) {
  for (let i = coloring.pages.length - 1; i >= 0; i--) {
    const p = coloring.pages[i];
    if (p.hidden) continue;
    const q = coloringMatrix(p, coloring.scale).inverse().transformPoint(new DOMPoint(v.x, v.y));
    if (coloring.hit.isPointInPath(coloring.shapes.get(p.id).outline, q.x, q.y, "evenodd")) return p;
  }
  return null;
}

function coloringBindPlacing(overlay) {
  const toUnits = (d) => d / coloring.scale;
  // Safari meldet zwei Finger zusätzlich als eigene Geste – die soll weder die Seite noch etwas anderes zoomen
  ["gesturestart", "gesturechange", "gestureend"].forEach((type) =>
    overlay.addEventListener(type, (e) => e.preventDefault(), { passive: false }));
  overlay.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    try { overlay.setPointerCapture(e.pointerId); } catch (_) { /* Zeiger schon weg – wie im Zeichenkern */ }
    const v = coloringVirtualPoint(e);
    if (coloring.pointers.size === 0) {
      const hitPage = coloringPageAt(v);
      if (hitPage && hitPage.uid !== coloring.selected) {
        coloring.selected = hitPage.uid;
        coloringRender();
      }
    }
    coloring.pointers.set(e.pointerId, v);
  });
  overlay.addEventListener("pointermove", (e) => {
    if (!coloring.pointers.has(e.pointerId)) return;
    e.preventDefault();
    const p = coloringSelectedPage();
    const prev = new Map(coloring.pointers);
    coloring.pointers.set(e.pointerId, coloringVirtualPoint(e));
    if (!p || p.hidden) return;
    const ids = [...coloring.pointers.keys()];
    if (ids.length === 1) {
      const a0 = prev.get(ids[0]), a1 = coloring.pointers.get(ids[0]);
      coloringMove(p, (q) => { q.cx += toUnits(a1.x - a0.x); q.cy += toUnits(a1.y - a0.y); });
    } else if (ids.length >= 2) {
      // Zwei Finger: drehen und skalieren um die Mitte zwischen den Fingern, dabei mitverschieben
      const [i, j] = ids;
      const a0 = prev.get(i), b0 = prev.get(j), a1 = coloring.pointers.get(i), b1 = coloring.pointers.get(j);
      const d0 = Math.hypot(b0.x - a0.x, b0.y - a0.y), d1 = Math.hypot(b1.x - a1.x, b1.y - a1.y);
      if (d0 < 1) return;
      const ratio = d1 / d0;
      const turn = Math.atan2(b1.y - a1.y, b1.x - a1.x) - Math.atan2(b0.y - a0.y, b0.x - a0.x);
      const m0 = { x: toUnits((a0.x + b0.x) / 2), y: toUnits((a0.y + b0.y) / 2) };
      const m1 = { x: toUnits((a1.x + b1.x) / 2), y: toUnits((a1.y + b1.y) / 2) };
      coloringMove(p, (q) => {
        const dx = q.cx - m0.x, dy = q.cy - m0.y;
        const cos = Math.cos(turn) * ratio, sin = Math.sin(turn) * ratio;
        q.cx = m1.x + dx * cos - dy * sin;
        q.cy = m1.y + dx * sin + dy * cos;
        q.size *= ratio;
        q.rot += (turn * 180) / Math.PI;
      });
    }
  });
  const end = (e) => {
    coloring.pointers.delete(e.pointerId);
    if (!coloring.pointers.size) schedulePaintSave();
  };
  overlay.addEventListener("pointerup", end);
  overlay.addEventListener("pointercancel", end);
  overlay.addEventListener("wheel", (e) => {
    e.preventDefault();
    const p = coloringSelectedPage();
    if (!p || p.hidden) return;
    if (e.shiftKey) coloringMove(p, (q) => { q.rot += e.deltaY > 0 ? 5 : -5; });
    else coloringMove(p, (q) => { q.size *= e.deltaY > 0 ? 0.95 : 1.05; });
    schedulePaintSave();
  }, { passive: false });
}

// ---- Auswahl und Werkzeuge ----
async function coloringOpenChooser() {
  const sheet = paintMode.el.querySelector(".paint-coloring-sheet");
  const grid = sheet.querySelector(".paint-coloring-grid");
  grid.innerHTML = "";
  sheet.hidden = false;
  let pages = [];
  try {
    pages = await apiJson("/api/v1/coloring-pages");
  } catch (err) {
    console.warn("Ausmalbilder nicht geladen:", err);
  }
  if (!pages.length) {
    grid.innerHTML = `<p class="paint-coloring-empty">${icon("Sanduhr")}</p>`;
    return;
  }
  pages.forEach((pg) => {
    coloring.catalog.set(pg.id, pg);
    const b = document.createElement("button");
    b.type = "button";
    b.className = "paint-coloring-choice";
    b.dataset.coloringId = pg.id;
    b.title = pg.name;
    b.setAttribute("aria-label", pg.name);
    b.innerHTML = `<img src="${pg.thumb_url}" alt="">`;
    b.addEventListener("click", () => {
      sheet.hidden = true;
      coloringAdd(pg).catch((err) => console.warn("Ausmalbild nicht geladen:", err));
    });
    grid.appendChild(b);
  });
}

async function coloringAdd(pg) {
  const v = (pg.shapes_url.match(/v=(\d+)/) || [])[1] || "0";
  const s = await coloringFetchShapes(pg.id, v);
  paintMode.el.querySelector(".paint-coloring-sheet").hidden = true;
  const uh = coloringUnitsHeight();
  const size = 0.8 * Math.min(PAINT_UNITS, (uh * s.width) / s.height);
  const uid = Math.random().toString(36).slice(2, 8);
  coloring.pages.push({ uid, id: pg.id, v, cx: PAINT_UNITS / 2, cy: uh / 2, size, rot: 0,
    color: coloringDefaultLineColor(), delta: 0 });
  coloringLayer(uid);
  coloring.selected = uid;
  coloring.placing = true;
  coloring.pxCache.clear();
  coloringRender();
  schedulePaintSave();
}

function coloringAction(action, btn) {
  if (action === "coloring") return coloringOpenChooser();
  if (action === "c-select") {
    coloring.selected = btn.dataset.coloringUid;
    coloringRender();
    return;
  }
  const p = coloringSelectedPage();
  if (!p) return;
  const i = coloring.pages.indexOf(p);
  if (action === "c-place") {
    coloring.placing = !coloring.placing;
    coloring.pointers.clear();
  } else if (action === "c-hide") {
    p.hidden = !p.hidden;
  } else if (action === "c-free") {
    p.free = !p.free;
  } else if (action === "c-back" || action === "c-front") {
    const j = action === "c-back" ? i - 1 : i + 1;
    if (j < 0 || j >= coloring.pages.length) return;
    [coloring.pages[i], coloring.pages[j]] = [coloring.pages[j], coloring.pages[i]];
  } else if (action === "c-thin" || action === "c-thick") {
    const d = COLORING_LINE_DELTAS.indexOf(p.delta);
    const next = Math.max(0, Math.min(COLORING_LINE_DELTAS.length - 1, (d < 0 ? 2 : d) + (action === "c-thin" ? -1 : 1)));
    p.delta = COLORING_LINE_DELTAS[next];
  } else if (action === "c-color") {
    p.color = paintMode.color;
  } else if (action === "c-remove") {
    // Ausmalbild weg – mit der Farbe darin
    const gone = new Set(coloringLayer(p.uid));
    const s = paintMode.surface;
    s.undoStack = s.undoStack.filter((a) => !a.stroke || !gone.has(a.stroke));
    s.redoStack = s.redoStack.filter((a) => !a.stroke || !gone.has(a.stroke));
    coloring.layers.delete(p.uid);
    coloring.pages = coloring.pages.filter((q) => q !== p);
    coloring.selected = null;
    if (!coloring.pages.length) coloring.placing = false;
    coloring.pxCache.clear();
  }
  coloringRender();
  schedulePaintSave();
}
