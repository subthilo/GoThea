// ==========================================================================
// Ziffern-Schreibfeld für Übungen (Gedankengang der Sachaufgabe, „Ordnen“ Stufe 4 …)
// --------------------------------------------------------------------------
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

// beforeRead(): Ziel der Zahl (z. B. Kästchen-ID) oder null = nichts lesen
// onRead(result, target): result = { text, chars, unsure } aus DigitInk.recognize
function createDigitPad({ beforeRead, onRead }) {
  if (typeof createInkSurface !== "function" || typeof DigitInk === "undefined") return null;
  const el = document.createElement("div");
  el.className = "gg-write";
  el.innerHTML = `
    <div class="gg-write-area" title="Hier schreiben"><canvas class="gg-write-ink"></canvas><canvas class="gg-write-overlay"></canvas></div>
    <button type="button" class="gg-key gg-write-clear" data-pad="clear" title="Neu schreiben" aria-label="Neu schreiben">${icon("Radierer")}</button>`;
  const area = el.querySelector(".gg-write-area");
  const ink = el.querySelector(".gg-write-ink"), overlay = el.querySelector(".gg-write-overlay");

  const pad = { el, surface: null, timer: null, target: null, chars: null, text: null, reading: 0 };

  pad.surface = createInkSurface({
    viewport: area, inkCanvas: ink, overlayCanvas: overlay,
    btnScrollTop: null, scrollTrack: null, scrollThumb: null,
    btnWbZoomIn: null, btnWbZoomOut: null, btnWbZoomReset: null, wbZoomLevelText: null,
    docUnderlay: null, docUnderlayImg: null, tasksLayer: null,
    inkCtx: ink.getContext("2d", { desynchronized: true }), overlayCtx: overlay.getContext("2d"),
    stopTutorSpeech: () => {},
    scheduleAutoSave: () => {  // „Strich fertig“ (oder radiert)
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
    pad.reading++;  // eine noch laufende Erkennung verwerfen
    pad.surface.strokes = [];
    pad.surface.undoStack = [];
    pad.surface.redoStack = [];
    pad.surface.redrawAllStrokes();
    pad.target = null;
    pad.chars = null;
    pad.text = null;
  };

  // In die Ansicht hängen (anstelle eines Platzhalters), Schriftfarbe wie der Text
  pad.mount = (slot, color) => {
    if (!slot) return;
    slot.replaceWith(el);
    pad.surface.currentColor = color || "#f8fafc";
    pad.surface.currentTool = "pen";
    pad.surface.resizeCanvases();
    pad.surface.redrawAllStrokes();
  };

  // Gelesene Ziffern als Muster speichern (nur aufrufen, wenn die gelesene Zahl die richtige war)
  pad.learn = (chars = pad.chars) => {
    const samples = (chars || []).filter((c) => /^[0-9]$/.test(c.label)).map((c) => DigitInk.toStored(c.label, c.strokes));
    if (!samples.length) return;
    apiJson("/api/v1/practice/handwriting", { method: "POST", json: { samples } })
      .catch((err) => console.warn("Handschrift-Muster nicht gespeichert:", err));
  };

  DigitInk.load();
  return pad;
}
