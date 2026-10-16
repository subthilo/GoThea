// ==========================================================================
// BÜCHER-BROWSER LOGIK (#tab-books)
// ==========================================================================

let currentBooks = [];
let activeBookId = null;
let activeBookDetail = null;
let activeChapter = null;
let currentChapterPage = 1;
let bookZoomMode = "width"; // Standard: Volle Dokumentbreite (100% Breite)

async function loadBooks() {
  try {
    const res = await apiFetch("/api/v1/books");
    if (!res.ok) {
      console.error("HTTP error loading books:", res.status);
      const grid = document.getElementById("book-catalog-grid");
      if (grid && currentBooks.length === 0) {
        grid.innerHTML = `
          <div class="empty-state-card" style="grid-column: 1 / -1; padding: 48px 24px; text-align: center; background: rgba(239, 68, 68, 0.05); border: 1px dashed rgba(239, 68, 68, 0.3); border-radius: 16px; margin: 20px 0;">
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
    renderBooksShelf();
    scheduleBooksRefreshWhileSegmenting();

    const toolbar = document.getElementById("book-catalog-toolbar");
    const grid = document.getElementById("book-catalog-grid");

    if (currentBooks.length === 0) {
      if (toolbar) toolbar.style.display = "none";
      if (grid) {
        grid.innerHTML = `
          <div class="empty-state-card" style="grid-column: 1 / -1; padding: 48px 24px; text-align: center; background: rgba(255, 255, 255, 0.02); border: 1px dashed var(--border-color); border-radius: 16px; margin: 20px 0;">
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

    if (toolbar) toolbar.style.display = "flex";

    if (currentBooks.length > 0) {
      if (!activeBookId || !currentBooks.some(b => b.id === activeBookId)) {
        await selectBook(currentBooks[0].id);
      } else {
        await selectBook(activeBookId);
      }
    }
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

function renderBooksShelf() {
  const container = document.getElementById("books-shelf-selector");
  if (!container) return;
  container.innerHTML = "";

  currentBooks.forEach((book) => {
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = `shelf-book-pill ${book.id === activeBookId ? "active" : ""}`;
    pill.dataset.bookId = book.id;
    pill.innerHTML = `
      <span class="shelf-book-icon">${subjectIcon(book.subject_name)}</span>
      <span class="shelf-book-title">${escapeHtml(book.title)}</span>
      <span class="shelf-book-badge">${book.segmenting ? `${icon("Sanduhr")} wird in Kapitel zerlegt…` : `${book.chapters_count} Kap. • ${book.total_pages} S.`}</span>
    `;
    pill.addEventListener("click", () => selectBook(book.id));
    container.appendChild(pill);
  });
}

async function selectBook(bookId) {
  activeBookId = bookId;
  renderBooksShelf();

  try {
    const res = await apiFetch(`/api/v1/books/${bookId}`);
    if (!res.ok) return;
    activeBookDetail = await res.json();

    // Katalog-Header befüllen
    const iconEl = document.getElementById("catalog-book-icon");
    const titleEl = document.getElementById("catalog-book-title");
    const subEl = document.getElementById("catalog-book-subtitle");
    const drawerSubEl = document.getElementById("drawer-book-subtitle");

    if (iconEl) iconEl.innerHTML = subjectIcon(activeBookDetail.subject_name);
    if (titleEl) titleEl.textContent = activeBookDetail.title;
    if (subEl) subEl.textContent = `${activeBookDetail.chapters_count} Lerneinheiten • ${activeBookDetail.total_pages} Seiten`;
    if (drawerSubEl) drawerSubEl.textContent = activeBookDetail.title;

    // Standardmäßig Katalog anzeigen (oder Reader aktualisieren falls bereits geöffnet)
    const readerView = document.getElementById("book-reader-view");
    const isReaderOpen = readerView && readerView.style.display !== "none";

    renderBookCatalog();
    renderDrawerTOC();

    if (isReaderOpen && activeChapter) {
      // Wenn das Buch gewechselt wurde während der Reader offen war, selbes Kapitel oder erstes Kapitel laden
      const chaps = activeBookDetail.chapters || [];
      const sameChap = chaps.find(c => c.id === activeChapter.id);
      if (sameChap) {
        openChapter(sameChap, currentChapterPage);
      } else {
        const newChap = chaps.find(c => c.chapter_number === 1) || chaps[0];
        if (newChap) openChapter(newChap, 1);
      }
    }
  } catch (err) {
    console.error("Fehler beim Abruf der Buch-Details:", err);
  }
}

// Ansicht 1: Übersicht aller Kapitel / Lerneinheiten als Kacheln (Progressive Disclosure)
function renderBookCatalog(filterTerm = "") {
  const container = document.getElementById("book-catalog-grid");
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
      (ch.focus && ch.focus.toLowerCase().includes(term)) ||
      hasSectionMatch
    );
  });

  if (chapters.length === 0) {
    container.innerHTML = `
      <div style="padding: 36px; text-align: center; color: var(--text-muted); font-size: 0.95rem; background: var(--bg-card); border-radius: 14px; border: 1px solid var(--border-color); width: 100%;">
        <p style="margin-bottom: 16px;">${filterTerm ? `Keine Lerneinheiten für "${escapeHtml(filterTerm)}" gefunden.` : "Für dieses Lehrwerk wurden noch keine separaten Lerneinheiten aufgeteilt."}</p>
        <button type="button" class="btn-primary" id="btn-open-full-book-fallback" style="margin: 0 auto; display: inline-flex; align-items: center; gap: 8px;">
          <span>${icon("Lesen")}</span>
          <span>Gesamtes Buch aufschlagen (${activeBookDetail.total_pages} Seiten)</span>
        </button>
      </div>
    `;
    const openBtn = document.getElementById("btn-open-full-book-fallback");
    if (openBtn) {
      openBtn.addEventListener("click", () => {
        openChapter({
          id: activeBookDetail.id,
          chapter_number: 0,
          title: activeBookDetail.title,
          start_page: 1,
          end_page: activeBookDetail.total_pages,
          page_count: activeBookDetail.total_pages,
          focus: activeBookDetail.summary || "Gesamtes Lehrwerk",
          file_url: `/api/v1/materials/${activeBookDetail.id}/file`,
          filename: `${activeBookDetail.title}.pdf`
        }, 1);
      });
    }
    return;
  }

  chapters.forEach((ch) => {
    const item = document.createElement("div");
    item.className = "book-toc-item";
    item.dataset.chapterId = ch.id;

    const isSingleFullBook = ch.id === activeBookDetail.id;
    const numDisplay = isSingleFullBook
      ? icon("Stern")
      : (ch.chapter_number === 0 ? "00" : String(ch.chapter_number).padStart(2, "0"));
    const unitLabel = isSingleFullBook
      ? "Gesamtbuch"
      : (ch.chapter_number === 0 ? "Titelei & Inhaltsverzeichnis" : `Einheit ${ch.chapter_number}`);

    let sectionsHtml = "";
    if (ch.sections && ch.sections.length > 0) {
      const hasSecMatch = Boolean(term && ch.sections.some(s => s.title.toLowerCase().includes(term) || String(s.book_page).includes(term)));
      sectionsHtml = `
        <details class="toc-subsections-accordion" ${hasSecMatch ? "open" : ""} onclick="event.stopPropagation()">
          <summary class="toc-summary">
            <span class="toc-summary-label">${icon("Inhaltsverzeichnis")} ${ch.sections.length} Unterthemen & Abschnitte</span>
            <span class="toc-chevron">${icon("Aufklappen")}</span>
          </summary>
          <div class="toc-subsections-grid">
            ${ch.sections.map(sec => `
              <button type="button" class="toc-sub-pill" data-target-page="${sec.relative_page}" title="Direkt aufschlagen: ${escapeHtml(sec.title)} (Buchseite ${sec.book_page})">
                <span class="toc-sub-title">${escapeHtml(sec.title)}</span>
                <span class="toc-sub-page">S. ${sec.book_page}</span>
              </button>
            `).join("")}
          </div>
        </details>
      `;
    }

    item.innerHTML = `
      <div class="toc-num-badge" title="${unitLabel}">
        ${numDisplay}
      </div>
      <div class="toc-item-main">
        <div class="toc-title-row">
          <div class="toc-item-title">${escapeHtml(ch.title)}</div>
        </div>
        <div class="toc-meta-row">
          <span class="toc-badge-pages">${icon("Dokumente")} S. ${ch.start_page}–${ch.end_page} (${ch.page_count} S.)</span>
          ${ch.topic_name ? `<span class="toc-badge-topic">${icon("Thema")} ${escapeHtml(ch.topic_name)}</span>` : ""}
          ${isSingleFullBook ? `<span class="toc-badge-topic">${icon("Stern")} Vollständige Ausgabe</span>` : ""}
        </div>
        ${sectionsHtml}
      </div>
      <div class="toc-item-action">
        <button type="button" class="btn-toc-open">
          <span>${isSingleFullBook ? "Gesamtbuch öffnen" : "Aufschlagen"}</span>
          <span>${icon("Pfeil rechts")}</span>
        </button>
      </div>
    `;

    // Klicken auf die Zeile öffnet das Kapitel ab Seite 1
    item.addEventListener("click", () => openChapter(ch, 1));

    // Klicken auf einzelne Unterseiten springt direkt zu dieser Seite
    item.querySelectorAll(".toc-sub-pill").forEach(pill => {
      pill.addEventListener("click", (e) => {
        e.stopPropagation();
        const p = parseInt(pill.dataset.targetPage, 10) || 1;
        openChapter(ch, p);
      });
    });

    container.appendChild(item);
  });
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
  window.scrollTo({ top: 0, behavior: "smooth" });
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
    catalogFilter.addEventListener("input", (e) => {
      renderBookCatalog(e.target.value);
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

