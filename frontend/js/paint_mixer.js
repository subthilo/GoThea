// ============================================================================
// Farbmischer im Mal-Modus: zwei Töpfe mischen wie Tusche, dazu heller/dunkler und der Farbkreis
// ============================================================================
// Paletten-Knopf am Ende der Farbleiste öffnet den Mischer über dem Bild. Ein Topf ist gewählt;
// ein Farbtupfer aus der Leiste füllt ihn (danach ist der andere Topf dran), der Farbkreis des
// Geräts ebenso. Haken: die Mischung kommt vorn in „eigene Farben“ (Server, /api/v1/design,
// höchstens 8, die älteste fällt heraus) und wird die Pinselfarbe.
// Gemischt wird wie mit Farbe, nicht wie mit Licht: gewichtetes geometrisches Mittel der
// Lichtanteile je Kanal – Blau + Gelb ergibt Grün statt Grau.

const PAINT_MIXER_LIGHT = 0.9;  // ganz hell/dunkel: so weit Richtung Weiß bzw. Schwarz

const paintMixer = { own: [], pots: ["#1e88e5", "#fdd835"], active: 1, ratio: 0.5, light: 0 };

function mixerLinear(c) {
  c /= 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function mixerByte(v) {
  v = v <= 0.0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - 0.055;
  return Math.round(Math.min(1, Math.max(0, v)) * 255);
}

function mixerRgb(hex) {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
}

function mixerHex(rgb) {
  return "#" + rgb.map((v) => v.toString(16).padStart(2, "0")).join("");
}

function mixPaints(a, b, t) {
  const A = mixerRgb(a).map(mixerLinear), B = mixerRgb(b).map(mixerLinear);
  const log = (x) => Math.log(Math.max(x, 0.002));
  return mixerHex(A.map((x, i) => mixerByte(Math.exp((1 - t) * log(x) + t * log(B[i])))));
}

function shadePaint(hex, light) {
  const to = light > 0 ? 255 : 0, t = Math.abs(light) * PAINT_MIXER_LIGHT;
  return mixerHex(mixerRgb(hex).map((v) => Math.round(v + (to - v) * t)));
}

function mixerResult(ratio = paintMixer.ratio, light = paintMixer.light) {
  return shadePaint(mixPaints(paintMixer.pots[0], paintMixer.pots[1], ratio), light);
}

function mixerGradient(fn) {
  return `linear-gradient(to right, ${[0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1].map(fn).join(", ")})`;
}

function paintMixerHtml() {
  return `
    <div class="paint-mixer" hidden>
      <div class="paint-mixer-row">
        <button type="button" class="paint-mixer-pot" data-paint-action="m-pot" data-pot="0" title="Farbe 1" aria-label="Farbe 1"></button>
        <input type="range" class="paint-mixer-slider paint-mixer-ratio" min="0" max="100" aria-label="Mischen">
        <button type="button" class="paint-mixer-pot" data-paint-action="m-pot" data-pot="1" title="Farbe 2" aria-label="Farbe 2"></button>
      </div>
      <div class="paint-mixer-result"></div>
      <input type="range" class="paint-mixer-slider paint-mixer-light" min="-100" max="100" aria-label="Heller oder dunkler">
      <div class="paint-mixer-actions">
        <label class="paint-btn paint-mixer-wheel" title="Farbkreis">${icon("Farbkreis")}<input type="color" aria-label="Farbkreis"></label>
        <button type="button" class="paint-btn" data-paint-action="m-close" title="Schließen" aria-label="Schließen">${icon("Schließen")}</button>
        <button type="button" class="paint-btn paint-btn-done" data-paint-action="m-take" title="Diese Farbe nehmen" aria-label="Diese Farbe nehmen">${icon("Haken")}</button>
      </div>
    </div>`;
}

function bindPaintMixer(root) {
  const el = root.querySelector(".paint-mixer");
  el.querySelector(".paint-mixer-ratio").addEventListener("input", (e) => {
    paintMixer.ratio = Number(e.target.value) / 100;
    renderPaintMixer();
  });
  el.querySelector(".paint-mixer-light").addEventListener("input", (e) => {
    paintMixer.light = Number(e.target.value) / 100;
    renderPaintMixer();
  });
  el.querySelector('input[type="color"]').addEventListener("input", (e) => fillMixerPot(e.target.value));
}

function renderPaintMixer() {
  const el = paintMode.el.querySelector(".paint-mixer");
  el.querySelectorAll(".paint-mixer-pot").forEach((b) => {
    const i = Number(b.dataset.pot);
    b.style.setProperty("--swatch", paintMixer.pots[i]);
    b.classList.toggle("active", i === paintMixer.active);
  });
  const ratio = el.querySelector(".paint-mixer-ratio"), light = el.querySelector(".paint-mixer-light");
  ratio.value = Math.round(paintMixer.ratio * 100);
  light.value = Math.round(paintMixer.light * 100);
  ratio.style.background = mixerGradient((t) => mixPaints(paintMixer.pots[0], paintMixer.pots[1], t));
  light.style.background = mixerGradient((t) => mixerResult(paintMixer.ratio, t * 2 - 1));
  el.querySelector(".paint-mixer-result").style.setProperty("--swatch", mixerResult());
  el.querySelector('input[type="color"]').value = paintMixer.pots[paintMixer.active];
}

function fillMixerPot(color) {
  paintMixer.pots[paintMixer.active] = color.toLowerCase();
  paintMixer.active = 1 - paintMixer.active;
  renderPaintMixer();
}

function paintMixerOpen() {
  return !!paintMode.el && !paintMode.el.querySelector(".paint-mixer").hidden;
}

function togglePaintMixer(show = !paintMixerOpen()) {
  const el = paintMode.el.querySelector(".paint-mixer");
  if (show) {
    // Start: die Pinselfarbe in Topf 1, Topf 2 ist dran
    paintMixer.pots[0] = paintMode.color || paintMixer.pots[0];
    paintMixer.active = 1;
    paintMixer.light = 0;
    renderPaintMixer();
  }
  el.hidden = !show;
  paintMode.el.querySelector('[data-paint-action="mixer"]').classList.toggle("active", show);
}

// Ein Farbtupfer bei offenem Mischer füllt den Topf, statt die Pinselfarbe zu wechseln
function paintMixerTakesColor(color) {
  if (!paintMixerOpen()) return false;
  fillMixerPot(color);
  return true;
}

function paintMixerAction(action, btn) {
  if (action === "m-pot") {
    paintMixer.active = Number(btn.dataset.pot);
    renderPaintMixer();
  } else if (action === "m-close") {
    togglePaintMixer(false);
  } else if (action === "m-take") {
    const color = mixerResult();
    paintMixer.own = [color, ...paintMixer.own.filter((c) => c !== color)].slice(0, 8);
    paintMode.color = color;
    paintMode.tool = "pen";
    togglePaintMixer(false);
    renderPaintColors();
    applyPaintTool();
    savePaintPrefs();
    savePaintMixerColors();
  }
}

async function loadPaintMixerColors() {
  try {
    const data = await apiJson("/api/v1/design");
    paintMixer.own = data.paint_colors || [];
  } catch (err) {
    console.error("Eigene Malfarben nicht geladen:", err);
  }
}

async function savePaintMixerColors() {
  try {
    const data = await apiJson("/api/v1/design/paint-colors", { method: "PUT", json: { colors: paintMixer.own } });
    paintMixer.own = data.paint_colors;
  } catch (err) {
    console.error("Eigene Malfarben nicht gespeichert:", err);
  }
}
