// ==========================================================================
// Ziffern-Schreibfeld für Übungen („Ordnen“ Stufe 4 …) und Nebenrechnung (Gedankengang)
// --------------------------------------------------------------------------
// Nebenrechnung (recognize: false): Kästchen wie im Heft, nichts wird gelesen – Thea rechnet dort
// schriftlich, das Ergebnis tippt sie ein (die Erkennung war für ganze Zahlen zu unsicher, 24.10.).
// print("37,5 · 3") schreibt eine Rechnung vor, ein Zeichen pro Kästchen.
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
function createDigitPad({ beforeRead, onRead, recognize = true }) {
  if (typeof createInkSurface !== "function" || (recognize && typeof DigitInk === "undefined")) return null;
  const el = document.createElement("div");
  el.className = recognize ? "gg-write" : "gg-write gg-scratch";
  el.innerHTML = `
    <div class="gg-write-area" title="${recognize ? "Hier schreiben" : "Nebenrechnung"}"><div class="gg-write-print" aria-hidden="true"></div><canvas class="gg-write-ink"></canvas><canvas class="gg-write-overlay"></canvas></div>
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
