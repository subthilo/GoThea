// ============================================================================
// Ausmalbilder im Mal-Modus (Konzept-Doc, Tab „Ausmalbilder“)
// ============================================================================
// Thea wählt ein freigegebenes Ausmalbild, legt es vor den Hintergrund oder auf die Kachel, verschiebt,
// dreht und skaliert es (ein Finger/Stift verschiebt, zwei Finger drehen und skalieren; Mac: Mausrad,
// mit Umschalttaste drehen) und malt dann in den Feldern: der Zeichenkern fragt beim Aufsetzen über die
// Schablone (clipForPoint/clipPath), in welchem Feld der Stift liegt, und hält den Strich darin.
// Außerhalb aller Ausmalbilder ist es der Hintergrund („bg“). Die Linien liegen als eigene Ebene über
// der Farbe (zoomt mit, docUnderlay des Kerns); Farbe und Stärke wählt Thea je Ausmalbild.
//
// Platzierung in Rastereinheiten des Bildes (wie die Striche): Mitte cx/cy, Breite size, Drehung rot (Grad).
// Schlüssel eines Feldes: "<uid>:<Feld-ID>"; "<uid>:x" = auf der Linie (malt nichts); "bg" = Hintergrund.
// Verschiebt Thea ein Ausmalbild später, wandert ihre Farbe darin mit.

const COLORING_LINE_DELTAS = [-1.2, -0.6, 0, 1, 2.5, 5];  // dünner/dicker, Einheiten des Ausmalbilds
const COLORING_LINE_FALLBACK = "#111111";

// Startfarbe der Linien: die Schriftfarbe des Schemas – hell auf dunklen, dunkel auf hellen Schemen
// (schwarze Linien verschwänden auf dunklem Grund)
function coloringDefaultLineColor() {
  const c = getComputedStyle(document.documentElement).getPropertyValue("--text-primary").trim();
  return /^#[0-9a-f]{6}$/i.test(c) ? c : COLORING_LINE_FALLBACK;
}
const COLORING_MIN_SIZE = 60;   // kleinste Breite in Rastereinheiten

const coloring = {
  pages: [],           // { uid, id, v, cx, cy, size, rot, color, delta }
  shapes: new Map(),   // id → { width, height, bleed, ink, outline, fields: [{ id, path, box }] }
  pxCache: new Map(),  // Schlüssel → Path2D in Punkten der Malfläche
  selected: null,
  placing: false,
  scale: 1,            // Punkte der Malfläche je Rastereinheit
  hit: document.createElement("canvas").getContext("2d"),
  pointers: new Map(),
  frame: 0,
};

function coloringReset() {
  coloring.pages = [];
  coloring.selected = null;
  coloring.placing = false;
  coloring.pxCache.clear();
  coloring.pointers.clear();
}

function coloringUnitsHeight() {
  return PAINT_UNITS / (paintMode.target ? paintMode.target.aspect : 1);
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

async function coloringLoad(pages) {
  coloringReset();
  const list = Array.isArray(pages) ? pages : [];
  await Promise.all(list.map((p) => coloringFetchShapes(p.id, p.v).catch((err) => console.warn("Ausmalbild fehlt:", err))));
  coloring.pages = list.filter((p) => coloring.shapes.has(p.id)).map((p) => ({ ...p }));
}

// ---- Geometrie ----
// Ausmalbild (eigenes 1000er-Raster) → Ziel (k = Punkte je Rastereinheit des Bildes; 1 = Rastereinheiten)
function coloringMatrix(p, k) {
  const s = coloring.shapes.get(p.id);
  return new DOMMatrix().scaleSelf(k, k).translateSelf(p.cx, p.cy).rotateSelf(p.rot)
    .scaleSelf(p.size / s.width, p.size / s.width).translateSelf(-s.width / 2, -s.height / 2);
}

function coloringBuildClip(key, k, w, h) {
  const path = new Path2D();
  if (key === "bg") {
    path.rect(0, 0, w, h);
    coloring.pages.forEach((p) => path.addPath(coloring.shapes.get(p.id).outline, coloringMatrix(p, k)));
    return path;
  }
  const [uid, fid] = String(key).split(":");
  const page = coloring.pages.find((p) => p.uid === uid);
  if (!page || fid === "x") return path;  // leer: malt nichts
  const field = coloring.shapes.get(page.id).fields.find((f) => String(f.id) === fid);
  if (field) path.addPath(field.path, coloringMatrix(page, k));
  return path;
}

// Schablone für den Zeichenkern: Feld unter dem Stift (Punkte der Malfläche)
function coloringClipForPoint(pt) {
  if (!coloring.pages.length || coloring.placing) return null;
  for (let i = coloring.pages.length - 1; i >= 0; i--) {
    const p = coloring.pages[i];
    const s = coloring.shapes.get(p.id);
    const q = coloringMatrix(p, coloring.scale).inverse().transformPoint(new DOMPoint(pt.x, pt.y));
    if (!coloring.hit.isPointInPath(s.outline, q.x, q.y, "evenodd")) continue;
    for (const f of s.fields) {
      const b = f.box;
      if (q.x < b[0] || q.x > b[2] || q.y < b[1] || q.y > b[3]) continue;
      if (coloring.hit.isPointInPath(f.path, q.x, q.y, "evenodd")) return `${p.uid}:${f.id}`;
    }
    return `${p.uid}:x`;
  }
  return "bg";
}

function coloringClipPath(key) {
  if (!coloring.pages.length) return null;
  let path = coloring.pxCache.get(key);
  if (!path) {
    path = coloringBuildClip(key, coloring.scale, paintMode.w, paintMode.h);
    coloring.pxCache.set(key, path);
  }
  return path;
}

// ---- Linien ----
function coloringLineSvg(p, s, k, selected) {
  const m = coloringMatrix(p, k);
  const ns = "http://www.w3.org/2000/svg";
  const g = document.createElementNS(ns, "g");
  g.setAttribute("transform", `matrix(${m.a} ${m.b} ${m.c} ${m.d} ${m.e} ${m.f})`);
  const ink = document.createElementNS(ns, "path");
  ink.setAttribute("d", s.inkD);
  ink.setAttribute("fill", p.color);
  ink.setAttribute("fill-rule", "evenodd");
  const delta = Math.max(p.delta || 0, -s.bleed * 0.9);
  if (delta > 0) {
    ink.setAttribute("stroke", p.color);
    ink.setAttribute("stroke-width", String(delta * 2));
    ink.setAttribute("stroke-linejoin", "round");
  } else if (delta < 0) {
    // Dünner: die Linienfläche um |delta| schrumpfen (Maske: Fläche minus breiter Rand)
    const mask = document.createElementNS(ns, "mask");
    mask.id = `cm-${p.uid}`;
    mask.setAttribute("maskUnits", "userSpaceOnUse");
    mask.innerHTML = `<rect x="-10" y="-10" width="${s.width + 20}" height="${s.height + 20}" fill="black"/>`;
    const inside = ink.cloneNode();
    inside.setAttribute("fill", "white");
    const edge = ink.cloneNode();
    edge.setAttribute("fill", "none");
    edge.setAttribute("stroke", "black");
    edge.setAttribute("stroke-width", String(-delta * 2));
    mask.append(inside, edge);
    g.appendChild(mask);
    ink.setAttribute("mask", `url(#cm-${p.uid})`);
  }
  g.appendChild(ink);
  if (selected) {
    const frame = document.createElementNS(ns, "rect");
    frame.setAttribute("x", "0");
    frame.setAttribute("y", "0");
    frame.setAttribute("width", s.width);
    frame.setAttribute("height", s.height);
    frame.setAttribute("class", "paint-coloring-frame");
    frame.setAttribute("vector-effect", "non-scaling-stroke");
    g.appendChild(frame);
  }
  return g;
}

function coloringRender() {
  const layer = paintMode.linesLayer;
  if (!layer) return;
  const w = paintMode.w, h = paintMode.h;
  layer.style.width = `${w}px`;
  layer.style.height = `${h}px`;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("width", w);
  svg.setAttribute("height", h);
  coloring.pages.forEach((p) => {
    const s = coloring.shapes.get(p.id);
    if (s) svg.appendChild(coloringLineSvg(p, s, coloring.scale, coloring.placing && p.uid === coloring.selected));
  });
  layer.replaceChildren(svg);
  const tools = paintMode.el.querySelectorAll("[data-coloring-tool]");
  tools.forEach((b) => { b.hidden = !coloring.pages.length; });
  const place = paintMode.el.querySelector('[data-paint-action="c-place"]');
  if (place) place.classList.toggle("active", coloring.placing);
  paintMode.el.querySelector(".paint-placing").hidden = !coloring.placing;
}

// Fürs fertige Bild: ctx steht auf Rastereinheiten des Bildes
function coloringDrawLines(ctx) {
  coloring.pages.forEach((p) => {
    const s = coloring.shapes.get(p.id);
    if (!s) return;
    const delta = Math.max(p.delta || 0, -s.bleed * 0.9);
    const draw = (c) => {
      c.save();
      const m = coloringMatrix(p, 1);
      c.transform(m.a, m.b, m.c, m.d, m.e, m.f);
      c.fillStyle = p.color;
      c.fill(s.ink, "evenodd");
      if (delta) {
        c.lineJoin = "round";
        c.lineWidth = Math.abs(delta) * 2;
        c.strokeStyle = p.color;
        if (delta < 0) c.globalCompositeOperation = "destination-out";
        c.stroke(s.ink);
      }
      c.restore();
    };
    if (delta >= 0) return draw(ctx);
    // Dünner: auf eigener Ebene schrumpfen, dann übernehmen (sonst radierte der Rand die Farbe darunter)
    const tmp = document.createElement("canvas");
    tmp.width = ctx.canvas.width;
    tmp.height = ctx.canvas.height;
    const t = tmp.getContext("2d");
    t.setTransform(ctx.getTransform());
    draw(t);
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(tmp, 0, 0);
    ctx.restore();
  });
}

function coloringClipUnits(key) {
  return coloringBuildClip(key, 1, PAINT_UNITS, coloringUnitsHeight());
}

function coloringSerialize() {
  return coloring.pages.map(({ uid, id, v, cx, cy, size, rot, color, delta }) =>
    ({ uid, id, v, cx: +cx.toFixed(2), cy: +cy.toFixed(2), size: +size.toFixed(2), rot: +rot.toFixed(2), color, delta }));
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
  const prefix = `${p.uid}:`;
  paintMode.surface.strokes.forEach((st) => {
    if (typeof st.clip !== "string" || !st.clip.startsWith(prefix)) return;
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
    const q = coloringMatrix(p, coloring.scale).inverse().transformPoint(new DOMPoint(v.x, v.y));
    if (coloring.hit.isPointInPath(coloring.shapes.get(p.id).outline, q.x, q.y, "evenodd")) return p;
  }
  return null;
}

function coloringBindPlacing(overlay) {
  const toUnits = (d) => d / coloring.scale;
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
    if (!p) return;
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
    if (!p) return;
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
  coloring.selected = uid;
  coloring.placing = true;
  coloring.pxCache.clear();
  coloringRender();
  paintMode.surface.redrawAllStrokes();
  schedulePaintSave();
}

function coloringAction(action) {
  const p = coloringSelectedPage();
  if (action === "coloring") return coloringOpenChooser();
  if (!p) return;
  if (action === "c-place") {
    coloring.placing = !coloring.placing;
    coloring.pointers.clear();
  } else if (action === "c-thin" || action === "c-thick") {
    const i = COLORING_LINE_DELTAS.indexOf(p.delta);
    const next = Math.max(0, Math.min(COLORING_LINE_DELTAS.length - 1, (i < 0 ? 2 : i) + (action === "c-thin" ? -1 : 1)));
    p.delta = COLORING_LINE_DELTAS[next];
  } else if (action === "c-color") {
    p.color = paintMode.color;
  } else if (action === "c-remove") {
    // Ausmalbild weg – mit der Farbe darin
    const prefix = `${p.uid}:`;
    const keep = (st) => !(typeof st.clip === "string" && st.clip.startsWith(prefix));
    const s = paintMode.surface;
    s.strokes = s.strokes.filter(keep);
    s.undoStack = s.undoStack.filter((a) => !a.stroke || keep(a.stroke));
    s.redoStack = s.redoStack.filter((a) => !a.stroke || keep(a.stroke));
    coloring.pages = coloring.pages.filter((q) => q !== p);
    coloring.selected = null;
    coloring.placing = false;
    coloring.pxCache.clear();
    s.redrawAllStrokes();
  }
  coloringRender();
  schedulePaintSave();
}
