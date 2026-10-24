// ==========================================================================
// Ziffern-Schreibfeld für Übungen („Ordnen“ Stufe 4 …) und Nebenrechnung (Gedankengang)
// --------------------------------------------------------------------------
// Nebenrechnung (recognize: false): Kästchen wie im Heft, nichts wird gelesen – Thea rechnet dort
// schriftlich, das Ergebnis tippt sie ein (die Erkennung war für ganze Zahlen zu unsicher, 24.10.).
// print("37,5 · 3") schreibt eine Rechnung vor, ein Zeichen pro Kästchen. Daneben Stift, Radierer,
// drei Strichbreiten (die gewählte merkt sich das Gerät) und „Alles löschen“ (data-pad="clear").
// Derselbe Zeichenkern wie die Tafel (createInkSurface, unverändert; kein Stocken wie
// bei Scribble), die Ziffern erkennt ein kleines Netz im Browser (js/digit_ink.js).
// Nach einer kurzen Schreibpause wird gelesen; die Ansicht entscheidet, wohin die
// Zahl gehört (beforeRead → Ziel, onRead → eintragen, veraltete Ergebnisse fallen weg).
// Bestätigte Ziffern (richtige Antwort, gelesene Zahl unverändert) speichert learn()
// mit ihren Strichen – zum Messen und späteren Nachtrainieren auf Theas Schrift.
// Ein Exemplar pro Ansicht, das bei jedem Zeichnen nur umgehängt wird (mount). Den Radierer-Knopf
// (data-pad="clear") behandelt die Ansicht: pad.clear() und ggf. das Ziel leeren.
// ==========================================================================

const DIGIT_PAD_PAUSE_MS = 450;
const SCRATCH_WIDTHS = [{ size: 2, title: "Fein" }, { size: 4, title: "Normal" }, { size: 7, title: "Kräftig" }];
const SCRATCH_WIDTH_KEY = "gothea.scratchWidth";

function scratchToolsHtml() {
  return `<div class="gg-scratch-tools" role="toolbar" aria-label="Stift">
    <button type="button" class="gg-key gg-tool" data-pad-tool="pen" title="Stift" aria-label="Stift">${icon("Pencil")}</button>
    <button type="button" class="gg-key gg-tool" data-pad-tool="pixel_eraser" title="Radierer" aria-label="Radierer">${icon("Radierer")}</button>
    ${SCRATCH_WIDTHS.map((w) => `<button type="button" class="gg-key gg-tool" data-pad-size="${w.size}" title="${w.title}" aria-label="${w.title}"><span class="gg-dot" style="--dot:${w.size + 3}px"></span></button>`).join("")}
    <button type="button" class="gg-key gg-tool" data-pad="clear" title="Alles löschen" aria-label="Alles löschen">${icon("Papierkorb")}</button>
  </div>`;
}

// beforeRead(): Ziel der Zahl (z. B. Kästchen-ID) oder null = nichts lesen
// onRead(result, target): result = { text, chars, unsure } aus DigitInk.recognize
function createDigitPad({ beforeRead, onRead, recognize = true }) {
  if (typeof createInkSurface !== "function" || (recognize && typeof DigitInk === "undefined")) return null;
  const el = document.createElement("div");
  el.className = recognize ? "gg-write" : "gg-write gg-scratch";
  el.innerHTML = `
    <div class="gg-write-area" title="${recognize ? "Hier schreiben" : "Nebenrechnung"}"><div class="gg-write-print" aria-hidden="true"></div><canvas class="gg-write-ink"></canvas><canvas class="gg-write-overlay"></canvas></div>
    ${recognize ? `<button type="button" class="gg-key gg-write-clear" data-pad="clear" title="Neu schreiben" aria-label="Neu schreiben">${icon("Radierer")}</button>` : scratchToolsHtml()}`;
  const area = el.querySelector(".gg-write-area");
  const ink = el.querySelector(".gg-write-ink"), overlay = el.querySelector(".gg-write-overlay");

  const pad = { el, surface: null, timer: null, target: null, chars: null, text: null, reading: 0, tool: "pen", width: 4 };
  if (!recognize) {
    try { pad.width = Number(localStorage.getItem(SCRATCH_WIDTH_KEY)) || pad.width; } catch (e) { /* ohne Speicher: Normal */ }
  }

  pad.surface = createInkSurface({
    viewport: area, inkCanvas: ink, overlayCanvas: overlay,
    btnScrollTop: null, scrollTrack: null, scrollThumb: null,
    btnWbZoomIn: null, btnWbZoomOut: null, btnWbZoomReset: null, wbZoomLevelText: null,
    docUnderlay: null, docUnderlayImg: null, tasksLayer: null,
    inkCtx: ink.getContext("2d", { desynchronized: true }), overlayCtx: overlay.getContext("2d"),
    stopTutorSpeech: () => {},
    scheduleAutoSave: () => {  // „Strich fertig“ (oder radiert)
      if (!recognize) return;
      clearTimeout(pad.timer);
      pad.timer = setTimeout(read, DIGIT_PAD_PAUSE_MS);
    },
    sendCanvasUpdate: () => {},
  });

  async function read() {
    const target = beforeRead();
    const strokes = pad.surface.strokes.filter((st) => st.tool === "pen" && st.points && st.points.length);
    if (target === null || target === undefined || !strokes.length) return;
    const reading = ++pad.reading;
    const result = await DigitInk.recognize(strokes);
    if (reading !== pad.reading) return;  // inzwischen neu geschrieben oder geleert
    pad.target = target;
    pad.chars = result.chars;
    pad.text = result.text;
    onRead(result, target);
  }

  pad.clear = () => {
    clearTimeout(pad.timer);
    pad.tool = "pen";
    applyTool();
    pad.reading++;  // eine noch laufende Erkennung verwerfen
    pad.surface.strokes = [];
    pad.surface.undoStack = [];
    pad.surface.redoStack = [];
    pad.surface.redrawAllStrokes();
    pad.target = null;
    pad.chars = null;
    pad.text = null;
  };

  // Werkzeug und Strichbreite der Nebenrechnung (Knöpfe neben dem Feld)
  function applyTool() {
    pad.surface.currentTool = pad.tool;
    pad.surface.currentBaseWidth = pad.width;
    el.querySelectorAll("[data-pad-tool]").forEach((b) => b.classList.toggle("active", b.dataset.padTool === pad.tool));
    el.querySelectorAll("[data-pad-size]").forEach((b) => b.classList.toggle("active", Number(b.dataset.padSize) === pad.width));
  }

  el.addEventListener("click", (e) => {
    const b = e.target.closest("[data-pad-tool], [data-pad-size]");
    if (!b) return;
    e.stopPropagation();
    if (b.dataset.padTool) pad.tool = b.dataset.padTool;
    if (b.dataset.padSize) {
      pad.width = Number(b.dataset.padSize);
      pad.tool = "pen";  // Breite wählen heißt weiterschreiben
      try { localStorage.setItem(SCRATCH_WIDTH_KEY, String(pad.width)); } catch (err) { /* nur für diese Sitzung */ }
    }
    applyTool();
  });

  // In die Ansicht hängen (anstelle eines Platzhalters), Schriftfarbe wie der Text
  pad.mount = (slot, color) => {
    if (!slot) return;
    slot.replaceWith(el);
    pad.surface.currentColor = color || "#f8fafc";
    applyTool();
    pad.surface.resizeCanvases();
    pad.surface.redrawAllStrokes();
  };

  // Vorgeschriebene Rechnung (oder "" = keine); jedes Zeichen in einem Kästchen
  pad.print = (text) => {
    el.querySelector(".gg-write-print").innerHTML = [...(text || "")]
      .map((ch) => `<span>${ch === " " ? "" : escapeHtml(ch)}</span>`).join("");
  };

  // Gelesene Ziffern als Muster speichern (nur aufrufen, wenn die gelesene Zahl die richtige war)
  pad.learn = (chars = pad.chars) => {
    const samples = (chars || []).filter((c) => /^[0-9]$/.test(c.label)).map((c) => DigitInk.toStored(c.label, c.strokes));
    if (!samples.length) return;
    apiJson("/api/v1/practice/handwriting", { method: "POST", json: { samples } })
      .catch((err) => console.warn("Handschrift-Muster nicht gespeichert:", err));
  };

  if (recognize) DigitInk.load();
  return pad;
}
