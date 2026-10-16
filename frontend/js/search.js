// ============================================================================
// Suche in den Unterlagen (Lupe in der Kopfzeile)
// Treffer = erschlossene Seiten; ein Tipp öffnet die Originalseite im Leser. Lösungen liefert
// der Server für Thea gar nicht erst aus.
// ============================================================================
const modalSearch = document.getElementById("modal-search");
const inputSearch = document.getElementById("input-search");
const searchResultsEl = document.getElementById("search-results");
const searchStatusEl = document.getElementById("search-status");
let searchDebounceTimer = null;
let searchRequestSeq = 0;  // nur die Antwort auf die letzte Eingabe zählt

function openSearchModal() {
  if (!modalSearch) return;
  modalSearch.style.display = "flex";
  if (inputSearch) {
    inputSearch.focus();
    inputSearch.select();
  }
}

function closeSearchModal() {
  if (modalSearch) modalSearch.style.display = "none";
}

// Server markiert Treffer im Ausschnitt mit ⟦ ⟧ (eckige Klammern kommen im Text selbst vor);
// erst escapen, dann markieren
function renderSnippet(snippet) {
  return escapeHtml(snippet || "").replace(/⟦([^⟧]*)⟧/g, "<mark>$1</mark>");
}

async function runSearch(query) {
  const seq = ++searchRequestSeq;
  if (!query.trim()) {
    searchResultsEl.innerHTML = "";
    searchStatusEl.textContent = "";
    return;
  }
  searchStatusEl.textContent = "Suche …";
  let hits;
  try {
    hits = await apiJson(`/api/v1/search?q=${encodeURIComponent(query)}&limit=15`);
  } catch (err) {
    if (seq !== searchRequestSeq) return;
    console.error("Suche fehlgeschlagen:", err);
    searchStatusEl.textContent = "Die Suche hat gerade nicht geklappt.";
    return;
  }
  if (seq !== searchRequestSeq) return;

  searchStatusEl.textContent = hits.length ? "" : "Nichts gefunden. Versuch ein anderes Wort.";
  searchResultsEl.innerHTML = "";
  hits.forEach((hit) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "search-hit";
    btn.innerHTML = `
      <div class="search-hit-label">${escapeHtml(hit.label)}</div>
      <div class="search-hit-meta">${subjectLabel(hit.subject_name)} · ${hit.source === "toc" ? "Abschnitt laut Inhaltsverzeichnis" : escapeHtml(hit.kind)}${hit.is_solution ? " · Lösung" : ""}</div>
      <div class="search-hit-snippet">${renderSnippet(hit.snippet)}</div>`;
    btn.addEventListener("click", () => openSearchHit(hit));
    li.appendChild(btn);
    searchResultsEl.appendChild(li);
  });
}

async function openSearchHit(hit) {
  closeSearchModal();
  try {
    if (hit.book_id) {
      // Buchkapitel im Buch öffnen (mit Inhaltsverzeichnis und Kapitel-Blättern)
      switchToTab("books");
      await selectBook(hit.book_id);
      const chapter = (activeBookDetail && activeBookDetail.chapters || []).find(c => c.id === hit.material_id);
      if (chapter) {
        openChapter(chapter, hit.page);
        showReaderSearchHint(hit);
        return;
      }
    }
    const material = await apiJson(`/api/v1/materials/${encodeURIComponent(hit.material_id)}`);
    openMaterialInReader(material, hit.page);
    showReaderSearchHint(hit);
  } catch (err) {
    console.error("Fundstelle konnte nicht geöffnet werden:", err);
  }
}

// Zeigt im Leser kurz den Textausschnitt, damit Thea die Stelle auf der Seite findet
function showReaderSearchHint(hit) {
  let hint = document.getElementById("reader-search-hint");
  if (!hint) {
    hint = document.createElement("div");
    hint.id = "reader-search-hint";
    hint.className = "reader-search-hint";
    hint.title = "Zum Schließen tippen";
    hint.addEventListener("click", () => { hint.style.display = "none"; });
    document.body.appendChild(hint);
  }
  hint.innerHTML = renderSnippet(hit.snippet);
  hint.style.display = "block";
  clearTimeout(hint._hideTimer);
  hint._hideTimer = setTimeout(() => { hint.style.display = "none"; }, 12000);
}

function setupSearchEvents() {
  const btnOpen = document.getElementById("btn-open-search");
  if (btnOpen) btnOpen.addEventListener("click", openSearchModal);
  const btnClose = document.getElementById("btn-close-search-modal");
  if (btnClose) btnClose.addEventListener("click", closeSearchModal);
  if (modalSearch) {
    modalSearch.addEventListener("click", (e) => {
      if (e.target === modalSearch) closeSearchModal();
    });
  }
  if (inputSearch) {
    inputSearch.addEventListener("input", () => {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => runSearch(inputSearch.value), 250);
    });
    inputSearch.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        clearTimeout(searchDebounceTimer);
        runSearch(inputSearch.value);
      } else if (e.key === "Escape") {
        closeSearchModal();
      }
    });
  }
}
