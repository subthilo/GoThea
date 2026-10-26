// ============================================================================
// Ausmalbilder verwalten (Eltern-Modus, Tab „Upload“): SVG hochladen, Vorschau, freigeben, entfernen
// ============================================================================
// Der Server berechnet die Felder im Hintergrund (auf dem Pi bis zu zwei Minuten); solange ein Bild
// „rechnet“, fragt die Liste alle paar Sekunden nach. Die Vorschau zeigt die Linien, so wie Thea sie
// ausmalt. Erst freigegebene Bilder sieht Thea im Mal-Modus. Konzept-Doc, Tab „Ausmalbilder“.

const COLORING_POLL_MS = 5000;
const openColoringRows = new Set();
let coloringPollTimer = null;

const COLORING_STATUS = {
  rechnet: { icon: "Sanduhr", title: "Felder werden berechnet …" },
  fehler: { icon: "Warnung", title: "Nicht verwendbar" },
  berechnet: { icon: "Bild", title: "Bereit – noch nicht freigegeben" },
  freigegeben: { icon: "Haken", title: "Freigegeben – Thea kann es ausmalen" },
};

async function loadColoringPages() {
  const list = document.getElementById("coloring-pages-list");
  if (!list) return;
  clearTimeout(coloringPollTimer);
  let pages = [];
  try {
    pages = await apiJson("/api/v1/coloring-pages");
  } catch (err) {
    console.warn("Ausmalbilder nicht geladen:", err);
    return;
  }
  list.innerHTML = "";
  pages.forEach((p) => list.appendChild(buildColoringRow(p)));
  const count = document.getElementById("coloring-pages-count");
  if (count) count.textContent = String(pages.length);
  if (pages.some((p) => p.status === "rechnet")) {
    coloringPollTimer = setTimeout(() => {
      if (document.getElementById("tab-uploads").classList.contains("active")) loadColoringPages();
    }, COLORING_POLL_MS);
  }
}

function buildColoringRow(p) {
  const row = document.createElement("div");
  row.className = `doc-row coloring-row status-${p.status}`;
  row.dataset.coloringId = p.id;
  const st = COLORING_STATUS[p.status] || COLORING_STATUS.fehler;
  const ready = p.status === "berechnet" || p.status === "freigegeben";
  row.innerHTML = `
    <div class="doc-row-head" role="button" tabindex="0" aria-expanded="false" title="Vorschau ein- oder ausblenden">
      <span class="doc-row-chevron">${icon("Aufklappen")}</span>
      <span class="coloring-thumb">${p.thumb_url ? `<img src="${p.thumb_url}" alt="">` : icon(st.icon)}</span>
      <span class="doc-row-title"><span class="doc-row-name"></span></span>
      <span class="coloring-status" title="${st.title}">${icon(st.icon)}${p.field_count ? ` ${p.field_count}` : ""}</span>
      ${ready ? `<button type="button" class="btn-mat-action coloring-release" data-release="${p.status === "freigegeben" ? "0" : "1"}"
        title="${p.status === "freigegeben" ? "Zurückziehen" : "Freigeben"}" aria-label="${p.status === "freigegeben" ? "Zurückziehen" : "Freigeben"}">
        ${icon(p.status === "freigegeben" ? "Rückgängig" : "Haken")}</button>` : ""}
    </div>
    <div class="doc-row-body">
      ${p.error ? `<p class="coloring-error">${icon("Warnung")} <span></span></p>` : ""}
      <div class="coloring-preview"></div>
      <div class="doc-row-actions">
        ${p.status === "fehler" ? `<button type="button" class="btn-mat-action coloring-recompute" title="Felder neu berechnen">${icon("Aktualisieren")} Neu berechnen</button>` : ""}
        <button type="button" class="btn-mat-action coloring-remove" title="Aus der Liste nehmen (schon bemalte Bilder bleiben)">${icon("Papierkorb")} Entfernen</button>
      </div>
    </div>`;
  row.querySelector(".doc-row-name").textContent = p.name;
  if (p.error) row.querySelector(".coloring-error span").textContent = p.error;

  makeRowExpandable(row, row.querySelector(".doc-row-head"), openColoringRows, p.id,
    () => ready && renderColoringPreview(row.querySelector(".coloring-preview"), p));

  const act = (sel, fn) => {
    const b = row.querySelector(sel);
    if (b) b.addEventListener("click", (e) => {
      e.stopPropagation();
      fn().then(loadColoringPages).catch((err) => {
        console.warn("Ausmalbild:", err);
        b.classList.add("failed");
      });
    });
  };
  act(".coloring-release", () => apiJson(`/api/v1/coloring-pages/${p.id}/freigabe`,
    { method: "PUT", json: { freigegeben: row.querySelector(".coloring-release").dataset.release === "1" } }));
  act(".coloring-recompute", () => apiJson(`/api/v1/coloring-pages/${p.id}/recompute`, { method: "POST" }));
  act(".coloring-remove", () => apiJson(`/api/v1/coloring-pages/${p.id}`, { method: "DELETE" }));
  return row;
}

// Vorschau: die Linien auf weißem Grund (bunte Felder brauchte es nicht, Nutzer 26.10.)
async function renderColoringPreview(box, p) {
  if (box.dataset.loaded) return;
  box.dataset.loaded = "1";
  try {
    const shapes = await apiJson(p.shapes_url);
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${shapes.width} ${shapes.height}`);
    svg.setAttribute("class", "coloring-preview-svg");
    const ink = document.createElementNS(ns, "path");
    ink.setAttribute("d", shapes.ink);
    ink.setAttribute("fill", "#111");
    ink.setAttribute("fill-rule", "evenodd");
    svg.appendChild(ink);
    box.appendChild(svg);
  } catch (err) {
    box.dataset.loaded = "";
    console.warn("Vorschau nicht geladen:", err);
  }
}

async function uploadColoringPage(file) {
  const form = new FormData();
  form.append("file", file);
  form.append("name", file.name.replace(/\.svg$/i, ""));
  try {
    await apiJson("/api/v1/coloring-pages", { method: "POST", body: form });
  } catch (err) {
    console.warn("Ausmalbild nicht hochgeladen:", err);
    alert(err.message || "Hochladen hat nicht geklappt.");  // wie beim Dokument-Upload
  }
  loadColoringPages();
}

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("coloring-file-input");
  const btn = document.getElementById("btn-coloring-upload");
  if (!input || !btn) return;
  btn.addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    [...input.files].forEach(uploadColoringPage);
    input.value = "";
  });
});

window.loadColoringPages = loadColoringPages;
