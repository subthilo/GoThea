// ==========================================================================
// BÜCHER-BROWSER LOGIK (#tab-books)
// ==========================================================================

let currentBooks = [];
let activeBookId = null;
let activeBookDetail = null;
let activeChapter = null;
let currentChapterPage = 1;
let bookZoomMode = "width"; // Standard: Volle Dokumentbreite (100% Breite)

// Inhaltsverzeichnis aller Bücher: Buch → Kapitel → Abschnitte, jede Ebene aufklappbar.
// Kapitel-Details werden erst beim Aufklappen (oder Suchen) geladen.
const bookDetailsCache = {};
let booksTreeFilter = "";
const BOOKS_OPEN_KEY = "gothea_books_open";
const booksOpenState = loadBooksOpenState();

function loadBooksOpenState() {
  try {
    const raw = JSON.parse(localStorage.getItem(BOOKS_OPEN_KEY) || "{}");
    return { books: new Set(raw.books || []), chapters: new Set(raw.chapters || []) };
  } catch (e) {
    return { books: new Set(), chapters: new Set() };
  }
}

function saveBooksOpenState() {
  try {
    localStorage.setItem(BOOKS_OPEN_KEY, JSON.stringify({
      books: [...booksOpenState.books],
      chapters: [...booksOpenState.chapters]
    }));
  } catch (e) {}
}

async function loadBooks() {
  const grid = document.getElementById("book-catalog-grid");
  const topBar = document.getElementById("books-top-bar");
  try {
    const res = await apiFetch("/api/v1/books");
    if (!res.ok) {
      console.error("HTTP error loading books:", res.status);
      if (grid && currentBooks.length === 0) {
        grid.innerHTML = `
          <div class="empty-state-card" style="padding: 48px 24px; text-align: center; background: rgba(239, 68, 68, 0.05); border: 1px dashed rgba(239, 68, 68, 0.3); border-radius: 16px; margin: 20px 0;">
            <div style="font-size: 2.5rem; margin-bottom: 12px;">${icon("Warnung")}</div>
            <h3 style="margin-bottom: 6px; color: #ef4444;">Lehrbücher konnten nicht geladen werden</h3>
            <p style="color: var(--text-secondary); max-width: 480px; margin: 0 auto 20px; font-size: 0.9rem;">
              Beim Abrufen der Bücher ist ein Serverfehler aufgetreten (${res.status}).
            </p>
            <button onclick="loadBooks()" class="btn-primary-sm">${icon("Aktualisieren")} Erneut versuchen</button>
          </div>
        `;
      }
      return;
    }
    currentBooks = await res.json();
    scheduleBooksRefreshWhileSegmenting();

    // Veraltete Details verwerfen (Buch wird noch zerlegt oder wurde neu zerlegt)
    currentBooks.forEach((b) => {
      const cached = bookDetailsCache[b.id];
      if (cached && (b.segmenting || cached.chapters_count !== b.chapters_count || cached.total_pages !== b.total_pages)) {
        delete bookDetailsCache[b.id];
      }
    });

    if (currentBooks.length === 0) {
      if (topBar) topBar.style.display = "none";
      if (grid) {
        grid.innerHTML = `
          <div class="empty-state-card" style="padding: 48px 24px; text-align: center; background: rgba(255, 255, 255, 0.02); border: 1px dashed var(--border-color); border-radius: 16px; margin: 20px 0;">
            <div style="font-size: 3rem; margin-bottom: 12px;">${icon("Bücher")}</div>
            <h3 style="margin-bottom: 6px;">Noch keine Schulbücher hinterlegt</h3>
            <p style="color: var(--text-secondary); max-width: 480px; margin: 0 auto 20px; font-size: 0.9rem;">
              Sobald Lehrwerke hochgeladen oder importiert werden, kannst du hier interaktiv durch alle Kapitel und Seiten navigieren.
            </p>
            <button id="btn-books-goto-upload" class="btn-primary-sm" style="display: inline-flex; align-items: center; gap: 8px;">
              <span>${icon("Upload")}</span>
              <span>Schulbuch hochladen</span>
            </button>
          </div>
        `;
        const btnUpload = document.getElementById("btn-books-goto-upload");
        if (btnUpload) {
          btnUpload.addEventListener("click", () => switchToTab("uploads"));
        }
      }
      return;
    }

    if (topBar) topBar.style.display = "flex";
    if (currentBooks.length === 1) booksOpenState.books.add(currentBooks[0].id);

    renderBooksTree();
    const ids = booksTreeFilter ? currentBooks.map((b) => b.id) : [...booksOpenState.books];
    await ensureBookDetails(ids);
    renderBooksTree();
  } catch (err) {
    console.error("Fehler beim Laden der Schulbücher:", err);
  }
}

// Solange ein Buch im Hintergrund in Kapitel zerlegt wird, regelmäßig nachladen
let booksRefreshTimer = null;
function scheduleBooksRefreshWhileSegmenting() {
  clearTimeout(booksRefreshTimer);
  if (!currentBooks.some((b) => b.segmenting)) return;
  booksRefreshTimer = setTimeout(() => {
    const booksTabActive = document.getElementById("tab-books")?.classList.contains("active");
    if (booksTabActive && !document.body.classList.contains("reader-zen-mode")) {
      loadBooks();
    } else {
      scheduleBooksRefreshWhileSegmenting();
    }
  }, 5000);
}

// Lädt fehlende Buch-Details (mit Kapiteln und Abschnitten) parallel nach
async function ensureBookDetails(bookIds) {
  const known = new Set(currentBooks.map((b) => b.id));
  const missing = bookIds.filter((id) => known.has(id) && !bookDetailsCache[id]);
  await Promise.all(missing.map(async (id) => {
    try {
      const res = await apiFetch(`/api/v1/books/${id}`);
      if (res.ok) bookDetailsCache[id] = await res.json();
    } catch (err) {
      console.error("Buch-Details konnten nicht geladen werden:", err);
    }
  }));
}

// Macht ein Buch zum aktiven Buch für Reader, Inhalts-Schublade und Kapitel-Blättern
function activateBook(detail) {
  activeBookId = detail.id;
  activeBookDetail = detail;
  const drawerSubEl = document.getElementById("drawer-book-subtitle");
  if (drawerSubEl) drawerSubEl.textContent = detail.title;
  renderDrawerTOC();
}

// Buch frisch laden und aktivieren (z. B. für Suchtreffer)
async function selectBook(bookId) {
  try {
    const res = await apiFetch(`/api/v1/books/${bookId}`);
    if (!res.ok) return;
    const detail = await res.json();
    bookDetailsCache[bookId] = detail;
    activateBook(detail);
    booksOpenState.books.add(bookId);
    saveBooksOpenState();
    renderBooksTree();
  } catch (err) {
    console.error("Fehler beim Abruf der Buch-Details:", err);
  }
}

// Bücher ohne Kapitel-Einteilung als Ganzes öffnen
function fullBookChapter(detail) {
  return {
    id: detail.id,
    chapter_number: 0,
    title: detail.title,
    start_page: 1,
    end_page: detail.total_pages,
    page_count: detail.total_pages,
    focus: detail.summary || "Gesamtes Lehrwerk",
    file_url: `/api/v1/materials/${detail.id}/file`,
    filename: `${detail.title}.pdf`
  };
}

function openBookChapter(detail, ch, page = 1) {
  activateBook(detail);
  booksOpenState.books.add(detail.id);
  saveBooksOpenState();
  openChapter(ch, page);
}

function sectionMatches(sec, term) {
  return sec.title.toLowerCase().includes(term) || String(sec.book_page).includes(term);
}

function chapterMatches(ch, term) {
  return ch.title.toLowerCase().includes(term) ||
    (ch.topic_name && ch.topic_name.toLowerCase().includes(term)) ||
    (ch.focus && ch.focus.toLowerCase().includes(term));
}

function renderBooksTree() {
  const container = document.getElementById("book-catalog-grid");
  if (!container || currentBooks.length === 0) return;
  const term = booksTreeFilter.toLowerCase().trim();
  const nodes = currentBooks.map((book) => renderBookNode(book, term)).filter(Boolean);
  container.innerHTML = nodes.length
    ? nodes.join("")
    : `<div class="btree-empty">Keine Kapitel oder Abschnitte zu „${escapeHtml(booksTreeFilter)}“ gefunden.</div>`;
}

function renderBookNode(book, term) {
  const detail = bookDetailsCache[book.id];
  const titleHit = Boolean(term) && book.title.toLowerCase().includes(term);

  // Beim Suchen: nur passende Kapitel zeigen; Kapitel mit passenden Abschnitten aufklappen
  let entries = null;
  if (detail) {
    entries = (detail.chapters || []).map((ch) => {
      const nodes = buildSectionTree(ch.sections || []);
      if (!term || titleHit || chapterMatches(ch, term)) {
        return { ch, nodes, open: booksOpenState.chapters.has(ch.id) };
      }
      const hits = filterSectionTree(nodes, term);
      return hits.length ? { ch, nodes: hits, open: true } : null;
    }).filter(Boolean);
  }
  if (term && !titleHit && !(entries && entries.length)) return "";

  const open = term ? true : booksOpenState.books.has(book.id);
  const color = subjectColor(book.subject_name);
  const meta = book.segmenting
    ? `${icon("Sanduhr")} wird in Kapitel zerlegt …`
    : `${book.chapters_count} Kapitel · ${book.total_pages} S.`;

  let children = "";
  if (open) {
    if (!detail) {
      children = `<div class="btree-loading">Kapitel werden geladen …</div>`;
    } else if (!(detail.chapters || []).length) {
      children = renderFullBookRow(detail);
    } else {
      children = entries.map((e) => renderChapterNode(detail, e)).join("");
    }
  }

  return `
    <div class="btree-book ${open ? "open" : ""}" style="--book-color: ${color};">
      <div class="btree-row btree-book-row" data-action="toggle-book" data-book-id="${escapeHtml(book.id)}" role="button" tabindex="0" aria-expanded="${open}">
        <span class="btree-chevron">${icon("Aufklappen")}</span>
        <span class="btree-book-icon">${subjectIcon(book.subject_name)}</span>
        <span class="btree-title">${escapeHtml(book.title)}</span>
        <span class="btree-meta">${meta}</span>
      </div>
      ${open ? `<div class="btree-children">${children}</div>` : ""}
    </div>
  `;
}

function renderFullBookRow(detail) {
  return `
    <div class="btree-chapter">
      <div class="btree-row btree-chapter-row" data-action="open-full-book" data-book-id="${escapeHtml(detail.id)}" role="button" tabindex="0">
        <span class="btree-chevron"></span>
        <span class="btree-num">${icon("Lesen")}</span>
        <span class="btree-title">Gesamtes Buch</span>
        <span class="btree-pages">${detail.total_pages} S.</span>
        <span class="btree-open">${icon("Pfeil rechts")}</span>
      </div>
    </div>
  `;
}

// Abschnitte eines Kapitels (flach mit "level") → verschachtelter Baum
function buildSectionTree(sections) {
  const root = [];
  const stack = [];
  sections.forEach((sec, i) => {
    const node = { sec, key: i, children: [] };
    const level = sec.level || 2;
    while (stack.length && stack[stack.length - 1].level >= level) stack.pop();
    (stack.length ? stack[stack.length - 1].node.children : root).push(node);
    stack.push({ level, node });
  });
  return root;
}

// Beim Suchen: passende Abschnitte samt ihrer Eltern behalten, Eltern aufklappen
function filterSectionTree(nodes, term) {
  return nodes.map((n) => {
    const kids = filterSectionTree(n.children, term);
    if (sectionMatches(n.sec, term)) return { ...n, forceOpen: kids.length > 0 };
    return kids.length ? { ...n, children: kids, forceOpen: true } : null;
  }).filter(Boolean);
}

function renderSectionNodes(ids, chapterId, nodes) {
  const indentLeaves = nodes.some((n) => n.children.length);
  return nodes.map((n) => {
    const { sec } = n;
    const title = `<span class="btree-section-title">${escapeHtml(sec.title)}</span><span class="btree-leader" aria-hidden="true"></span>`;
    if (!n.children.length) {
      return `
        <button type="button" class="btree-row btree-section-row" data-action="open-section" ${ids} data-page="${sec.relative_page}" title="Buchseite ${sec.book_page} aufschlagen">
          ${indentLeaves ? `<span class="btree-chevron"></span>` : ""}${title}
          <span class="btree-section-page">${sec.book_page}</span>
        </button>`;
    }
    const key = `${chapterId}#${n.key}`;
    const open = n.forceOpen || booksOpenState.chapters.has(key);
    return `
      <div class="btree-node ${open ? "open" : ""}">
        <div class="btree-row btree-section-row" data-action="toggle-node" data-key="${escapeHtml(key)}" role="button" tabindex="0" aria-expanded="${open}">
          <span class="btree-chevron">${icon("Aufklappen")}</span>${title}
          <button type="button" class="btree-section-page btree-page-btn" data-action="open-section" ${ids} data-page="${sec.relative_page}" title="Buchseite ${sec.book_page} aufschlagen">${sec.book_page}</button>
        </div>
        ${open ? `<div class="btree-subsections">${renderSectionNodes(ids, chapterId, n.children)}</div>` : ""}
      </div>`;
  }).join("");
}

function renderChapterNode(detail, { ch, nodes, open }) {
  const isFullBook = ch.id === detail.id;
  const hasSections = nodes.length > 0;
  const num = isFullBook ? icon("Lesen") : (ch.chapter_number === 0 ? "00" : String(ch.chapter_number ?? "").padStart(2, "0"));
  const title = isFullBook ? "Gesamtes Buch" : escapeHtml(ch.title);
  const isActive = activeChapter && activeChapter.id === ch.id;
  const ids = `data-book-id="${escapeHtml(detail.id)}" data-chapter-id="${escapeHtml(ch.id)}"`;
  const isOpen = open && hasSections;

  return `
    <div class="btree-chapter ${isOpen ? "open" : ""}">
      <div class="btree-row btree-chapter-row ${isActive ? "active" : ""}" ${hasSections ? `data-action="toggle-node" data-key="${escapeHtml(ch.id)}" aria-expanded="${isOpen}"` : `data-action="open-chapter"`} ${ids} role="button" tabindex="0">
        <span class="btree-chevron">${hasSections ? icon("Aufklappen") : ""}</span>
        <span class="btree-num">${num}</span>
        <span class="btree-title">
          ${title}
          ${ch.topic_name ? `<span class="btree-topic">${icon("Thema")} ${escapeHtml(ch.topic_name)}</span>` : ""}
        </span>
        <span class="btree-pages">S. ${ch.start_page}–${ch.end_page}</span>
        <button type="button" class="btree-open" data-action="open-chapter" ${ids} title="Kapitel aufschlagen">
          ${icon("Lesen")}<span class="btree-open-label">Aufschlagen</span>
        </button>
      </div>
      ${isOpen ? `<div class="btree-children btree-sections">${renderSectionNodes(ids, ch.id, nodes)}</div>` : ""}
    </div>
  `;
}

async function onBooksTreeClick(e) {
  const el = e.target.closest("[data-action]");
  if (!el || !e.currentTarget.contains(el)) return;
  const { action, bookId, chapterId } = el.dataset;

  if (action === "toggle-book" || action === "toggle-node") {
    if (booksTreeFilter) return; // beim Suchen ist alles Passende aufgeklappt
    const set = action === "toggle-book" ? booksOpenState.books : booksOpenState.chapters;
    const key = action === "toggle-book" ? bookId : el.dataset.key;
    if (set.has(key)) set.delete(key); else set.add(key);
    saveBooksOpenState();
    renderBooksTree();
    if (action === "toggle-book" && set.has(key) && !bookDetailsCache[key]) {
      await ensureBookDetails([key]);
      renderBooksTree();
    }
    return;
  }

  const detail = bookDetailsCache[bookId];
  if (!detail) return;
  if (action === "open-full-book") {
    openBookChapter(detail, fullBookChapter(detail), 1);
    return;
  }
  const ch = (detail.chapters || []).find((c) => c.id === chapterId);
  if (!ch) return;
  const page = action === "open-section" ? (parseInt(el.dataset.page, 10) || 1) : 1;
  openBookChapter(detail, ch, page);
}

async function onBooksFilterInput(value) {
  booksTreeFilter = value;
  renderBooksTree();
  if (value.trim()) {
    await ensureBookDetails(currentBooks.map((b) => b.id));
    if (booksTreeFilter === value) renderBooksTree();
  }
}

// Ansicht 2: Vollbreiten-Reader für ein gewähltes Kapitel öffnen
function openChapter(ch, targetPage = 1) {
  if (!ch) return;
  activeChapter = ch;
  currentChapterPage = Math.max(1, Math.min(ch.page_count, targetPage || 1));

  // Umschalten auf Reader-Ansicht & Zen-Mode aktivieren (100% Bildschirm fürs Buch)
  const catalogView = document.getElementById("book-catalog-view");
  const readerView = document.getElementById("book-reader-view");
  if (catalogView) catalogView.style.display = "none";
  if (readerView) readerView.style.display = "flex";
  document.body.classList.add("reader-zen-mode");

  // Ultraschlanke Kopfzeile (Vorschlag 1)
  const titleSlim = document.getElementById("reader-chapter-title-slim");
  const counterSlim = document.getElementById("reader-page-counter-slim");
  const downloadBtn = document.getElementById("btn-book-download-pdf");

  if (titleSlim) {
    // Einzelne Dokumente (Mitschrift, Arbeitsblatt …) haben keine Kapitelnummer: nur der Titel
    const unitLabel = ch.chapter_number === 0 ? "Titelei"
      : (ch.chapter_number != null ? `Einheit ${ch.chapter_number}` : "");
    const fullTitle = unitLabel ? `${unitLabel}: ${ch.title}` : ch.title;
    titleSlim.textContent = fullTitle;
    titleSlim.title = fullTitle;
  }
  if (counterSlim) {
    const absPage = ch.start_page + currentChapterPage - 1;
    counterSlim.textContent = `Seite ${currentChapterPage} von ${ch.page_count} (S. ${absPage})`;
  }
  if (downloadBtn) {
    downloadBtn.href = ch.file_url;
    downloadBtn.setAttribute("download", ch.filename);
  }

  // Drawer aktiv markieren
  updateDrawerActiveState();

  // Drawer schließen falls offen
  closeTOCDrawer();

  // Seiten-Pills & gewählte Seite anzeigen
  renderBookPageStrip();
  renderChapterPage();

  // Nach oben scrollen für optimales Leseerlebnis
  const canvasWrap = document.getElementById("book-page-canvas-wrapper");
  if (canvasWrap) canvasWrap.scrollTop = 0;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function closeReaderToCatalog() {
  const catalogView = document.getElementById("book-catalog-view");
  const readerView = document.getElementById("book-reader-view");
  if (readerView) readerView.style.display = "none";
  if (catalogView) catalogView.style.display = "flex";
  document.body.classList.remove("reader-zen-mode");
  closeTOCDrawer();
  // Zurück an die Stelle im Inhaltsverzeichnis, von der aus gelesen wurde
  renderBooksTree();
  const activeRow = document.querySelector("#book-catalog-grid .btree-chapter-row.active");
  if (activeRow) activeRow.scrollIntoView({ block: "center" });
  else window.scrollTo({ top: 0, behavior: "smooth" });
}

function updateChapterNavButtons() {
  const prevBtn = document.getElementById("btn-reader-prev-chapter");
  const nextBtn = document.getElementById("btn-reader-next-chapter");
  if (!activeBookDetail || !activeChapter) return;

  const chaps = activeBookDetail.chapters || [];
  const idx = chaps.findIndex(c => c.id === activeChapter.id);

  if (prevBtn) prevBtn.disabled = idx <= 0;
  if (nextBtn) nextBtn.disabled = idx < 0 || idx >= chaps.length - 1;
}

function navigateChapter(delta) {
  if (!activeBookDetail || !activeChapter) return;
  const chaps = activeBookDetail.chapters || [];
  const idx = chaps.findIndex(c => c.id === activeChapter.id);
  const targetIdx = idx + delta;
  if (targetIdx >= 0 && targetIdx < chaps.length) {
    openChapter(chaps[targetIdx], 1);
  }
}

// Schnelles Blättern im Kapitel (per 2-Finger-Swipe, Schwebepfeile oder Tastatur)
function flipBookPage(delta) {
  if (!activeChapter) return;
  const targetPage = currentChapterPage + delta;
  if (targetPage >= 1 && targetPage <= activeChapter.page_count) {
    currentChapterPage = targetPage;
    renderChapterPage();
  }
}

// 3. Offcanvas TOC Drawer
function openTOCDrawer() {
  const drawer = document.getElementById("book-toc-drawer");
  const backdrop = document.getElementById("book-toc-drawer-backdrop");
  if (drawer) drawer.classList.add("open");
  if (backdrop) backdrop.classList.add("open");
}

function closeTOCDrawer() {
  const drawer = document.getElementById("book-toc-drawer");
  const backdrop = document.getElementById("book-toc-drawer-backdrop");
  if (drawer) drawer.classList.remove("open");
  if (backdrop) backdrop.classList.remove("open");
}

function renderDrawerTOC(filterTerm = "") {
  const container = document.getElementById("drawer-chapters-list");
  if (!container || !activeBookDetail) return;
  container.innerHTML = "";

  const term = (filterTerm || "").toLowerCase().trim();
  const chapters = (activeBookDetail.chapters || []).filter((ch) => {
    if (!term) return true;
    const hasSectionMatch = (ch.sections || []).some(
      (s) =>
        s.title.toLowerCase().includes(term) ||
        String(s.book_page).includes(term)
    );
    return (
      ch.title.toLowerCase().includes(term) ||
      (ch.topic_name && ch.topic_name.toLowerCase().includes(term)) ||
      hasSectionMatch
    );
  });

  if (chapters.length === 0) {
    container.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 0.88rem;">Keine Lerneinheiten für "${escapeHtml(filterTerm)}" gefunden.</div>`;
    return;
  }

  chapters.forEach((ch) => {
    const item = document.createElement("div");
    const isActive = activeChapter && activeChapter.id === ch.id;
    item.className = `drawer-chapter-item ${isActive ? "active" : ""}`;
    item.dataset.chapterId = ch.id;

    const unitLabel = ch.chapter_number === 0 ? "Titelei" : `Einheit ${ch.chapter_number}`;

    let sectionsHtml = "";
    if (ch.sections && ch.sections.length > 0) {
      const visibleSections = term
        ? ch.sections.filter(
            (s) =>
              s.title.toLowerCase().includes(term) ||
              String(s.book_page).includes(term) ||
              ch.title.toLowerCase().includes(term)
          )
        : ch.sections;

      if (visibleSections.length > 0) {
        sectionsHtml = `
          <div class="drawer-sections-list">
            ${visibleSections
              .map((sec) => {
                const isSecActive = isActive && currentChapterPage >= sec.relative_page;
                return `
                  <div class="drawer-section-item ${isSecActive ? "active" : ""}" data-target-page="${sec.relative_page}" title="Direkt aufschlagen: ${escapeHtml(sec.title)} (Buchseite ${sec.book_page})">
                    <span class="drawer-sec-bullet">↳</span>
                    <span class="drawer-sec-title">${escapeHtml(sec.title)}</span>
                    <span class="drawer-sec-page">S. ${sec.book_page}</span>
                  </div>
                `;
              })
              .join("")}
          </div>
        `;
      }
    }

    item.innerHTML = `
      <div class="drawer-chapter-header" title="Kapitel ab Seite 1 aufschlagen">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="catalog-badge">${unitLabel}</span>
          <span style="font-size: 0.74rem; color: var(--text-muted); font-weight: 600;">S. ${ch.start_page}–${ch.end_page}</span>
        </div>
        <div style="font-size: 0.92rem; font-weight: 700; color: var(--text-primary); margin-top: 4px;">${escapeHtml(ch.title)}</div>
        ${ch.topic_name ? `<div style="font-size: 0.76rem; color: #94a3b8;">${icon("Thema")} ${escapeHtml(ch.topic_name)}</div>` : ""}
      </div>
      ${sectionsHtml}
    `;

    const chapHeader = item.querySelector(".drawer-chapter-header");
    if (chapHeader) {
      chapHeader.addEventListener("click", () => openChapter(ch, 1));
    }

    item.querySelectorAll(".drawer-section-item").forEach((secEl) => {
      secEl.addEventListener("click", (e) => {
        e.stopPropagation();
        const p = parseInt(secEl.dataset.targetPage, 10) || 1;
        openChapter(ch, p);
      });
    });

    container.appendChild(item);
  });
}

function updateDrawerActiveState() {
  document.querySelectorAll(".drawer-chapter-item").forEach((it) => {
    const isChapActive = activeChapter && it.dataset.chapterId === activeChapter.id;
    it.classList.toggle("active", isChapActive);
    if (isChapActive && activeChapter && activeChapter.sections && activeChapter.sections.length > 0) {
      let currentActiveRel = 1;
      activeChapter.sections.forEach((s) => {
        if (s.relative_page <= currentChapterPage && s.relative_page >= currentActiveRel) {
          currentActiveRel = s.relative_page;
        }
      });
      it.querySelectorAll(".drawer-section-item").forEach((sEl) => {
        const p = parseInt(sEl.dataset.targetPage, 10);
        sEl.classList.toggle("active", p === currentActiveRel);
      });
    }
  });
}

// 4. Seiten-Pills & Seiten-Rendering
function renderBookPageStrip() {
  const strip = document.getElementById("book-page-strip");
  if (!strip || !activeChapter) return;
  strip.innerHTML = "";

  for (let p = 1; p <= activeChapter.page_count; p++) {
    const absPage = activeChapter.start_page + p - 1;
    const pill = document.createElement("div");
    pill.className = `book-page-pill ${p === currentChapterPage ? "active" : ""}`;
    pill.dataset.page = p;
    pill.textContent = p;
    pill.title = `Seite ${p} des Kapitels (Buchseite ${absPage})`;
    pill.addEventListener("click", () => {
      currentChapterPage = p;
      renderChapterPage();
    });
    strip.appendChild(pill);
  }
}

async function renderChapterPage() {
  if (!activeChapter) return;

  const counterEl = document.getElementById("book-page-counter");
  const counterSlim = document.getElementById("reader-page-counter-slim");
  const prevBtn = document.getElementById("btn-book-prev-page");
  const nextBtn = document.getElementById("btn-book-next-page");
  const floatPrev = document.getElementById("btn-floating-prev");
  const floatNext = document.getElementById("btn-floating-next");
  const imgEl = document.getElementById("book-page-img");
  const loadingEl = document.getElementById("book-page-loading");

  const absPage = activeChapter.start_page + currentChapterPage - 1;
  if (counterSlim) {
    counterSlim.textContent = `Seite ${currentChapterPage} von ${activeChapter.page_count} (S. ${absPage})`;
  }
  if (counterEl) {
    counterEl.innerHTML = `Seite ${currentChapterPage} von ${activeChapter.page_count} <small id="book-page-absolute">(Buchseite ${absPage})</small>`;
  }

  if (prevBtn) prevBtn.disabled = currentChapterPage <= 1;
  if (nextBtn) nextBtn.disabled = currentChapterPage >= activeChapter.page_count;
  if (floatPrev) floatPrev.disabled = currentChapterPage <= 1;
  if (floatNext) floatNext.disabled = currentChapterPage >= activeChapter.page_count;

  // Schnell-Sprung-Dropdown für Unterthemen / Inhaltsverzeichnis-Einträge synchronisieren
  const sectionWrap = document.getElementById("book-section-picker-wrap");
  const sectionSelect = document.getElementById("book-section-select");
  if (sectionWrap && sectionSelect) {
    const sections = activeChapter.sections || [];
    if (sections.length > 0) {
      sectionWrap.style.display = "inline-flex";
      sectionSelect.innerHTML = sections
        .map(
          (s) =>
            `<option value="${s.relative_page}">${escapeHtml(s.title)} (S. ${s.book_page})</option>`
        )
        .join("");

      // Bestimme den Abschnitt, in dem Thea sich gerade befindet
      let currentActiveRel = sections[0].relative_page;
      sections.forEach((s) => {
        if (s.relative_page <= currentChapterPage) {
          currentActiveRel = s.relative_page;
        }
      });
      sectionSelect.value = String(currentActiveRel);

      if (!sectionSelect.dataset.wired) {
        sectionSelect.dataset.wired = "true";
        sectionSelect.addEventListener("change", (e) => {
          const targetPage = parseInt(e.target.value, 10);
          if (targetPage && targetPage >= 1 && activeChapter && targetPage <= activeChapter.page_count) {
            currentChapterPage = targetPage;
            renderChapterPage();
          }
        });
      }
    } else {
      sectionWrap.style.display = "none";
    }
  }

  // Aktive Pill markieren und horizontal ins Sichtfeld scrollen (ohne vertikales Springen)
  document.querySelectorAll(".book-page-pill").forEach((pill) => {
    const isAct = parseInt(pill.dataset.page, 10) === currentChapterPage;
    pill.classList.toggle("active", isAct);
    if (isAct) {
      const booksTab = document.getElementById("tab-books");
      if (booksTab && booksTab.classList.contains("active")) {
        const strip = document.getElementById("book-page-strip");
        if (strip) {
          const targetScroll = pill.offsetLeft - (strip.clientWidth / 2) + (pill.clientWidth / 2);
          strip.scrollTo({ left: Math.max(0, targetScroll), behavior: "smooth" });
        }
      }
    }
  });

  // Drawer-Aktualisierung (aktive Sektion hervorheben)
  updateDrawerActiveState();

  // Scrollposition auf Seitenanfang zurücksetzen
  const canvasWrap = document.getElementById("book-page-canvas-wrapper");
  if (canvasWrap) canvasWrap.scrollTop = 0;

  // Bild in gewähltem Modus laden
  if (imgEl) {
    if (!imgEl.dataset.calloutProtected) {
      imgEl.dataset.calloutProtected = "true";
      imgEl.addEventListener("contextmenu", (e) => e.preventDefault());
      imgEl.addEventListener("dragstart", (e) => e.preventDefault());
    }
    if (loadingEl) loadingEl.style.display = "flex";
    imgEl.className = `book-page-img mode-${bookZoomMode}`;
    const targetUrl = `/api/v1/materials/${activeChapter.id}/preview?page=${currentChapterPage}`;

    const onImageLoaded = () => {
      if (loadingEl) loadingEl.style.display = "none";
      syncBookAnnotationCanvasSize();
      loadBookAnnotations(activeChapter.id, currentChapterPage);
    };

    imgEl.onload = onImageLoaded;
    imgEl.onerror = (e) => {
      if (loadingEl) loadingEl.style.display = "none";
      console.error("Fehler beim Laden der Buchseite:", targetUrl, e);
    };
    imgEl.src = targetUrl;

    if (imgEl.complete && imgEl.naturalWidth > 0) {
      onImageLoaded();
    }
  }

  // Benachbarte Seiten intelligent im Hintergrund vorladen
  prefetchAdjacentPages();
}

function prefetchAdjacentPages() {
  if (!activeChapter) return;
  const p = currentChapterPage;
  const pagesToPrefetch = [p + 1, p - 1, p + 2];

  pagesToPrefetch.forEach((targetP) => {
    if (targetP >= 1 && targetP <= activeChapter.page_count) {
      // 1. Browser-Bild-Cache vorwärmen
      const preloadImg = new Image();
      preloadImg.src = `/api/v1/materials/${activeChapter.id}/preview?page=${targetP}`;
    }
  });

  // 2. Server-seitige Prioritäts-Queue triggern
  try {
    apiFetch(`/api/v1/materials/${activeChapter.id}/prefetch?page=${p}`, {
      method: "POST"
    }).catch(() => {});
  } catch (e) {}
}

function setupBookBrowserEvents() {
  // Zurück zur Kapitelübersicht
  const btnBack = document.getElementById("btn-back-to-catalog");
  if (btnBack) {
    btnBack.addEventListener("click", closeReaderToCatalog);
  }

  // Drawer öffnen / schließen
  const btnOpenDrawer = document.getElementById("btn-open-toc-drawer");
  if (btnOpenDrawer) {
    btnOpenDrawer.addEventListener("click", openTOCDrawer);
  }

  const btnCloseDrawer = document.getElementById("btn-close-toc-drawer");
  if (btnCloseDrawer) {
    btnCloseDrawer.addEventListener("click", closeTOCDrawer);
  }

  const backdrop = document.getElementById("book-toc-drawer-backdrop");
  if (backdrop) {
    backdrop.addEventListener("click", closeTOCDrawer);
  }

  // Filter in Katalog-Ansicht
  const catalogFilter = document.getElementById("book-catalog-filter-input");
  if (catalogFilter) {
    catalogFilter.addEventListener("input", (e) => onBooksFilterInput(e.target.value));
  }

  // Inhaltsverzeichnis: Auf-/Zuklappen und Aufschlagen (ein Listener für alle Zeilen)
  const booksTree = document.getElementById("book-catalog-grid");
  if (booksTree) {
    booksTree.addEventListener("click", onBooksTreeClick);
    booksTree.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target.matches("[role='button']")) {
        e.preventDefault();
        e.target.click();
      }
    });
  }

  // Filter im Offcanvas Drawer
  const drawerFilter = document.getElementById("drawer-filter-input");
  if (drawerFilter) {
    drawerFilter.addEventListener("input", (e) => {
      renderDrawerTOC(e.target.value);
    });
  }

  // Vorheriges / Nächstes Kapitel Buttons im Reader
  const prevChapBtn = document.getElementById("btn-reader-prev-chapter");
  if (prevChapBtn) {
    prevChapBtn.addEventListener("click", () => navigateChapter(-1));
  }

  const nextChapBtn = document.getElementById("btn-reader-next-chapter");
  if (nextChapBtn) {
    nextChapBtn.addEventListener("click", () => navigateChapter(1));
  }

  // Seiten-Navigation: Schwebepfeile links & rechts
  const floatPrev = document.getElementById("btn-floating-prev");
  const floatNext = document.getElementById("btn-floating-next");
  if (floatPrev) {
    floatPrev.addEventListener("click", (e) => {
      e.stopPropagation();
      flipBookPage(-1);
    });
  }
  if (floatNext) {
    floatNext.addEventListener("click", (e) => {
      e.stopPropagation();
      flipBookPage(1);
    });
  }

  // Seiten-Navigation Buttons (Fallback falls vorhanden)
  const prevBtn = document.getElementById("btn-book-prev-page");
  const nextBtn = document.getElementById("btn-book-next-page");

  if (prevBtn) {
    prevBtn.addEventListener("click", () => flipBookPage(-1));
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => flipBookPage(1));
  }

  // Schwebende Stift-Palette Ein-/Ausklappen (Vorschlag 1)
  const btnToggleInk = document.getElementById("btn-toggle-ink-toolbar");
  const inkPalette = document.getElementById("reader-floating-ink-palette");
  const btnClosePalette = document.getElementById("btn-close-ink-palette");

  if (btnToggleInk && inkPalette) {
    btnToggleInk.addEventListener("click", () => {
      const isHidden = inkPalette.style.display === "none";
      inkPalette.style.display = isHidden ? "flex" : "none";
      btnToggleInk.classList.toggle("active", isHidden);
    });
  }

  if (btnClosePalette && inkPalette) {
    btnClosePalette.addEventListener("click", () => {
      inkPalette.style.display = "none";
      if (btnToggleInk) btnToggleInk.classList.remove("active");
    });
  }

  // Tastatur-Navigation (Links / Rechts Pfeiltasten zum Blättern)
  window.addEventListener("keydown", (e) => {
    const readerView = document.getElementById("book-reader-view");
    if (readerView && readerView.style.display !== "none") {
      if (e.key === "ArrowLeft") {
        flipBookPage(-1);
      } else if (e.key === "ArrowRight") {
        flipBookPage(1);
      }
    }
  });

  // 2-Finger-Wischen auf Mac-Trackpads (Horizontaler 2-Finger-Wisch erzeugt deltaX)
  let macWheelCooldown = false;
  let macAccumulatedDeltaX = 0;
  let macWheelTimer = null;

  window.addEventListener("wheel", (e) => {
    if (!document.body.classList.contains("reader-zen-mode")) return;
    const readerView = document.getElementById("book-reader-view");
    if (!readerView || readerView.style.display === "none") return;

    // Nur horizontal dominierende Gesten auswerten (damit normales vertikales Scrollen unberührt bleibt)
    if (Math.abs(e.deltaX) > Math.abs(e.deltaY) * 1.2 && Math.abs(e.deltaX) > 8) {
      if (macWheelCooldown) {
        e.preventDefault();
        return;
      }

      macAccumulatedDeltaX += e.deltaX;

      clearTimeout(macWheelTimer);
      macWheelTimer = setTimeout(() => {
        macAccumulatedDeltaX = 0;
      }, 140);

      // Schwellenwert für Seitenwechsel: 45px akkumulierter Wischweg
      if (Math.abs(macAccumulatedDeltaX) > 45) {
        macWheelCooldown = true;
        const dir = macAccumulatedDeltaX > 0 ? 1 : -1;
        macAccumulatedDeltaX = 0;
        flipBookPage(dir);
        e.preventDefault();

        // Cooldown, um Trägheitsimpulse des Trackpads abzufangen
        setTimeout(() => {
          macWheelCooldown = false;
        }, 400);
      }
    }
  }, { passive: false });

  // 1-Klick Zoom-Umschalter in der Kopfzeile & Palette
  const btnToggleZoom = document.getElementById("btn-toggle-zoom-mode");
  const zoomIcon = document.getElementById("zoom-mode-icon");
  const zoomFitBtn = document.getElementById("btn-book-zoom-fit");
  const zoomWidthBtn = document.getElementById("btn-book-zoom-width");
  const imgEl = document.getElementById("book-page-img");

  function setBookZoomMode(mode) {
    bookZoomMode = mode;
    if (imgEl) imgEl.className = `book-page-img mode-${mode}`;
    if (zoomIcon) zoomIcon.innerHTML = icon(mode === "fit" ? "Breite" : "Vollbild");
    if (btnToggleZoom) btnToggleZoom.title = mode === "fit" ? "Auf volle Breite umschalten" : "Ganze Seite einpassen";
    if (zoomFitBtn) zoomFitBtn.classList.toggle("active", mode === "fit");
    if (zoomWidthBtn) zoomWidthBtn.classList.toggle("active", mode === "width");
    setTimeout(syncBookAnnotationCanvasSize, 220);
  }

  if (btnToggleZoom) {
    btnToggleZoom.addEventListener("click", () => {
      setBookZoomMode(bookZoomMode === "width" ? "fit" : "width");
    });
  }

  if (zoomFitBtn) {
    zoomFitBtn.addEventListener("click", () => setBookZoomMode("fit"));
  }

  if (zoomWidthBtn) {
    zoomWidthBtn.addEventListener("click", () => setBookZoomMode("width"));
  }

  // Inking Engine starten
  initBookInking();
}

