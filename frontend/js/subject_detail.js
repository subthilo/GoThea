// Render Dashboard Cards (klickbar zur Fach-Detailseite mit Vektor-Icons)
function renderDashboardSubjects(subjects, topicsMap) {
  cachedSubjects = subjects;
  cachedTopicsMap = topicsMap;
  if (!dashboardSubjectsGrid) return;
  dashboardSubjectsGrid.innerHTML = "";

  subjects.forEach((s) => {
    const card = document.createElement("div");
    card.className = "subject-card subject-app-tile";
    const subColor = s.color_code || "#2563eb";
    card.style.setProperty("--tile-color", subColor);
    card.dataset.subjectId = s.id;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("title", `${s.name} öffnen`);

    card.innerHTML = `
      <div class="subject-tile-icon-wrap" style="background: ${subColor}20; border-color: ${subColor}45;">
        <img src="${getSubjectIconUrl(s.name)}" class="subject-tile-svg" alt="${escapeHtml(s.name)}">
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
}

let subjectDetailSourceTab = "dashboard";

function openSubjectDetail(subjectId, sourceTab = "dashboard") {
  subjectDetailSourceTab = sourceTab;
  currentDetailSubjectId = subjectId;
  const s = cachedSubjects.find((sub) => sub.id === subjectId) || {
    id: subjectId,
    name: "Schulfach",
    color_code: "#6366f1",
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
    btnBack.innerHTML = `<span>${icon("Pfeil links")} Zurück ${sourceTab === "timetable" ? "zum Stundenplan" : "zur Übersicht"}</span>`;
  }

  const heroCard = document.getElementById("subject-hero-card");
  if (heroCard) {
    heroCard.style.borderLeft = `6px solid ${s.color_code}`;
    heroCard.style.boxShadow = `0 10px 32px rgba(0, 0, 0, 0.35), 0 0 24px ${s.color_code}15`;
  }

  const iconEl = document.getElementById("subject-detail-icon");
  if (iconEl) {
    iconEl.innerHTML = `<img src="${getSubjectIconUrl(s.name)}" class="subject-hero-svg" alt="${escapeHtml(s.name)}">`;
    iconEl.style.background = `${s.color_code}22`;
    iconEl.style.borderColor = `${s.color_code}44`;
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
    btnExercise.onclick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (typeof window.openClozeTrainer === "function") {
        window.openClozeTrainer({
          subjectId: s.id,
          subjectName: s.name,
          sourceMaterialTitle: null
        });
      }
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
  if (topicsCount) topicsCount.textContent = `${topics.length} Thema${topics.length === 1 ? "" : "n"}`;

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
  initSubjectScoresVisibility();
  loadSubjectScores(subjectId);

  // View aktivieren
  document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".nav-tab").forEach((b) => b.classList.remove("active"));
  const tabEl = document.getElementById("tab-subject-detail");
  if (tabEl) tabEl.classList.add("active");
  document.body.classList.remove("reader-zen-mode");
  applyTabViewModes("subject-detail");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function initSubjectScoresVisibility() {
  const btnToggle = document.getElementById("btn-toggle-subject-scores-visibility");
  const bodyEl = document.getElementById("subject-scores-body");
  const hiddenEl = document.getElementById("subject-scores-hidden-state");
  const iconEl = document.getElementById("btn-toggle-subject-scores-icon");
  const textEl = document.getElementById("btn-toggle-subject-scores-text");

  let isHidden = localStorage.getItem("gothea_hide_subject_scores") === "true";

  function applyVisibility(hidden) {
    if (bodyEl) bodyEl.style.display = hidden ? "none" : "block";
    if (hiddenEl) hiddenEl.style.display = hidden ? "block" : "none";
    if (iconEl) iconEl.innerHTML = icon(hidden ? "Anzeigen" : "Verbergen");
    if (textEl) textEl.textContent = hidden ? "Scores einblenden" : "Scores ausblenden";
  }

  applyVisibility(isHidden);

  if (btnToggle) {
    btnToggle.onclick = () => {
      isHidden = !isHidden;
      localStorage.setItem("gothea_hide_subject_scores", isHidden ? "true" : "false");
      applyVisibility(isHidden);
    };
  }
}

// Bei Abschluss einer Übung im Hintergrund Fach-Scores neu laden & Gamification aktualisieren
window.addEventListener("gothea:exercise-completed", (e) => {
  if (currentDetailSubjectId) {
    loadSubjectScores(currentDetailSubjectId);
  }
  loadGamificationOverview();
  fireCelebrationConfetti();
});

// Übungsmethode → Icon (das Emoji aus der API wird nicht angezeigt)
function methodIconName(methodKey) {
  const names = {
    math_problem: "Mathematik",
    math_example: "Schreibwerkzeuge",
    physics_diagram: "Physik",
    formula_derivation: "Geodreieck",
    text_question: "Lesen"
  };
  return names[methodKey] || "Übungen";
}

async function loadSubjectScores(subjectId) {
  const container = document.getElementById("subject-scores-methods-grid");
  const badgeEl = document.getElementById("subject-adaptive-level-badge");
  const hintTextEl = document.getElementById("subject-scores-adaptive-hint-text");
  if (!container) return;

  container.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 18px; color: var(--text-muted); font-size: 0.85rem;">Lade Trainingsstand...</div>`;

  try {
    const res = await apiFetch(`/api/v1/exercises/scores/${encodeURIComponent(subjectId)}`);
    if (!res.ok) {
      container.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); font-size: 0.85rem;">Keine Trainingsdaten verfügbar.</div>`;
      return;
    }
    const data = await res.json();

    if (badgeEl) {
      if (isParentActive) {
        badgeEl.innerHTML = iconText("Ziel", data.difficulty_label || "Stufe 2 (Mittel)");
        badgeEl.className = `badge-adaptive-level level-${data.difficulty_level_code || 2}`;
      } else {
        const badgeTitle = data.positive_summary?.badge || "Gymnasial-Profi";
        badgeEl.innerHTML = `${iconText("Ziel", badgeTitle)} (${data.subject_stars || 0} ${icon("Stern")})`;
        badgeEl.className = `badge-adaptive-level level-2`;
      }
    }

    if (hintTextEl) {
      if (isParentActive) {
        if (data.difficulty_level_code === 1) {
          hintTextEl.textContent = "Sanfter Aufbau-Modus aktiv: Luna wählt leichtere Aufgaben, damit Thea die Grundlagen festigt und fast alles richtig hat.";
        } else if (data.difficulty_level_code === 3) {
          hintTextEl.textContent = "Spitzen-Modus aktiv: Thea löst Übungen mit Bravour! Luna stellt anspruchsvolle Vertiefungsaufgaben bereit.";
        } else {
          hintTextEl.textContent = "Ausgewogenes Gymnasial-Niveau: Luna passt den Schwierigkeitsgrad nach jeder Übung an Theas Fortschritt an.";
        }
      } else {
        hintTextEl.textContent = data.positive_summary?.encouragement || "Toller Lernfortschritt! Mit jeder Übung sammelst du wertvolle Wissens-Sterne und XP.";
      }
    }

    const methods = data.methods || {};
    const methodKeys = Object.keys(methods);

    if (methodKeys.length === 0) {
      container.innerHTML = `
        <div class="subject-score-empty" style="grid-column: 1 / -1; text-align: center; padding: 24px; color: var(--text-muted);">
          <span>Noch keine Übungen für dieses Fach absolviert. Starte oben eine Lückentext-Übung!</span>
        </div>
      `;
      return;
    }

    container.innerHTML = methodKeys.map((k) => {
      const m = methods[k];
      const hasData = m.completed_count > 0;
      const scorePct = hasData ? Math.round(m.average_score) : 0;
      const levelCode = m.difficulty_level_code || 2;

      if (!isParentActive) {
        // THEA-MODUS: Positives Gamified Scoring, niemals Fehlerprozente oder rote Warnfarben
        const starsCount = hasData ? Math.min(3, Math.max(1, Math.round((scorePct / 100) * 3))) : 0;
        const starsDisplay = hasData ? icon("Stern").repeat(starsCount) : "Noch keine Sterne";
        return `
          <div class="method-score-card">
            <div class="method-score-header">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="method-score-icon">${icon(methodIconName(k))}</span>
                <strong class="method-score-name">${escapeHtml(m.name)}</strong>
              </div>
              <span class="method-difficulty-pill" style="background: rgba(250, 204, 21, 0.15); color: #facc15; border-color: rgba(250, 204, 21, 0.35);">
                ${hasData ? starsDisplay : `Bereit zum Üben ${icon("Pflanze")}`}
              </span>
            </div>

            <div class="method-score-metrics">
              <div class="method-score-main">
                <span class="method-score-percent" style="color: #facc15;">${hasData ? `+${m.completed_count * 10} XP` : "–"}</span>
                <span class="method-score-sublabel">${hasData ? "Punkte gesammelt" : "Neu"}</span>
              </div>
              <div class="method-score-details">
                <div><strong>${m.completed_count}</strong> Übung${m.completed_count === 1 ? "" : "en"} gemeistert</div>
                <div>${hasData ? `Toller Einsatz! Weiter so ${icon("Daumen hoch")}` : "Starte deine erste Runde!"}</div>
              </div>
            </div>

            <div class="method-score-bar-wrap">
              <div class="method-score-bar bar-high" style="width: ${hasData ? Math.max(40, scorePct) : 0}%; background: linear-gradient(90deg, #10b981, #facc15);"></div>
            </div>
          </div>
        `;
      }

      // ELTERN-MODUS: Analytische Detailübersicht mit Quoten
      return `
        <div class="method-score-card">
          <div class="method-score-header">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="method-score-icon">${icon(methodIconName(k))}</span>
              <strong class="method-score-name">${escapeHtml(m.name)}</strong>
            </div>
            <span class="method-difficulty-pill level-${levelCode}">
              ${escapeHtml(m.difficulty_label)}
            </span>
          </div>

          <div class="method-score-metrics">
            <div class="method-score-main">
              <span class="method-score-percent">${hasData ? `${scorePct}%` : "–"}</span>
              <span class="method-score-sublabel">${hasData ? "Erfolgsquote" : "Noch nicht geübt"}</span>
            </div>
            <div class="method-score-details">
              <div><strong>${m.completed_count}</strong> Übung${m.completed_count === 1 ? "" : "en"} absolviert</div>
              ${m.recent_score !== null && m.recent_score !== undefined ? `<div>Zuletzt: <strong>${Math.round(m.recent_score)}%</strong></div>` : `<div>Noch keine Daten</div>`}
            </div>
          </div>

          <div class="method-score-bar-wrap">
            <div class="method-score-bar ${scorePct >= 80 ? "bar-high" : (scorePct >= 60 ? "bar-mid" : "bar-low")}" style="width: ${hasData ? scorePct : 0}%;"></div>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.warn("Fehler beim Laden der Fach-Scores:", err);
    container.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); font-size: 0.85rem;">Trainingsstand konnte nicht geladen werden.</div>`;
  }
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
  if (count) count.textContent = `${boards.length} ${boards.length === 1 ? "Tafel" : "Tafeln"}`;

  const newCard = `
    <button type="button" class="subject-board-card subject-board-new" data-new-board="1">
      <span class="subject-board-thumb subject-board-thumb-new">+</span>
      <span class="subject-board-title">Neue Tafel</span>
    </button>`;
  grid.innerHTML = newCard + boards.map((b) => {
    const when = b.updated_at || b.created_at;
    const date = when ? new Date(/[zZ]|[+-]\d\d:\d\d$/.test(when) ? when : `${when}Z`) : null;
    const dateText = date ? date.toLocaleDateString("de-DE", { day: "numeric", month: "short" }) : "";
    const thumb = b.has_thumbnail
      ? `<img class="subject-board-thumb" src="/api/v1/boards/${encodeURIComponent(b.id)}/thumbnail?v=${encodeURIComponent(b.updated_at || "")}" alt="">`
      : `<span class="subject-board-thumb"></span>`;
    return `
      <button type="button" class="subject-board-card" data-board-id="${escapeHtml(b.id)}">
        ${thumb}
        <span class="subject-board-title">${escapeHtml(b.title || "Tafel")}</span>
        <span class="subject-board-meta">${escapeHtml(dateText)}</span>
      </button>`;
  }).join("");

  grid.querySelectorAll(".subject-board-card").forEach((card) => {
    card.addEventListener("click", () => {
      if (card.dataset.newBoard && typeof window.openNewBoardOnWhiteboard === "function") {
        window.openNewBoardOnWhiteboard(subjectId);
      } else if (card.dataset.boardId && typeof window.openBoardOnWhiteboard === "function") {
        window.openBoardOnWhiteboard(card.dataset.boardId);
      }
    });
  });
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
        countBadge.textContent = `${currentSubjectMaterials.length} Dokument${currentSubjectMaterials.length === 1 ? "" : "e"}`;
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

function renderSubjectMaterialsList(materials) {
  const grid = document.getElementById("subject-materials-grid");
  if (!grid) return;
  grid.innerHTML = "";

  const filtered = materials.filter((m) => {
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
      <div style="grid-column: 1 / -1; text-align: center; padding: 48px 16px; background: rgba(255, 255, 255, 0.02); border: 1px dashed var(--border-color); border-radius: 16px; color: var(--text-secondary);">
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

  filtered.forEach((m) => {
    const card = buildMaterialCard(m, () => {
      loadSubjectMaterials(currentDetailSubjectId);
      loadUploadsHistory();
    });
    grid.appendChild(card);
  });
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

