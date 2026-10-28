// Render Dashboard Cards (klickbar zur Fach-Detailseite mit Vektor-Icons)
function renderDashboardSubjects(subjects, topicsMap) {
  cachedSubjects = subjects;
  cachedTopicsMap = topicsMap;
  if (!dashboardSubjectsGrid) return;
  dashboardSubjectsGrid.innerHTML = "";

  subjects.forEach((s) => {
    const card = document.createElement("div");
    card.className = "subject-card subject-app-tile";
    const subColor = subjectColor(s.name);
    card.style.setProperty("--tile-color", subColor);
    card.dataset.subjectId = s.id;
    card.dataset.paintTile = s.id;  // bemalbar: Platz dashboard/tile/<Fach>
    card.dataset.paintKind = "quadrat";
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("title", `${s.name} öffnen`);

    card.innerHTML = `
      <div class="subject-tile-icon-wrap">
        ${subjectIcon(s.name, "subject-tile-icon")}
      </div>
      <div class="subject-tile-name">${escapeHtml(s.name)}</div>
    `;

    const handleOpen = () => {
      openSubjectDetail(s.id);
    };

    card.addEventListener("click", handleOpen);
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleOpen();
      }
    });

    dashboardSubjectsGrid.appendChild(card);
  });
  if (typeof applyPaintings === "function") applyPaintings();  // neue Kacheln bekommen ihre Bilder
}

let subjectDetailSourceTab = "dashboard";

function openSubjectDetail(subjectId, sourceTab = "dashboard") {
  subjectDetailSourceTab = sourceTab;
  currentDetailSubjectId = subjectId;
  const s = cachedSubjects.find((sub) => sub.id === subjectId) || {
    id: subjectId,
    name: "Schulfach",
    min_grade: 7,
    max_grade: 7
  };
  window.currentDetailSubjectId = subjectId;
  window.currentSubject = s;
  window.cachedSubjects = cachedSubjects;
  window.openSubjectDetail = openSubjectDetail;

  const breadcrumb = document.getElementById("subject-detail-breadcrumb");
  const sourceName = sourceTab === "timetable" ? "Stundenplan" : "Übersicht";
  if (breadcrumb) breadcrumb.textContent = `${sourceName} / ${s.name}`;

  const btnBack = document.getElementById("btn-back-to-dashboard");
  if (btnBack) {
    btnBack.innerHTML = `<span>${icon("Pfeil links")}</span>`;
    btnBack.title = sourceTab === "timetable" ? "Zurück zum Stundenplan" : "Zurück zur Übersicht";
  }

  const heroCard = document.getElementById("subject-hero-card");
  if (heroCard) {
    const heroColor = subjectColor(s.name);
    heroCard.style.borderLeft = `6px solid ${heroColor}`;
    heroCard.style.boxShadow = `0 10px 32px rgba(0, 0, 0, 0.35), 0 0 24px ${heroColor}15`;
  }

  const iconEl = document.getElementById("subject-detail-icon");
  if (iconEl) {
    iconEl.innerHTML = subjectIcon(s.name, "subject-hero-icon-svg");
    iconEl.style.setProperty("--tile-color", subjectColor(s.name));
  }

  const nameEl = document.getElementById("subject-detail-name");
  if (nameEl) nameEl.textContent = s.name;

  const gradeEl = document.getElementById("subject-detail-grade");
  if (gradeEl) gradeEl.textContent = `Klasse ${s.min_grade}–${s.max_grade}`;

  const btnWb = document.getElementById("btn-subject-open-wb");
  if (btnWb) {
    btnWb.onclick = () => {
      switchToTab("whiteboard");
      const subSel = document.getElementById("wb-subject-select");
      if (subSel) {
        subSel.value = s.id;
        subSel.dispatchEvent(new Event("change"));
      }
    };
  }

  const btnExercise = document.getElementById("btn-subject-start-exercise");
  if (btnExercise) {
    btnExercise.dataset.subjectId = s.id;
    btnExercise.dataset.subjectName = s.name;
    // Übungen aus echten Aufgaben (Tab „Üben“); ohne Probebetrieb keine Karte
    btnExercise.style.display = window.practiceEnabled ? "" : "none";
    btnExercise.onclick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      window.startPracticeRound(s.id);  // Runde nur für dieses Fach
    };
  }

  const btnUpload = document.getElementById("btn-subject-upload-doc");
  if (btnUpload) {
    btnUpload.onclick = () => {
      openMaterialUploadModal(s.id);
    };
  }

  const handleKeyTrigger = (el) => {
    if (el) {
      el.onkeydown = (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          el.click();
        }
      };
    }
  };
  handleKeyTrigger(btnWb);
  handleKeyTrigger(btnExercise);
  handleKeyTrigger(btnUpload);

  const topics = cachedTopicsMap[s.id] || [];
  const topicsCount = document.getElementById("subject-topics-count");
  if (topicsCount) topicsCount.textContent = String(topics.length);

  const topicsContainer = document.getElementById("subject-detail-topics");
  if (topicsContainer) {
    if (topics.length === 0) {
      topicsContainer.innerHTML = `<span style="color: var(--text-muted); font-size: 0.85rem;">Keine spezifischen Themen für dieses Fach hinterlegt.</span>`;
    } else {
      topicsContainer.innerHTML = topics.map((t) => `
        <div class="subject-topic-chip">
          <span>${escapeHtml(t.name)}</span>
          ${t.rlp_level_code ? `<span class="topic-rlp-tag">RLP ${t.rlp_level_code}</span>` : ""}
        </div>
      `).join("");
    }
  }

  // Filter-Pills zurücksetzen
  activeSubjectKindFilter = "all";
  const pills = document.querySelectorAll("#subject-materials-filter-bar .filter-pill");
  pills.forEach((p) => {
    p.classList.toggle("active", p.dataset.kind === "all");
  });

  loadSubjectMaterials(subjectId);
  loadSubjectBoards(subjectId);

  // View aktivieren
  document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".nav-tab").forEach((b) => b.classList.remove("active"));
  const tabEl = document.getElementById("tab-subject-detail");
  if (tabEl) {
    tabEl.dataset.paint = `subject-detail/${subjectId}`;  // bemalbar, eigenes Bild je Fach
    tabEl.classList.add("active");
  }
  document.body.classList.remove("reader-zen-mode");
  applyTabViewModes("subject-detail");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// Tafeln eines Fachs auf der Fachseite: Vorschaubild, Name, zuletzt bearbeitet; erste Karte = neue Tafel
async function loadSubjectBoards(subjectId) {
  const grid = document.getElementById("subject-boards-grid");
  const count = document.getElementById("subject-boards-count");
  if (!grid) return;
  let boards = [];
  try {
    const res = await apiFetch(`/api/v1/boards?subject_id=${encodeURIComponent(subjectId)}`);
    if (res.ok) boards = await res.json();
  } catch (err) {
    console.warn("Tafeln des Fachs nicht geladen:", err);
  }
  if (count) count.textContent = String(boards.length);

  const btnNew = document.getElementById("btn-subject-new-board");
  if (btnNew) {
    btnNew.onclick = () => {
      if (typeof window.openNewBoardOnWhiteboard === "function") window.openNewBoardOnWhiteboard(subjectId);
    };
  }

  if (boards.length === 0) {
    grid.innerHTML = `<div class="uploads-filter-empty">Noch keine Tafeln in diesem Fach.</div>`;
    return;
  }

  grid.innerHTML = "";
  boards.forEach((b) => grid.appendChild(buildBoardRow(b)));
}

// Aufgeklappte Tafelzeilen (bleiben beim Neuladen der Fachseite offen)
const openBoardRows = new Set();

// Tafel als aufklappbare Zeile: zugeklappt Titel, Datum, Öffnen; aufgeklappt die Vorschau.
// Das Vorschaubild wird erst beim Aufklappen geladen.
function buildBoardRow(b) {
  const when = b.updated_at || b.created_at;
  const date = when ? new Date(/[zZ]|[+-]\d\d:\d\d$/.test(when) ? when : `${when}Z`) : null;
  const dateText = date ? date.toLocaleDateString("de-DE", { day: "numeric", month: "short" }) : "";
  const thumbUrl = b.has_thumbnail
    ? `/api/v1/boards/${encodeURIComponent(b.id)}/thumbnail?v=${encodeURIComponent(b.updated_at || "")}`
    : "";

  const row = document.createElement("div");
  row.className = "doc-row board-row";
  row.dataset.boardId = b.id;
  row.style.cssText = subjectStyle(b.subject_name);
  row.innerHTML = `
    <div class="doc-row-head" role="button" tabindex="0" aria-expanded="false" title="Vorschau ein- oder ausblenden">
      <span class="doc-row-chevron">${icon("Aufklappen")}</span>
      <span class="doc-row-kind">${icon("Tafel")}</span>
      <span class="doc-row-title"><span class="doc-row-name">${escapeHtml(b.title || "Tafel")}</span></span>
      <span class="doc-row-pages">${escapeHtml(dateText)}</span>
      <button type="button" class="btn-mat-action board-row-rename" title="Umbenennen" aria-label="Umbenennen">${icon("Schreibwerkzeuge")}</button>
      <button type="button" class="btn-mat-action board-row-open" title="Öffnen" aria-label="Öffnen">${icon("Tafel")}</button>
    </div>
    <div class="doc-row-body">
      ${thumbUrl
        ? `<button type="button" class="board-row-preview" title="Tafel öffnen"><img alt="Vorschau: ${escapeHtml(b.title || "Tafel")}"></button>`
        : `<p class="doc-row-summary">Für diese Tafel gibt es noch keine Vorschau.</p>`}
      <div class="doc-row-actions parent-only">
        <button type="button" class="btn-mat-action btn-mat-del board-row-delete" title="Tafel endgültig löschen">${icon("Papierkorb")} Löschen</button>
      </div>
    </div>
  `;

  const open = () => {
    if (typeof window.openBoardOnWhiteboard === "function") window.openBoardOnWhiteboard(b.id);
  };
  row.querySelector(".board-row-open").addEventListener("click", (e) => {
    e.stopPropagation();
    open();
  });
  row.querySelector(".board-row-rename").addEventListener("click", async (e) => {
    e.stopPropagation();
    if (typeof window.renameBoardFromList !== "function") return;
    await window.renameBoardFromList(b);
    loadSubjectBoards(b.subject_id);
  });
  row.querySelector(".board-row-delete").addEventListener("click", async () => {
    if (!confirm(`Tafel „${b.title || "Tafel"}“ endgültig löschen? Das lässt sich nicht rückgängig machen.`)) return;
    if (typeof window.deleteBoardFromList !== "function") return;
    await window.deleteBoardFromList(b);
    loadSubjectBoards(b.subject_id);
  });
  const preview = row.querySelector(".board-row-preview");
  if (preview) preview.addEventListener("click", open);
  const img = row.querySelector(".board-row-preview img");
  makeRowExpandable(row, row.querySelector(".doc-row-head"), openBoardRows, b.id, () => {
    if (img && !img.getAttribute("src")) img.src = thumbUrl;
  });
  return row;
}

async function loadSubjectMaterials(subjectId) {
  const grid = document.getElementById("subject-materials-grid");
  const countBadge = document.getElementById("subject-materials-count");
  if (!grid) return;

  grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 30px; color: var(--text-secondary);">Lade Materialien...</div>`;

  try {
    const res = await apiFetch(`/api/v1/materials?subject_id=${encodeURIComponent(subjectId)}`);
    if (res.ok) {
      currentSubjectMaterials = await res.json();
      if (countBadge) {
        const n = currentSubjectMaterials.filter((m) => !isChapterOfKnownBook(m)).length;
        countBadge.textContent = String(n);
      }
      renderSubjectMaterialsList(currentSubjectMaterials);
    } else {
      grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--danger);">Fehler beim Laden der Materialien.</div>`;
    }
  } catch (err) {
    console.error("Fehler beim Laden der Fach-Materialien:", err);
    grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--danger);">Netzwerkfehler.</div>`;
  }
}

// Kapitel eines bekannten Schulbuchs stehen nicht einzeln in der Liste, sondern im aufklappbaren Buch.
// Steht das Buch nicht auf dieser Fachseite, bleibt das Kapitel sichtbar (sonst wäre es unauffindbar).
function isChapterOfKnownBook(m) {
  return isBookChapter(m) && currentBooks.some((b) => b.id === m.parent_id);
}

function renderSubjectMaterialsList(materials) {
  const grid = document.getElementById("subject-materials-grid");
  if (!grid) return;
  grid.innerHTML = "";

  const filtered = materials.filter((m) => !isChapterOfKnownBook(m)).filter((m) => {
    if (activeSubjectKindFilter === "all") return true;
    if (activeSubjectKindFilter === "Arbeitsblatt") return m.kind === "Arbeitsblatt";
    if (activeSubjectKindFilter === "Mitschrift") return m.kind === "Mitschrift" || m.kind === "Hefterseite";
    if (activeSubjectKindFilter === "Buch") return (m.kind || "").includes("Buch");
    if (activeSubjectKindFilter === "Vokabelliste") return m.kind === "Vokabelliste";
    if (activeSubjectKindFilter === "Sonstiges") return m.kind === "Sonstiges";
    if (activeSubjectKindFilter === "Test") {
      const k = m.kind || "";
      return k.includes("Test") || k.includes("Klassenarbeit") || k.includes("Übung") || k.includes("Klausur");
    }
    return true;
  });

  if (filtered.length === 0) {
    const filterName = activeSubjectKindFilter === "all" ? "" : ` in der Kategorie „${activeSubjectKindFilter}“`;
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 48px 16px; background: rgba(var(--ink-rgb), 0.02); border: 1px dashed var(--border-color); border-radius: 16px; color: var(--text-secondary);">
        <span style="font-size: 2.4rem; display: block; margin-bottom: 8px;">${icon("Eingang")}</span>
        <div style="font-weight: 700; color: var(--text-primary); font-size: 1.1rem; margin-bottom: 6px;">Keine Dokumente${filterName}</div>
        <p style="font-size: 0.88rem; max-width: 440px; margin: 0 auto 16px;">
          Lade Arbeitsblätter, Mitschriften, Tests oder Schulbücher für dieses Fach hoch, um sie hier direkt zu öffnen und auf der Tafel zu bearbeiten.
        </p>
        <button class="btn-primary-sm" onclick="openMaterialUploadModal('${currentDetailSubjectId || ''}')">${icon("Plus")} Jetzt Dokument hochladen</button>
      </div>
    `;
    return;
  }

  const embeddedBooks = [];
  filtered.forEach((m) => {
    const book = currentBooks.find((b) => b.id === m.id);
    if (book) {
      grid.appendChild(buildEmbeddedBookNode(book));
      embeddedBooks.push(book.id);
      return;
    }
    const card = buildMaterialCard(m, () => {
      loadSubjectMaterials(currentDetailSubjectId);
      loadUploadsHistory();
    });
    grid.appendChild(card);
  });

  // Aufgeklappte Bücher brauchen ihre Kapitel
  const openBooks = embeddedBooks.filter((id) => booksOpenState.books.has(id));
  if (openBooks.length) ensureBookDetails(openBooks).then(rerenderBookTrees);
}

function setupSubjectDetailEvents() {
  const btnBack = document.getElementById("btn-back-to-dashboard");
  if (btnBack) {
    btnBack.addEventListener("click", () => {
      switchToTab(subjectDetailSourceTab || "dashboard");
    });
  }

  const btnToggleTopics = document.getElementById("btn-toggle-subject-topics");
  if (btnToggleTopics) {
    btnToggleTopics.addEventListener("click", () => {
      const chips = document.getElementById("subject-detail-topics");
      const arrow = document.getElementById("subject-topics-arrow");
      if (!chips) return;
      const isHidden = chips.style.display === "none";
      chips.style.display = isHidden ? "flex" : "none";
      if (arrow) arrow.style.transform = isHidden ? "rotate(180deg)" : "rotate(0deg)";
    });
  }

  const subjectFilterPills = document.querySelectorAll("#subject-materials-filter-bar .filter-pill");
  subjectFilterPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      subjectFilterPills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      activeSubjectKindFilter = pill.dataset.kind || "all";
      renderSubjectMaterialsList(currentSubjectMaterials);
    });
  });
}

