// ============================================================================
// Theas gemalte Hintergründe anzeigen (Malen – Architektur im Konzept-Doc)
// ============================================================================
// Jede bemalbare Seite weist sich selbst aus: data-paint="<Platz>" am Tab (z. B. "dashboard").
// Der Server löst den Platz samt Rückfall auf ("subject-detail/sub_math" → "subject-detail").
// Im Eltern-Modus keine Bilder (neutral). Hinter Tafel, Leser und Übungen nie (dort kein data-paint).

let paintDisplayRequest = 0;

function activePaintKey() {
  const pane = document.querySelector(".tab-pane.active");
  if (!pane || document.body.classList.contains("reader-zen-mode")) return null;
  return pane.dataset.paint || null;
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

async function applyPaintings() {
  const request = ++paintDisplayRequest;
  const key = typeof isParentActive !== "undefined" && isParentActive ? null : activePaintKey();
  if (!key) {
    showPaintBackground(null);
    return;
  }
  let slot = null;
  try {
    const data = await apiJson(`/api/v1/paintings?keys=${encodeURIComponent(key)}`);
    slot = data.slots[key];
  } catch (err) {
    console.warn("Gemalter Hintergrund nicht geladen:", err);
  }
  if (request !== paintDisplayRequest) return; // inzwischen andere Seite
  showPaintBackground(slot && slot.image_url);
}

window.applyPaintings = applyPaintings;
