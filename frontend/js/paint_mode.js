// ============================================================================
// Mal-Modus: Thea bemalt den Hintergrund der Seite, auf der sie gerade ist (Malen – Architektur)
// ============================================================================
// Pinsel-Knopf unten rechts (nur Thea-Modus, nur auf Seiten mit data-paint) → Vollbild mit dem
// quadratischen Bild. Derselbe Zeichenkern wie die Tafel (createInkSurface, unverändert, eigenes
// Exemplar): der Stift malt, zwei Finger zoomen und verschieben.
// Geisterbild: die echte Seite liegt darüber, so wie sie auf dem Bildschirm über dem Bild liegen wird
// (voll · halb · nur Umrisse · aus); zwei Rahmen zeigen, was quer und was hoch zu sehen ist.
// Striche werden in einem festen Raster gespeichert (PAINT_UNITS × PAINT_UNITS), unabhängig von
// Bildschirm und Lage; das fertige Bild rendert der Browser und lädt es mit hoch.
// Speichern läuft unsichtbar nach jedem Strich, sichtbar nur bei Fehler.
// Bilder ohne Striche (z. B. von Hand eingespielt) werden nicht übermalt: dann beginnt ein neues Bild,
// das alte bleibt unter „Meine Bilder“.

const PAINT_UNITS = 1000;
const PAINT_SAVE_DELAY_MS = 1200;
const PAINT_MAX_IMAGE_PX = 2400;
const PAINT_PREFS_KEY = "gothea.paint";
// Theas Malfarben sind fest (die Farben des Schemas kommen beim Öffnen dazu)
const PAINT_COLORS = ["#000000", "#ffffff", "#9e9e9e", "#8d6e63", "#e53935", "#d81b60", "#fb8c00", "#fdd835",
  "#7cb342", "#2e7d32", "#00acc1", "#1e88e5", "#3949ab", "#8e24aa"];
const PAINT_THEME_VARS = ["--accent", "--accent-light", "--text-primary", "--bg-card", "--bg-primary"];
// Breiten in Rastereinheiten (ein Tausendstel der Bildkante)
const PAINT_WIDTHS = [{ size: 3, title: "Fein" }, { size: 8, title: "Mittel" }, { size: 18, title: "Dick" },
  { size: 40, title: "Sehr dick" }];
const PAINT_GHOSTS = [
  { id: "half", title: "Seite halb durchsichtig", icon: "Anzeigen" },
  { id: "outline", title: "Nur Umrisse der Seite", icon: "Übersicht" },
  { id: "off", title: "Seite ausgeblendet", icon: "Verbergen" },
  { id: "full", title: "Seite voll sichtbar", icon: "Anzeigen" },
];

const paintMode = {
  el: null, surface: null, viewport: null, ghostLayer: null,
  side: 0, key: null, paintingId: null,
  tool: "pen", color: null, width: 8, ghost: "half",
  saveTimer: null, dirty: false, pending: Promise.resolve(),
};

function loadPaintPrefs() {
  try {
    const p = JSON.parse(localStorage.getItem(PAINT_PREFS_KEY) || "{}");
    if (PAINT_WIDTHS.some((w) => w.size === p.width)) paintMode.width = p.width;
    if (PAINT_GHOSTS.some((g) => g.id === p.ghost)) paintMode.ghost = p.ghost;
    if (typeof p.color === "string") paintMode.color = p.color;
  } catch (e) { /* ohne Speicher: Standard */ }
}

function savePaintPrefs() {
  try {
    localStorage.setItem(PAINT_PREFS_KEY, JSON.stringify({ width: paintMode.width, ghost: paintMode.ghost, color: paintMode.color }));
  } catch (e) { /* ohne Speicher */ }
}

// ---- Aufbau (einmal; der Zeichenkern hängt globale Listener an, deshalb nur ein Exemplar) ----
function buildPaintMode() {
  if (paintMode.el) return paintMode.el;
  const el = document.createElement("div");
  el.className = "paint-mode";
  el.id = "paint-mode";
  el.hidden = true;
  el.innerHTML = `
    <div class="paint-bar paint-bar-colors" role="toolbar" aria-label="Farben"></div>
    <div class="paint-stage">
      <div class="paint-viewport">
        <canvas class="paint-ink"></canvas><canvas class="paint-overlay"></canvas>
        <div class="paint-ghost" aria-hidden="true"></div>
      </div>
    </div>
    <div class="paint-bar paint-bar-tools" role="toolbar" aria-label="Werkzeuge">
      <button type="button" class="paint-btn" data-paint-tool="pen" title="Pinsel" aria-label="Pinsel">${icon("Pinsel")}</button>
      <button type="button" class="paint-btn" data-paint-tool="pixel_eraser" title="Radierer" aria-label="Radierer">${icon("Radierer")}</button>
      ${PAINT_WIDTHS.map((w) => `<button type="button" class="paint-btn" data-paint-width="${w.size}" title="${w.title}" aria-label="${w.title}"><span class="paint-dot" style="--dot:${Math.min(30, 4 + w.size * 0.6)}px"></span></button>`).join("")}
      <button type="button" class="paint-btn" data-paint-action="undo" title="Rückgängig" aria-label="Rückgängig">${icon("Rückgängig")}</button>
      <button type="button" class="paint-btn" data-paint-action="redo" title="Wiederholen" aria-label="Wiederholen">${icon("Wiederholen")}</button>
      <button type="button" class="paint-btn" data-paint-action="ghost" title="" aria-label=""></button>
      <span class="paint-save-error" hidden title="Speichern hat nicht geklappt – es wird weiter versucht">${icon("Warnung")}</span>
      <button type="button" class="paint-btn paint-btn-done" data-paint-action="done" title="Fertig" aria-label="Fertig">${icon("Haken")}</button>
    </div>`;
  document.body.appendChild(el);
  paintMode.el = el;
  paintMode.viewport = el.querySelector(".paint-viewport");
  paintMode.ghostLayer = el.querySelector(".paint-ghost");
  const ink = el.querySelector(".paint-ink"), overlay = el.querySelector(".paint-overlay");

  paintMode.surface = createInkSurface({
    viewport: paintMode.viewport, inkCanvas: ink, overlayCanvas: overlay,
    btnScrollTop: null, scrollTrack: null, scrollThumb: null,
    btnWbZoomIn: null, btnWbZoomOut: null, btnWbZoomReset: null, wbZoomLevelText: null,
    // Das Geisterbild folgt Zoom und Verschieben, weil der Kern die Aufgaben-Ebene mitbewegt
    docUnderlay: null, docUnderlayImg: null, tasksLayer: paintMode.ghostLayer,
    inkCtx: ink.getContext("2d", { desynchronized: true }), overlayCtx: overlay.getContext("2d"),
    stopTutorSpeech: () => {},
    scheduleAutoSave: () => { paintMode.surface.redoStack = []; schedulePaintSave(); },
    sendCanvasUpdate: () => {},
  });

  // Das Bild bleibt im Rahmen: nicht über seine Kanten hinaus verschieben
  const clamp = () => clampPaintPan();
  ink.addEventListener("touchmove", clamp);
  ink.addEventListener("touchend", clamp);
  ink.addEventListener("wheel", clamp);

  el.addEventListener("click", onPaintClick);
  window.addEventListener("resize", () => { if (!el.hidden) layoutPaintMode(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !el.hidden) closePaintMode();
  });
  return el;
}

function renderPaintColors() {
  const bar = paintMode.el.querySelector(".paint-bar-colors");
  const cs = getComputedStyle(document.documentElement);
  const theme = PAINT_THEME_VARS.map((v) => cs.getPropertyValue(v).trim()).filter((c) => /^#[0-9a-f]{6}$/i.test(c));
  const swatch = (c) => `<button type="button" class="paint-swatch" data-paint-color="${c}" style="--swatch:${c}" title="${c}" aria-label="Farbe ${c}"></button>`;
  bar.innerHTML = `<div class="paint-swatches paint-swatches-theme">${[...new Set(theme)].map(swatch).join("")}</div>
    <div class="paint-swatches">${PAINT_COLORS.map(swatch).join("")}</div>`;
  if (!paintMode.color) paintMode.color = theme[0] || PAINT_COLORS[4];
}

// ---- Größe: das Quadrat füllt die Bühne; Striche wachsen mit, wenn sich die Kante ändert ----
function layoutPaintMode() {
  const stage = paintMode.el.querySelector(".paint-stage").getBoundingClientRect();
  const side = Math.floor(Math.min(stage.width, stage.height));
  if (side <= 0) return;
  const old = paintMode.side;
  paintMode.side = side;
  paintMode.viewport.style.width = `${side}px`;
  paintMode.viewport.style.height = `${side}px`;
  const s = paintMode.surface;
  if (old && old !== side) {
    const f = side / old;
    s.strokes.forEach((st) => scaleStroke(st, f));
    (s.redoStack || []).forEach((a) => a.stroke && scaleStroke(a.stroke, f));
    s.scale = 1.0;
    s.panX = 0;
    s.panY = 0;
  }
  s.resizeCanvases();
  applyPaintTool();
  buildPaintGhost();
  s.updateViewportPan();
}

function scaleStroke(stroke, f) {
  stroke.width *= f;
  stroke.points.forEach((p) => { p.x *= f; p.y *= f; });
  stroke.bbox = paintMode.surface.computeBoundingBox(stroke.points);
}

function clampPaintPan() {
  const s = paintMode.surface, side = paintMode.side;
  const min = side - side * s.scale;
  const x = Math.max(min, Math.min(0, s.panX)), y = Math.max(min, Math.min(0, s.panY));
  if (x !== s.panX || y !== s.panY) {
    s.panX = x;
    s.panY = y;
    s.updateViewportPan();
  }
}

// ---- Geisterbild: die Seite so, wie sie über dem Bild liegt (Bild = Quadrat, randlos eingepasst) ----
function buildPaintGhost() {
  const layer = paintMode.ghostLayer;
  layer.innerHTML = "";
  const W = window.innerWidth, H = window.innerHeight, D = Math.max(W, H);
  const k = paintMode.side / D;
  const src = document.querySelector(".app-container");
  const header = src && src.querySelector(".header");
  const main = src && src.querySelector(".content");
  const pane = main && main.querySelector(".tab-pane.active");
  if (header && pane) {
    const page = document.createElement("div");
    page.className = "paint-ghost-page";
    page.style.width = `${W}px`;
    page.style.height = `${H}px`;
    page.style.transform = `translate(${((D - W) / 2) * k}px, ${((D - H) / 2) * k}px) scale(${k})`;
    // Nur Kopfzeile und aktive Seite (die übrigen Tabs sind verborgen und groß)
    const clone = src.cloneNode(false), mainClone = main.cloneNode(false);
    const headerClone = ghostClone(header), paneClone = ghostClone(pane);
    clone.style.marginTop = `${-paintMode.scrollY}px`;
    headerClone.style.transform = `translateY(${paintMode.scrollY}px)`;  // klebt oben wie beim Scrollen
    mainClone.appendChild(paneClone);
    clone.append(headerClone, mainClone);
    clone.setAttribute("inert", "");
    page.appendChild(clone);
    layer.appendChild(page);
  }
  // Rahmen: was quer und was hoch zu sehen ist (bei diesem Gerät), die aktuelle Lage kräftiger
  const ratio = D / Math.min(W, H), side = paintMode.side, part = side / ratio, off = (side - part) / 2;
  const landscape = W >= H;
  layer.insertAdjacentHTML("beforeend",
    `<div class="paint-frame${landscape ? " current" : ""}" style="left:0;top:${off}px;width:${side}px;height:${part}px"></div>
     <div class="paint-frame${landscape ? "" : " current"}" style="left:${off}px;top:0;width:${part}px;height:${side}px"></div>`);
  applyPaintGhost();
}

function ghostClone(src) {
  const clone = src.cloneNode(true);
  markGhostBoxes(src, clone);
  return clone;
}

// Für „nur Umrisse“: Flächen der Seite (Karten, Kacheln, Knöpfe) im Klon markieren
function markGhostBoxes(src, clone) {
  const a = [src, ...src.getElementsByTagName("*")], b = [clone, ...clone.getElementsByTagName("*")];
  for (let i = 0; i < a.length && i < b.length; i++) {
    const cs = getComputedStyle(a[i]);
    if (cs.display === "none") continue;
    const filled = cs.backgroundColor !== "rgba(0, 0, 0, 0)" && cs.backgroundColor !== "transparent";
    if (filled || parseFloat(cs.borderTopWidth) > 0 || cs.backgroundImage !== "none") b[i].classList.add("ghost-box");
  }
}

function applyPaintGhost() {
  const g = PAINT_GHOSTS.find((x) => x.id === paintMode.ghost) || PAINT_GHOSTS[0];
  paintMode.ghostLayer.dataset.ghost = g.id;
  const btn = paintMode.el.querySelector('[data-paint-action="ghost"]');
  btn.innerHTML = icon(g.icon);
  btn.title = g.title;
  btn.setAttribute("aria-label", g.title);
}

// ---- Werkzeug ----
function applyPaintTool() {
  const s = paintMode.surface;
  s.currentTool = paintMode.tool;
  s.currentColor = paintMode.color;
  s.currentBaseWidth = (paintMode.width * paintMode.side) / PAINT_UNITS;
  paintMode.el.querySelectorAll("[data-paint-tool]").forEach((b) => b.classList.toggle("active", b.dataset.paintTool === paintMode.tool));
  paintMode.el.querySelectorAll("[data-paint-width]").forEach((b) => b.classList.toggle("active", Number(b.dataset.paintWidth) === paintMode.width));
  paintMode.el.querySelectorAll("[data-paint-color]").forEach((b) => b.classList.toggle("active", b.dataset.paintColor === paintMode.color));
  paintMode.el.style.setProperty("--paint-current", paintMode.color);
}

function onPaintClick(e) {
  const btn = e.target.closest("button");
  if (!btn || !paintMode.el.contains(btn)) return;
  const s = paintMode.surface;
  if (btn.dataset.paintColor) {
    paintMode.color = btn.dataset.paintColor;
    paintMode.tool = "pen";
  } else if (btn.dataset.paintTool) {
    paintMode.tool = btn.dataset.paintTool;
  } else if (btn.dataset.paintWidth) {
    paintMode.width = Number(btn.dataset.paintWidth);
  } else if (btn.dataset.paintAction === "undo" || btn.dataset.paintAction === "redo") {
    const from = btn.dataset.paintAction === "undo" ? s.undoStack : s.redoStack;
    const to = btn.dataset.paintAction === "undo" ? s.redoStack : s.undoStack;
    const action = from.pop();
    if (!action || action.type !== "add_stroke") return;
    if (from === s.undoStack) s.strokes = s.strokes.filter((st) => st !== action.stroke);
    else s.strokes.push(action.stroke);
    to.push(action);
    s.redrawAllStrokes();
    schedulePaintSave();
    return;
  } else if (btn.dataset.paintAction === "ghost") {
    const i = PAINT_GHOSTS.findIndex((g) => g.id === paintMode.ghost);
    paintMode.ghost = PAINT_GHOSTS[(i + 1) % PAINT_GHOSTS.length].id;
    applyPaintGhost();
  } else if (btn.dataset.paintAction === "done") {
    closePaintMode();
    return;
  } else {
    return;
  }
  applyPaintTool();
  savePaintPrefs();
}

// ---- Laden und Speichern ----
function strokesFromSaved(json) {
  let data = null;
  try { data = JSON.parse(json || "null"); } catch (e) { return []; }
  const list = Array.isArray(data) ? data : (data && Array.isArray(data.strokes) ? data.strokes : []);
  const f = paintMode.side / PAINT_UNITS;
  return list.filter((st) => st && Array.isArray(st.points) && st.points.length).map((st) => {
    const stroke = { tool: st.tool || "pen", color: st.color || "#000000", width: (st.width || 8) * f,
      points: st.points.map((p) => ({ x: p.x * f, y: p.y * f, pressure: p.pressure || 0.5 })) };
    stroke.bbox = paintMode.surface.computeBoundingBox(stroke.points);
    return stroke;
  });
}

function strokesInUnits() {
  const f = PAINT_UNITS / paintMode.side;
  const r = (v) => Math.round(v * 10) / 10;
  return paintMode.surface.strokes.map((st) => ({
    tool: st.tool, color: st.color, width: r(st.width * f),
    points: st.points.map((p) => ({ x: r(p.x * f), y: r(p.y * f), pressure: Math.round((p.pressure || 0.5) * 100) / 100 })),
  }));
}

function renderPaintImage(strokes) {
  const px = Math.min(PAINT_MAX_IMAGE_PX, Math.round(Math.max(screen.width, screen.height) * (window.devicePixelRatio || 1)));
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = px;
  const ctx = canvas.getContext("2d");
  ctx.scale(px / PAINT_UNITS, px / PAINT_UNITS);
  strokes.forEach((st) => paintMode.surface.renderStrokeToContext(ctx, st));
  // Safari kann teils kein WebP erzeugen und liefert dann PNG – der Server nimmt beides
  return new Promise((resolve) => canvas.toBlob(resolve, "image/webp", 0.85));
}

function schedulePaintSave() {
  paintMode.dirty = true;
  clearTimeout(paintMode.saveTimer);
  paintMode.saveTimer = setTimeout(flushPaintSave, PAINT_SAVE_DELAY_MS);
}

function flushPaintSave() {
  clearTimeout(paintMode.saveTimer);
  if (paintMode.dirty) {
    paintMode.dirty = false;
    paintMode.pending = paintMode.pending.then(savePaintingNow);
  }
  return paintMode.pending;
}

async function savePaintingNow() {
  const key = paintMode.key;
  const strokes = strokesInUnits();
  if (!paintMode.paintingId && !strokes.length) return;
  try {
    const form = new FormData();
    form.append("strokes_json", JSON.stringify({ v: 1, units: PAINT_UNITS, strokes }));
    form.append("image", await renderPaintImage(strokes), "bild");
    if (paintMode.paintingId) {
      await apiJson(`/api/v1/paintings/${paintMode.paintingId}`, { method: "PUT", body: form });
    } else {
      form.append("kind", "background");
      form.append("format", "square");
      form.append("slot_key", key);
      paintMode.paintingId = (await apiJson("/api/v1/paintings", { method: "POST", body: form })).id;
    }
    showPaintSaveError(false);
  } catch (err) {
    console.warn("Bild nicht gespeichert:", err);
    showPaintSaveError(true);
    if (paintMode.key === key) schedulePaintSave();  // später noch einmal
  }
}

function showPaintSaveError(on) {
  const el = paintMode.el && paintMode.el.querySelector(".paint-save-error");
  if (el) el.hidden = !on;
}

// ---- Öffnen und Schließen ----
async function openPaintMode() {
  const key = typeof activePaintKey === "function" ? activePaintKey() : null;
  if (!key || (typeof isParentActive !== "undefined" && isParentActive)) return;
  buildPaintMode();
  loadPaintPrefs();
  paintMode.key = key;
  paintMode.paintingId = null;
  paintMode.scrollY = window.scrollY;
  const s = paintMode.surface;
  s.strokes = [];
  s.undoStack = [];
  s.redoStack = [];
  s.scale = 1.0;
  s.panX = 0;
  s.panY = 0;
  renderPaintColors();
  paintMode.el.hidden = false;
  document.body.classList.add("paint-mode-open");
  paintMode.side = 0;
  layoutPaintMode();

  try {
    const slot = (await apiJson(`/api/v1/paintings?keys=${encodeURIComponent(key)}`)).slots[key];
    if (slot && paintMode.key === key) {
      const painting = await apiJson(`/api/v1/paintings/${slot.id}`);
      const strokes = strokesFromSaved(painting.strokes_json);
      // Ohne Striche (von Hand eingespielt): nicht übermalen, sondern neu beginnen
      if (strokes.length && paintMode.key === key) {
        paintMode.paintingId = painting.id;
        s.strokes = strokes;
        s.redrawAllStrokes();
      }
    }
  } catch (err) {
    console.warn("Bild zum Weitermalen nicht geladen:", err);
  }
}

async function closePaintMode() {
  if (!paintMode.el || paintMode.el.hidden) return;
  await flushPaintSave();
  paintMode.el.hidden = true;
  paintMode.key = null;
  paintMode.ghostLayer.innerHTML = "";  // der Klon trägt dieselben IDs wie die Seite
  document.body.classList.remove("paint-mode-open");
  window.scrollTo(0, paintMode.scrollY || 0);
  if (typeof applyPaintings === "function") applyPaintings();
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-paint");
  if (btn) btn.addEventListener("click", openPaintMode);
});

window.openPaintMode = openPaintMode;
window.closePaintMode = closePaintMode;
