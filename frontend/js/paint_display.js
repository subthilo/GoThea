// ============================================================================
// Theas gemalte Hintergründe und Kacheln anzeigen (Malen – Architektur im Konzept-Doc)
// ============================================================================
// Welche Flächen bemalbar sind, steht in js/paint_slots.js (data-paint am Tab, data-paint-tile an Kacheln).
// Der Server liefert zu jedem Platz sein Bild (kein Rückfall auf ein Bild „für alle Fächer“).
// Im Eltern-Modus keine Bilder (neutral). Hinter Tafel, Leser und Übungen nie (dort kein data-paint).
// Das Kachelbild liegt als Hintergrund in der Kachel (CSS-Variable --paint-img): Rundung, Rand und
// Schatten bleiben der Kachel, die Abdeckung und der Textschutz stehen in css/paintings.css.

let paintDisplayRequest = 0;

function activePaintPane() {
  const pane = document.querySelector(".tab-pane.active");
  if (!pane || !pane.dataset.paint || document.body.classList.contains("reader-zen-mode")) return null;
  return pane;
}

function activePaintKey() {
  const pane = activePaintPane();
  return pane ? pane.dataset.paint : null;
}

function showPaintBackground(url) {
  const layer = document.getElementById("paint-bg");
  const img = layer ? layer.querySelector(".paint-bg-img") : null;
  if (!img) return;
  if (!url) {
    document.body.classList.remove("paint-bg-on");
    img.removeAttribute("src");
    return;
  }
  if (img.getAttribute("src") === url) {
    document.body.classList.add("paint-bg-on");
    return;
  }
  // Erst einblenden, wenn das Bild da ist – sonst blitzt die leere Abdeckung auf
  img.onload = () => document.body.classList.add("paint-bg-on");
  img.onerror = () => document.body.classList.remove("paint-bg-on");
  img.src = url;
}

function showPaintTile(el, url) {
  el.classList.toggle("has-paint", Boolean(url));
  if (url) el.style.setProperty("--paint-img", `url("${url}")`);
  else el.style.removeProperty("--paint-img");
}

function clearPaintTiles() {
  document.querySelectorAll("[data-paint-tile].has-paint").forEach((el) => showPaintTile(el, null));
}

async function applyPaintings() {
  const request = ++paintDisplayRequest;
  const parent = typeof isParentActive !== "undefined" && isParentActive;
  const pane = parent ? null : activePaintPane();
  const fab = document.getElementById("btn-paint");
  if (fab) fab.hidden = !pane;
  if (!pane) {
    showPaintBackground(null);
    clearPaintTiles();
    return;
  }
  const key = pane.dataset.paint;
  const tiles = paintTilesOf(pane);
  let slots = {};
  try {
    const keys = [key, ...tiles.map((t) => t.key)].map(encodeURIComponent).join(",");
    slots = (await apiJson(`/api/v1/paintings?keys=${keys}`)).slots;
  } catch (err) {
    console.warn("Gemalte Bilder nicht geladen:", err);
  }
  if (request !== paintDisplayRequest) return; // inzwischen andere Seite
  showPaintBackground(slots[key] && slots[key].image_url);
  tiles.forEach((t) => showPaintTile(t.el, slots[t.key] && slots[t.key].image_url));
}

window.applyPaintings = applyPaintings;
