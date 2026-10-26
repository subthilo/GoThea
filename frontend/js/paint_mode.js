// ============================================================================
// Mal-Modus: Thea bemalt den Hintergrund der Seite oder eine Kachel darauf (Malen – Architektur)
// ============================================================================
// Pinsel-Knopf unten rechts (nur Thea-Modus, nur auf Seiten mit data-paint): zuerst die Fläche
// wählen – die bemalbaren Kacheln sind umrandet, antippen; oder „Hintergrund“. Dann Vollbild mit
// dem Bild in seinem festen Format (Hintergrund quadratisch, Kacheln je Art, js/paint_slots.js).
// Derselbe Zeichenkern wie die Tafel (createInkSurface, unverändert, eigenes Exemplar): der Stift
// malt, zwei Finger zoomen und verschieben.
// Geisterbild: die echte Seite bzw. der Inhalt der Kachel liegt darüber, so wie später über dem Bild
// (halb · nur Umrisse · aus · voll); Rahmen zeigen, was davon zu sehen ist (Hintergrund: quer und hoch).
// Striche werden in Rastereinheiten gespeichert (Breite = PAINT_UNITS), unabhängig von Bildschirm und
// Lage; das fertige Bild rendert der Browser und lädt es mit hoch. Speichern läuft unsichtbar nach
// jedem Strich, sichtbar nur bei Fehler.
// Plätze mit Fach (Fachseite, Fach-Kachel): „nur dieses Fach“ oder „für alle Fächer“.
// Bilder ohne Striche (z. B. von Hand eingespielt) werden nicht übermalt: dann beginnt ein neues Bild,
// das alte bleibt unter „Meine Bilder“.

const PAINT_UNITS = 1000;
const PAINT_SAVE_DELAY_MS = 1200;
const PAINT_MAX_IMAGE_PX = 2400;
const PAINT_PREVIEW_MS = 2500;
const PAINT_PREFS_KEY = "gothea.paint";
// Theas Malfarben sind fest (die Farben des Schemas kommen beim Öffnen dazu)
const PAINT_COLORS = ["#000000", "#ffffff", "#9e9e9e", "#8d6e63", "#e53935", "#d81b60", "#fb8c00", "#fdd835",
  "#7cb342", "#2e7d32", "#00acc1", "#1e88e5", "#3949ab", "#8e24aa"];
const PAINT_THEME_VARS = ["--accent", "--accent-light", "--text-primary", "--bg-card", "--bg-primary"];
// Breiten: Hintergrund in Rastereinheiten (ein Tausendstel der Bildkante); Kacheln in Bildschirmpunkten
// der echten Kachel – „fein“ muss in der kleinen Kachel noch sichtbar sein, nicht nur im Vollbild
const PAINT_WIDTHS = [
  { bg: 3, tile: 1.5, title: "Fein" },
  { bg: 8, tile: 3, title: "Mittel" },
  { bg: 18, tile: 6, title: "Dick" },
  { bg: 40, tile: 14, title: "Sehr dick" },
];
const PAINT_GHOSTS = [
  { id: "half", title: "Seite halb durchsichtig", icon: "Anzeigen" },
  { id: "outline", title: "Nur Umrisse der Seite", icon: "Übersicht" },
  { id: "off", title: "Seite und Rahmen ausgeblendet", icon: "Verbergen" },
  { id: "full", title: "Seite voll sichtbar", icon: "Anzeigen" },
];

const paintMode = {
  el: null, surface: null, viewport: null, ghostLayer: null, chooser: null,
  w: 0, h: 0, target: null, scrollY: 0,  // target.paintingId: das Bild, an dem gerade gemalt wird
  tool: "pen", color: null, widthIndex: 1, ghost: "half",
  saveTimer: null, dirty: false, pending: Promise.resolve(),
};

function loadPaintPrefs() {
  try {
    const p = JSON.parse(localStorage.getItem(PAINT_PREFS_KEY) || "{}");
    if (PAINT_WIDTHS[p.widthIndex]) paintMode.widthIndex = p.widthIndex;
    if (PAINT_GHOSTS.some((g) => g.id === p.ghost)) paintMode.ghost = p.ghost;
    if (typeof p.color === "string") paintMode.color = p.color;
  } catch (e) { /* ohne Speicher: Standard */ }
}

function savePaintPrefs() {
  try {
    localStorage.setItem(PAINT_PREFS_KEY, JSON.stringify({ widthIndex: paintMode.widthIndex, ghost: paintMode.ghost, color: paintMode.color }));
  } catch (e) { /* ohne Speicher */ }
}

// Platz, an dem gerade gemalt wird (je nach „nur dieses Fach“ / „für alle“)
function paintTargetKey(t) {
  return t.scope === "all" && t.generalKey ? t.generalKey : t.specificKey;
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
        <div class="paint-lines" aria-hidden="true"></div>
        <div class="paint-ghost" aria-hidden="true"></div>
        <div class="paint-placing" hidden></div>
      </div>
    </div>
    <div class="paint-coloring-sheet" hidden>
      <div class="paint-coloring-grid"></div>
      <button type="button" class="paint-btn" data-paint-action="c-close" title="Schließen" aria-label="Schließen">${icon("Schließen")}</button>
    </div>
    <div class="paint-bar paint-bar-tools" role="toolbar" aria-label="Werkzeuge">
      <button type="button" class="paint-btn" data-paint-tool="pen" title="Pinsel" aria-label="Pinsel">${icon("Pinsel")}</button>
      <button type="button" class="paint-btn" data-paint-tool="pixel_eraser" title="Radierer" aria-label="Radierer">${icon("Radierer")}</button>
      ${PAINT_WIDTHS.map((w, i) => `<button type="button" class="paint-btn" data-paint-width="${i}" title="${w.title}" aria-label="${w.title}"><span class="paint-dot" style="--dot:${[5, 9, 15, 26][i]}px"></span></button>`).join("")}
      <button type="button" class="paint-btn" data-paint-action="undo" title="Rückgängig" aria-label="Rückgängig">${icon("Rückgängig")}</button>
      <button type="button" class="paint-btn" data-paint-action="redo" title="Wiederholen" aria-label="Wiederholen">${icon("Wiederholen")}</button>
      <button type="button" class="paint-btn" data-paint-action="ghost" title="" aria-label=""></button>
      <button type="button" class="paint-btn" data-paint-action="scope" title="" aria-label=""></button>
      <button type="button" class="paint-btn" data-paint-action="coloring" title="Ausmalbild" aria-label="Ausmalbild">${icon("Ausmalbild")}</button>
      <button type="button" class="paint-btn" data-paint-action="c-place" data-coloring-tool hidden title="Ausmalbild verschieben, drehen, größer/kleiner" aria-label="Ausmalbild platzieren">${icon("Hand")}</button>
      <button type="button" class="paint-btn" data-paint-action="c-thin" data-coloring-tool hidden title="Linien dünner" aria-label="Linien dünner">${icon("Minus")}</button>
      <button type="button" class="paint-btn" data-paint-action="c-thick" data-coloring-tool hidden title="Linien dicker" aria-label="Linien dicker">${icon("Plus")}</button>
      <button type="button" class="paint-btn" data-paint-action="c-color" data-coloring-tool hidden title="Linien in der gewählten Farbe" aria-label="Linienfarbe">${icon("Marker")}</button>
      <button type="button" class="paint-btn" data-paint-action="c-remove" data-coloring-tool hidden title="Ausmalbild entfernen" aria-label="Ausmalbild entfernen">${icon("Papierkorb")}</button>
      <button type="button" class="paint-btn" data-paint-action="preview" title="So sieht es aus" aria-label="So sieht es aus">${icon("Bild")}</button>
      <span class="paint-save-error" hidden title="Speichern hat nicht geklappt – es wird weiter versucht">${icon("Warnung")}</span>
      <button type="button" class="paint-btn paint-btn-done" data-paint-action="done" title="Fertig" aria-label="Fertig">${icon("Haken")}</button>
    </div>`;
  document.body.appendChild(el);
  paintMode.el = el;
  paintMode.viewport = el.querySelector(".paint-viewport");
  paintMode.ghostLayer = el.querySelector(".paint-ghost");
  paintMode.linesLayer = el.querySelector(".paint-lines");
  const ink = el.querySelector(".paint-ink"), overlay = el.querySelector(".paint-overlay");

  paintMode.surface = createInkSurface({
    viewport: paintMode.viewport, inkCanvas: ink, overlayCanvas: overlay,
    btnScrollTop: null, scrollTrack: null, scrollThumb: null,
    btnWbZoomIn: null, btnWbZoomOut: null, btnWbZoomReset: null, wbZoomLevelText: null,
    // Geisterbild und Linien der Ausmalbilder folgen Zoom und Verschieben: der Kern bewegt die
    // Aufgaben-Ebene und die Unterlage mit
    docUnderlay: paintMode.linesLayer, docUnderlayImg: null, tasksLayer: paintMode.ghostLayer,
    inkCtx: ink.getContext("2d", { desynchronized: true }), overlayCtx: overlay.getContext("2d"),
    stopTutorSpeech: () => {},
    scheduleAutoSave: () => { paintMode.surface.redoStack = []; schedulePaintSave(); },
    sendCanvasUpdate: () => {},
    // Schablone: der Strich bleibt im Feld des Ausmalbilds, in dem der Stift aufsetzt (js/paint_coloring.js)
    clipForPoint: (pt) => coloringClipForPoint(pt),
    clipPath: (key) => coloringClipPath(key),
  });
  paintMode.surface.isUnderlayVisible = true;
  coloringBindPlacing(el.querySelector(".paint-placing"));

  // Das Bild bleibt im Rahmen: nicht über seine Kanten hinaus verschieben
  const clamp = () => clampPaintPan();
  ink.addEventListener("touchmove", clamp);
  ink.addEventListener("touchend", clamp);
  ink.addEventListener("wheel", clamp);

  el.addEventListener("click", onPaintClick);
  window.addEventListener("resize", () => { if (!el.hidden) layoutPaintMode(); });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (!el.hidden) closePaintMode();
    else stopPaintChoosing();
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

// ---- Größe: das Bild füllt die Bühne in seinem Format; Striche wachsen mit, wenn es sich ändert ----
function layoutPaintMode() {
  const stage = paintMode.el.querySelector(".paint-stage").getBoundingClientRect();
  const a = paintMode.target.aspect;
  const w = Math.floor(Math.min(stage.width, stage.height * a));
  const h = Math.floor(w / a);
  if (w <= 0 || h <= 0) return;
  const old = paintMode.w;
  paintMode.w = w;
  paintMode.h = h;
  paintMode.viewport.style.width = `${w}px`;
  paintMode.viewport.style.height = `${h}px`;
  coloring.scale = w / PAINT_UNITS;
  coloring.pxCache.clear();
  const s = paintMode.surface;
  if (old && old !== w) {
    const f = w / old;
    s.strokes.forEach((st) => scaleStroke(st, f));
    (s.redoStack || []).forEach((act) => act.stroke && scaleStroke(act.stroke, f));
    s.scale = 1.0;
    s.panX = 0;
    s.panY = 0;
  }
  s.resizeCanvases();
  applyPaintTool();
  buildPaintGhost();
  s.updateViewportPan();
  coloringRender();
}

function scaleStroke(stroke, f) {
  stroke.width *= f;
  stroke.points.forEach((p) => { p.x *= f; p.y *= f; });
  stroke.bbox = paintMode.surface.computeBoundingBox(stroke.points);
}

function clampPaintPan() {
  const s = paintMode.surface;
  const x = Math.max(paintMode.w - paintMode.w * s.scale, Math.min(0, s.panX));
  const y = Math.max(paintMode.h - paintMode.h * s.scale, Math.min(0, s.panY));
  if (x !== s.panX || y !== s.panY) {
    s.panX = x;
    s.panY = y;
    s.updateViewportPan();
  }
}

// ---- Geisterbild: Seite bzw. Kachelinhalt so, wie es über dem Bild liegt (Bild randlos eingepasst) ----
function buildPaintGhost() {
  const layer = paintMode.ghostLayer;
  layer.innerHTML = "";
  const t = paintMode.target, w = paintMode.w, h = paintMode.h;
  let source, sw, sh;
  if (t.kind === "background") {
    sw = window.innerWidth;
    sh = window.innerHeight;
    source = ghostOfPage(sw, sh);
  } else {
    const r = t.el.getBoundingClientRect();
    sw = r.width;
    sh = r.height;
    source = ghostOfTile(t.el, sw, sh);
  }
  // Das Bild bedeckt Bildschirm bzw. Kachel (object-fit/background-size: cover) – umgekehrt liegt
  // also Bildschirm bzw. Kachel ganz im Bild: einpassen, nicht füllen
  const k = Math.min(w / sw, h / sh), ox = (w - sw * k) / 2, oy = (h - sh * k) / 2;
  if (source) {
    source.style.transform = `translate(${ox}px, ${oy}px) scale(${k})`;
    layer.appendChild(source);
  }
  // Rahmen: was zu sehen ist – beim Hintergrund quer und hoch (aktuelle Lage kräftiger)
  const frame = (x, y, fw, fh, current) =>
    `<div class="paint-frame${current ? " current" : ""}" style="left:${x}px;top:${y}px;width:${fw}px;height:${fh}px"></div>`;
  if (t.kind === "background") {
    const part = w / (Math.max(sw, sh) / Math.min(sw, sh)), off = (w - part) / 2;
    layer.insertAdjacentHTML("beforeend", frame(0, off, w, part, sw >= sh) + frame(off, 0, part, h, sw < sh));
  } else {
    layer.insertAdjacentHTML("beforeend", frame(ox, oy, sw * k, sh * k, true));
  }
  applyPaintGhost();
}

// Kopfzeile und aktive Seite (die übrigen Tabs sind verborgen und groß), jeweils genau an ihrer
// Stelle auf dem Bildschirm (Scrollstand, klebende Kopfzeile, Staging-Banner darüber)
function ghostOfPage(sw, sh) {
  const src = document.querySelector(".app-container");
  const header = src && src.querySelector(".header");
  const main = src && src.querySelector(".content");
  const pane = main && main.querySelector(".tab-pane.active");
  if (!header || !pane) return null;
  const page = document.createElement("div");
  page.className = "paint-ghost-page";
  page.style.width = `${sw}px`;
  page.style.height = `${sh}px`;
  const clone = src.cloneNode(false), mainClone = main.cloneNode(false);
  const headerClone = ghostClone(header);
  mainClone.appendChild(ghostClone(pane));
  Object.assign(clone.style, { position: "static", margin: "0", padding: "0", maxWidth: "none", minHeight: "0" });
  [[header, headerClone], [main, mainClone]].forEach(([el, c]) => {
    const r = el.getBoundingClientRect();
    Object.assign(c.style, { position: "absolute", left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`,
      margin: "0", boxSizing: "border-box" });
  });
  clone.append(mainClone, headerClone);
  clone.setAttribute("inert", "");
  page.appendChild(clone);
  return page;
}

// Nur der Inhalt der Kachel (Icon, Text, Zahl) – ihre Fläche ist ja das Bild
function ghostOfTile(el, sw, sh) {
  const page = document.createElement("div");
  page.className = "paint-ghost-page";
  page.style.width = `${sw}px`;
  page.style.height = `${sh}px`;
  const clone = ghostClone(el);
  clone.classList.remove("has-paint");
  clone.classList.add("paint-ghost-tile");
  clone.style.width = `${sw}px`;
  clone.style.height = `${sh}px`;
  clone.style.margin = "0";
  clone.setAttribute("inert", "");
  page.appendChild(clone);
  return page;
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

// „Nur dieses Fach“ (Fach-Icon) oder „für alle Fächer“ (Schulranzen); nur bei Plätzen mit Fach
function renderPaintScope() {
  const t = paintMode.target, btn = paintMode.el.querySelector('[data-paint-action="scope"]');
  btn.hidden = !t.generalKey;
  if (!t.generalKey) return;
  const subjects = typeof cachedSubjects !== "undefined" && Array.isArray(cachedSubjects) ? cachedSubjects : [];
  const subject = subjects.find((s) => s.id === paintSubjectOfKey(t.specificKey));
  const name = subject ? subject.name : "dieses Fach";
  const all = t.scope === "all";
  btn.innerHTML = all ? icon("Schulranzen") : (subject ? subjectIcon(subject.name) : icon("Thema"));
  btn.title = all ? "Für alle Fächer" : `Nur für ${name}`;
  btn.setAttribute("aria-label", btn.title);
  btn.style.color = all || !subject ? "" : subjectColor(subject.name);
}

// ---- Werkzeug ----
function paintWidthUnits(index) {
  const t = paintMode.target, w = PAINT_WIDTHS[index];
  return t.kind === "background" ? w.bg : (w.tile * PAINT_UNITS) / t.displayW;
}

function applyPaintTool() {
  const s = paintMode.surface;
  s.currentTool = paintMode.tool;
  s.currentColor = paintMode.color;
  s.currentBaseWidth = (paintWidthUnits(paintMode.widthIndex) * paintMode.w) / PAINT_UNITS;
  paintMode.el.querySelectorAll("[data-paint-tool]").forEach((b) => b.classList.toggle("active", b.dataset.paintTool === paintMode.tool));
  paintMode.el.querySelectorAll("[data-paint-width]").forEach((b) => b.classList.toggle("active", Number(b.dataset.paintWidth) === paintMode.widthIndex));
  paintMode.el.querySelectorAll("[data-paint-color]").forEach((b) => b.classList.toggle("active", b.dataset.paintColor === paintMode.color));
  paintMode.el.style.setProperty("--paint-current", paintMode.color);
}

function onPaintClick(e) {
  const btn = e.target.closest("button");
  if (!btn || !paintMode.el.contains(btn)) return;
  const s = paintMode.surface, action = btn.dataset.paintAction;
  if (btn.dataset.paintColor) {
    paintMode.color = btn.dataset.paintColor;
    paintMode.tool = "pen";
  } else if (btn.dataset.paintTool) {
    paintMode.tool = btn.dataset.paintTool;
  } else if (btn.dataset.paintWidth !== undefined) {
    paintMode.widthIndex = Number(btn.dataset.paintWidth);
  } else if (action === "undo" || action === "redo") {
    const from = action === "undo" ? s.undoStack : s.redoStack;
    const to = action === "undo" ? s.redoStack : s.undoStack;
    const act = from.pop();
    if (!act || act.type !== "add_stroke") return;
    if (action === "undo") s.strokes = s.strokes.filter((st) => st !== act.stroke);
    else s.strokes.push(act.stroke);
    to.push(act);
    s.redrawAllStrokes();
    schedulePaintSave();
    return;
  } else if (action === "ghost") {
    const i = PAINT_GHOSTS.findIndex((g) => g.id === paintMode.ghost);
    paintMode.ghost = PAINT_GHOSTS[(i + 1) % PAINT_GHOSTS.length].id;
    applyPaintGhost();
  } else if (action === "scope") {
    setPaintScope(paintMode.target.scope === "all" ? "subject" : "all");
    return;
  } else if (action === "preview") {
    previewPaintTile();
    return;
  } else if (action === "done") {
    closePaintMode();
    return;
  } else if (action === "c-close") {
    paintMode.el.querySelector(".paint-coloring-sheet").hidden = true;
    return;
  } else if (action === "coloring" || (action && action.startsWith("c-"))) {
    coloringAction(action);
    return;
  } else {
    return;
  }
  applyPaintTool();
  savePaintPrefs();
}

// ---- Laden und Speichern ----
function parseSavedPainting(json) {
  try { return JSON.parse(json || "null"); } catch (e) { return null; }
}

function strokesFromSaved(data) {
  const list = Array.isArray(data) ? data : (data && Array.isArray(data.strokes) ? data.strokes : []);
  const f = paintMode.w / PAINT_UNITS;
  return list.filter((st) => st && Array.isArray(st.points) && st.points.length).map((st) => {
    const stroke = { tool: st.tool || "pen", color: st.color || "#000000", width: (st.width || 8) * f,
      points: st.points.map((p) => ({ x: p.x * f, y: p.y * f, pressure: p.pressure || 0.5 })) };
    if (st.clip != null) stroke.clip = st.clip;  // Feld eines Ausmalbilds
    stroke.bbox = paintMode.surface.computeBoundingBox(stroke.points);
    return stroke;
  });
}

function strokesInUnits() {
  const f = PAINT_UNITS / paintMode.w;
  const r = (v) => Math.round(v * 10) / 10;
  return paintMode.surface.strokes.map((st) => ({
    tool: st.tool, color: st.color, width: r(st.width * f), ...(st.clip != null ? { clip: st.clip } : {}),
    points: st.points.map((p) => ({ x: r(p.x * f), y: r(p.y * f), pressure: Math.round((p.pressure || 0.5) * 100) / 100 })),
  }));
}

// Auflösung: Hintergrund nach dem Bildschirm, Kachel nach ihrer echten Größe × Dichte × 2 (für Zoom).
// Arbeitet nur mit der Momentaufnahme (snap) – der Mal-Modus kann schon geschlossen sein.
function renderPaintImage(snap) {
  const t = snap.target, dpr = window.devicePixelRatio || 1;
  const base = t.kind === "background" ? Math.max(screen.width, screen.height) * dpr : t.displayW * dpr * 2;
  const pw = Math.min(PAINT_MAX_IMAGE_PX, Math.round(base));
  const canvas = document.createElement("canvas");
  canvas.width = pw;
  canvas.height = Math.round(pw / t.aspect);
  const ctx = canvas.getContext("2d");
  ctx.scale(pw / PAINT_UNITS, pw / PAINT_UNITS);
  const clips = new Map();  // jedes Feld nur einmal als Pfad bauen (viele Striche liegen im selben Feld)
  const clipFor = (key) => {
    if (!clips.has(key)) clips.set(key, coloringBuildClip(key, 1, PAINT_UNITS, PAINT_UNITS / t.aspect, snap.pages));
    return clips.get(key);
  };
  snap.strokes.forEach((st) => {
    ctx.save();
    if (st.clip != null) ctx.clip(clipFor(st.clip), "evenodd");  // im Feld des Ausmalbilds
    paintMode.surface.renderStrokeToContext(ctx, { ...st, clip: undefined });
    ctx.restore();
  });
  coloringDrawLines(ctx, snap.pages);
  // Safari kann teils kein WebP erzeugen und liefert dann PNG – der Server nimmt beides
  return new Promise((resolve) => canvas.toBlob(resolve, "image/webp", 0.85));
}

function schedulePaintSave() {
  paintMode.dirty = true;
  clearTimeout(paintMode.saveTimer);
  paintMode.saveTimer = setTimeout(flushPaintSave, PAINT_SAVE_DELAY_MS);
}

// Momentaufnahme jetzt, Speichern danach in der Kette: das dauert bei großen Bildern auf dem iPad
// Sekunden (Bild rechnen, hochladen), und der Mal-Modus kann inzwischen geschlossen oder ein anderes
// Bild offen sein
function flushPaintSave() {
  clearTimeout(paintMode.saveTimer);
  if (paintMode.dirty && paintMode.target) {
    paintMode.dirty = false;
    const snap = { target: paintMode.target, strokes: strokesInUnits(), pages: coloringSerialize(), tries: 0 };
    snap.target.lastSnap = snap;
    paintMode.pending = paintMode.pending.then(() => savePaintingNow(snap));
  }
  return paintMode.pending;
}

async function savePaintingNow(snap) {
  const { target, strokes, pages } = snap;
  if (!target.paintingId && !strokes.length && !pages.length) return;
  try {
    const form = new FormData();
    // Als Datei-Teil: Formularfelder nimmt der Server nur bis 1 MB an, ein fleißig bemaltes Bild ist größer
    const data = JSON.stringify({ v: 1, units: PAINT_UNITS, aspect: target.aspect, strokes, pages });
    form.append("strokes", new Blob([data], { type: "application/json" }), "strokes.json");
    form.append("image", await renderPaintImage(snap), "bild");
    if (target.paintingId) {
      await apiJson(`/api/v1/paintings/${target.paintingId}`, { method: "PUT", body: form });
    } else {
      form.append("kind", target.kind);
      form.append("format", target.format);
      form.append("slot_key", paintTargetKey(target));
      target.paintingId = (await apiJson("/api/v1/paintings", { method: "POST", body: form })).id;
    }
    showPaintSaveError(false);
  } catch (err) {
    console.warn("Bild nicht gespeichert:", err);
    showPaintSaveError(true);
    // Später noch einmal – mit dieser Aufnahme, solange keine neuere für dasselbe Bild unterwegs ist
    if (paintMode.target === target) schedulePaintSave();
    else if (target.lastSnap === snap && snap.tries++ < 3) {
      setTimeout(() => { paintMode.pending = paintMode.pending.then(() => savePaintingNow(snap)); }, 5000);
    }
  }
}

function showPaintSaveError(on) {
  const el = paintMode.el && paintMode.el.querySelector(".paint-save-error");
  if (el) el.hidden = !on;
}

// Für alle Fächer: das Bild hängt am gemeinsamen Platz, der Platz des Fachs wird frei (Rückfall).
// Nur dieses Fach: ab jetzt eine eigene Kopie, die das gemeinsame Bild nicht mehr ändert.
function setPaintScope(scope) {
  const t = paintMode.target;
  if (!t.generalKey || t.scope === scope) return;
  t.scope = scope;
  renderPaintScope();
  if (scope === "subject") {
    paintMode.pending = paintMode.pending.then(() => { t.paintingId = null; });
    paintMode.dirty = true;
    flushPaintSave();
    return;
  }
  paintMode.pending = paintMode.pending.then(async () => {
    try {
      if (t.paintingId) {
        await apiJson(`/api/v1/paintings/slots/${t.generalKey}`, { method: "PUT", json: { painting_id: t.paintingId } });
      }
      await apiJson(`/api/v1/paintings/slots/${t.specificKey}`, { method: "DELETE" });
    } catch (err) {
      console.warn("Bild nicht für alle Fächer übernommen:", err);
      showPaintSaveError(true);
    }
  });
}

// „So sieht es aus“: die Kachel kurz in Originalgröße an ihrem Platz, dann zurück zum Malen
async function previewPaintTile() {
  const t = paintMode.target;
  await flushPaintSave();
  paintMode.el.hidden = true;
  document.body.classList.remove("paint-mode-open");
  document.body.classList.add("paint-previewing");
  if (typeof applyPaintings === "function") await applyPaintings();
  if (t.el) t.el.scrollIntoView({ block: "center" });
  let timer = null;
  const back = (e) => {
    if (e) e.preventDefault();
    clearTimeout(timer);
    document.removeEventListener("pointerdown", back, true);
    document.body.classList.remove("paint-previewing");
    if (paintMode.target !== t) return;
    paintMode.el.hidden = false;
    document.body.classList.add("paint-mode-open");
  };
  timer = setTimeout(back, PAINT_PREVIEW_MS);
  setTimeout(() => document.addEventListener("pointerdown", back, true), 0);
}

// ---- Fläche wählen: Kacheln umrandet antippen, oder „Hintergrund“ ----
// Eigene Felder genau über den Kacheln (Safari auf dem iPad schickt Klicks auf Flächen ohne eigenen
// Klick-Handler nicht zuverlässig); eine Abdeckung darunter fängt alles andere ab (= Abbrechen).
function buildPaintChooser() {
  if (paintMode.chooser) return paintMode.chooser;
  const bar = document.createElement("div");
  bar.className = "paint-chooser";
  bar.hidden = true;
  bar.innerHTML = `
    <button type="button" class="paint-btn" data-paint-choose="background" title="Hintergrund" aria-label="Hintergrund">${icon("Bild")}</button>
    <button type="button" class="paint-btn" data-paint-choose="cancel" title="Abbrechen" aria-label="Abbrechen">${icon("Schließen")}</button>`;
  bar.addEventListener("click", (e) => {
    const choice = e.target.closest("[data-paint-choose]");
    if (!choice) return;
    stopPaintChoosing();
    if (choice.dataset.paintChoose === "background") openPaintMode(null);
  });
  document.body.appendChild(bar);
  paintMode.chooser = bar;
  return bar;
}

function startPaintChoosing() {
  const pane = typeof activePaintPane === "function" ? activePaintPane() : null;
  if (!pane || (typeof isParentActive !== "undefined" && isParentActive)) return;
  const tiles = paintTilesOf(pane);
  if (!tiles.length) {
    openPaintMode(null);
    return;
  }
  stopPaintChoosing();
  const shield = document.createElement("div");
  shield.className = "paint-pick-shield";
  shield.addEventListener("click", stopPaintChoosing);
  document.body.appendChild(shield);
  tiles.forEach((tile) => {
    const r = tile.el.getBoundingClientRect();
    const pick = document.createElement("button");
    pick.type = "button";
    pick.className = "paint-pick";
    pick.dataset.paintPick = tile.key;
    pick.title = "Diese Kachel bemalen";
    pick.setAttribute("aria-label", pick.title);
    // Seitenkoordinaten: die Felder scrollen mit der Seite
    Object.assign(pick.style, { left: `${r.left + window.scrollX}px`, top: `${r.top + window.scrollY}px`,
      width: `${r.width}px`, height: `${r.height}px` });
    pick.addEventListener("click", (e) => {
      e.preventDefault();
      stopPaintChoosing();
      openPaintMode(tile);
    });
    document.body.appendChild(pick);
  });
  buildPaintChooser().hidden = false;
  document.body.classList.add("paint-choosing");
}

function stopPaintChoosing() {
  document.body.classList.remove("paint-choosing");
  document.querySelectorAll(".paint-pick, .paint-pick-shield").forEach((el) => el.remove());
  if (paintMode.chooser) paintMode.chooser.hidden = true;
}

// ---- Öffnen und Schließen ----
// tile = { el, kind, key } aus paintTilesOf() oder null für den Hintergrund der Seite
async function openPaintMode(tile) {
  const pane = activePaintPane();
  if (!pane || (typeof isParentActive !== "undefined" && isParentActive)) return;
  buildPaintMode();
  loadPaintPrefs();
  const specificKey = tile ? tile.key : pane.dataset.paint;
  const target = tile
    ? { kind: "tile", format: tile.kind, aspect: PAINT_TILE_KINDS[tile.kind].aspect, el: tile.el,
      displayW: tile.el.getBoundingClientRect().width }
    : { kind: "background", format: "square", aspect: 1, el: null };
  Object.assign(target, { specificKey, generalKey: paintGeneralKey(specificKey), scope: "subject", paintingId: null });
  paintMode.target = target;
  paintMode.scrollY = window.scrollY;
  coloringReset();
  coloringRefreshAvailable();
  paintMode.el.querySelector(".paint-coloring-sheet").hidden = true;
  const s = paintMode.surface;
  s.strokes = [];
  s.undoStack = [];
  s.redoStack = [];
  s.scale = 1.0;
  s.panX = 0;
  s.panY = 0;
  renderPaintColors();
  paintMode.el.querySelector('[data-paint-action="preview"]').hidden = target.kind !== "tile";
  paintMode.el.hidden = false;
  document.body.classList.add("paint-mode-open");
  paintMode.w = 0;
  layoutPaintMode();
  renderPaintScope();

  // Laden läuft in derselben Kette wie Speichern und Umschalten: die warten, bis das Bild da ist
  paintMode.pending = paintMode.pending.then(() => loadPaintingFor(target));
  await paintMode.pending;
}

async function loadPaintingFor(target) {
  const s = paintMode.surface, key = target.specificKey;
  try {
    const slot = (await apiJson(`/api/v1/paintings?keys=${encodeURIComponent(key)}`)).slots[key];
    if (!slot || paintMode.target !== target) return;
    // Kommt das Bild vom gemeinsamen Platz, malt Thea zunächst „für alle“ weiter
    if (slot.slot_key === target.generalKey) target.scope = "all";
    renderPaintScope();
    const painting = await apiJson(`/api/v1/paintings/${slot.id}`);
    const data = parseSavedPainting(painting.strokes_json);
    const strokes = strokesFromSaved(data);
    const pages = data && Array.isArray(data.pages) ? data.pages : [];
    // Ohne Striche und Ausmalbilder (von Hand eingespielt): nicht übermalen, sondern neu beginnen
    if ((strokes.length || pages.length) && paintMode.target === target) {
      await coloringLoad(pages);  // Felder müssen da sein, bevor Striche darin gezeichnet werden
      if (paintMode.target !== target) return;
      target.paintingId = painting.id;
      s.strokes = strokes.concat(s.strokes);  // schon während des Ladens Gemaltes bleibt obenauf
      s.redrawAllStrokes();
      coloringRender();
    }
  } catch (err) {
    console.warn("Bild zum Weitermalen nicht geladen:", err);
  }
}

async function closePaintMode() {
  if (!paintMode.el || paintMode.el.hidden) return;
  coloring.placing = false;
  // Sofort schließen; gespeichert wird im Hintergrund weiter, danach zeigt die Seite das neue Bild
  const saved = flushPaintSave();
  paintMode.el.hidden = true;
  paintMode.target = null;
  paintMode.ghostLayer.innerHTML = "";  // der Klon trägt dieselben IDs wie die Seite
  document.body.classList.remove("paint-mode-open");
  window.scrollTo(0, paintMode.scrollY || 0);
  saved.then(() => { if (typeof applyPaintings === "function") applyPaintings(); });
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-paint");
  if (btn) btn.addEventListener("click", startPaintChoosing);
});

window.openPaintMode = openPaintMode;
window.closePaintMode = closePaintMode;
