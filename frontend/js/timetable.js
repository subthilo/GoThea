// ==========================================================================
// Timetable Import Subsystem
// ==========================================================================

const btnOpenTimetableModal = document.getElementById("btn-open-timetable-modal");
const timetableFileInput = document.getElementById("timetable-file-input");
const modalTimetableResult = document.getElementById("modal-timetable-result");
const btnCloseTimetableModal = document.getElementById("btn-close-timetable-modal");
const btnTtConfirmClose = document.getElementById("btn-tt-confirm-close");
const btnTtErrorClose = document.getElementById("btn-tt-error-close");

const ttLoadingState = document.getElementById("tt-loading-state");
const ttResultState = document.getElementById("tt-result-state");
const ttErrorState = document.getElementById("tt-error-state");
const ttResultStatusTitle = document.getElementById("tt-result-status-title");
const ttResultDocName = document.getElementById("tt-result-doc-name");
const ttAddedSubjectsList = document.getElementById("tt-added-subjects-list");
const ttAllSubjectsList = document.getElementById("tt-all-subjects-list");
const ttErrorTitle = document.getElementById("tt-error-title");
const ttErrorDetail = document.getElementById("tt-error-detail");

function openTimetableModal() {
  if (timetableFileInput) timetableFileInput.click();
}

function closeTimetableModal() {
  if (modalTimetableResult) modalTimetableResult.style.display = "none";
}

if (btnOpenTimetableModal) {
  btnOpenTimetableModal.addEventListener("click", openTimetableModal);
}
if (btnCloseTimetableModal) {
  btnCloseTimetableModal.addEventListener("click", closeTimetableModal);
}
if (btnTtConfirmClose) {
  btnTtConfirmClose.addEventListener("click", closeTimetableModal);
}
if (btnTtErrorClose) {
  btnTtErrorClose.addEventListener("click", closeTimetableModal);
}
if (modalTimetableResult) {
  modalTimetableResult.addEventListener("click", (e) => {
    if (e.target === modalTimetableResult && (!ttLoadingState || ttLoadingState.style.display !== "block")) {
      closeTimetableModal();
    }
  });
}

if (timetableFileInput) {
  timetableFileInput.addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    if (modalTimetableResult) {
      modalTimetableResult.style.display = "flex";
      if (ttLoadingState) ttLoadingState.style.display = "block";
      if (ttResultState) ttResultState.style.display = "none";
      if (ttErrorState) ttErrorState.style.display = "none";
    }

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await apiFetch("/api/v1/taxonomy/import-timetable", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Serverfehler HTTP ${res.status}`);
      }

      const data = await res.json();

      if (ttLoadingState) ttLoadingState.style.display = "none";
      if (ttErrorState) ttErrorState.style.display = "none";
      if (ttResultState) ttResultState.style.display = "block";

      const newlyAddedCount = (data.created_subjects || []).length;
      if (ttResultStatusTitle) {
        if (!data.slots_imported) {
          ttResultStatusTitle.innerHTML = iconText("Warnung", "Wochenraster nicht erkannt – Stundenplan unverändert");
        } else if (newlyAddedCount > 0) {
          ttResultStatusTitle.innerHTML = iconText("Feier", `${data.slots_imported} Stunden übernommen, ${newlyAddedCount} neue(s) Fach/Fächer angelegt!`);
        } else {
          ttResultStatusTitle.innerHTML = iconText("Erledigt", `Stundenplan übernommen: ${data.slots_imported} Stunden`);
        }
      }

      const matTitle = (data.material && data.material.title) || data.material_title || data.filename || "";
      if (ttResultDocName && matTitle) {
        let docText = `Dokument „${matTitle}“ als Stundenplan einsortiert.`;
        const grid = data.timetable_grid || {};
        if (grid.wochentyp || grid.hat_wechselwochen) {
          const wochenLabel = grid.wochentyp || "A/B-Wechselwochen";
          docText += ` (${wochenLabel} – Fächer beider Wochen übernommen)`;
        }
        if (grid.wechsel_details) {
          docText += `<div style="margin-top: 6px; font-size: 0.8rem; color: var(--accent-light);">${icon("Aktualisieren")} ${escapeHtml(grid.wechsel_details)}</div>`;
        }
        ttResultDocName.innerHTML = docText;
      }

      // Render added subjects
      if (ttAddedSubjectsList) {
        ttAddedSubjectsList.innerHTML = "";
        if (data.created_subjects && data.created_subjects.length > 0) {
          data.created_subjects.forEach((s) => {
            const pill = document.createElement("span");
            pill.className = "mat-card-badge";
            pill.style.background = "rgba(16, 185, 129, 0.2)";
            pill.style.color = "#10b981";
            pill.style.border = "1px solid rgba(16, 185, 129, 0.4)";
            pill.style.padding = "4px 10px";
            pill.style.fontSize = "0.85rem";
            pill.innerHTML = `${icon("Luna")} ${subjectLabel(s.name, "")}`;
            ttAddedSubjectsList.appendChild(pill);
          });
        } else {
          ttAddedSubjectsList.innerHTML = `<span style="font-size: 0.85rem; color: var(--text-secondary); font-style: italic;">Alle erkannten Schulfächer existierten bereits in deiner Fächerliste.</span>`;
        }
      }

      // Render all detected subjects
      if (ttAllSubjectsList) {
        ttAllSubjectsList.innerHTML = "";
        // Kombiniere neu angelegte und bereits existierende Fächer (enthalten vollständige Subject-Objekte mit icon & name)
        const allRecognized = [...(data.created_subjects || []), ...(data.existing_subjects || [])];
        const listToDisplay = allRecognized.length > 0 ? allRecognized : (data.detected_subjects || []);

        if (listToDisplay.length > 0) {
          listToDisplay.forEach((s) => {
            const pill = document.createElement("span");
            pill.className = "mat-card-badge";
            pill.style.background = "rgba(99, 102, 241, 0.15)";
            pill.style.color = "var(--accent-light)";
            pill.style.padding = "4px 10px";
            pill.style.fontSize = "0.85rem";
            if (typeof s === "object" && s !== null) {
              pill.innerHTML = subjectLabel(s.name, "");
            } else {
              const matched = allRecognized.find((sub) => sub.name.toLowerCase() === String(s).toLowerCase());
              pill.innerHTML = subjectLabel(matched ? matched.name : String(s), "");
            }
            ttAllSubjectsList.appendChild(pill);
          });
        } else {
          ttAllSubjectsList.innerHTML = `<span style="font-size: 0.85rem; color: var(--text-secondary); font-style: italic;">Keine Fächerkürzel erkannt.</span>`;
        }
      }

      // Refresh taxonomy, materials and timetable across the whole app
      await loadTaxonomy();
      await loadMaterials();
      await loadTimetable();
      await loadTodayDashboardWidget();

    } catch (err) {
      console.error("Fehler beim Import des Stundenplans:", err);
      if (ttLoadingState) ttLoadingState.style.display = "none";
      if (ttResultState) ttResultState.style.display = "none";
      if (ttErrorState) ttErrorState.style.display = "block";
      if (ttErrorTitle) ttErrorTitle.textContent = "Import fehlgeschlagen";
      if (ttErrorDetail) ttErrorDetail.textContent = err.message || "Unbekannter Fehler bei der Übertragung.";
    } finally {
      timetableFileInput.value = "";
    }
  });
}

// ==============================================================================
// STUNDENPLAN-WIDGET & VOLLBILD-VERWALTUNG
// ==============================================================================

let currentTimetableWeek = "A";
let currentTimetableData = null;

async function loadTimetable(forcedWeek = null) {
  try {
    const weekParam = forcedWeek || currentTimetableWeek;
    const res = await apiFetch(`/api/v1/timetable?week_type=${weekParam}`);
    if (!res.ok) throw new Error("Fehler beim Laden des Stundenplans.");
    currentTimetableData = await res.json();
    currentTimetableWeek = currentTimetableData.current_week_type || "A";

    // Header aktualisieren
    const subtitleEl = document.getElementById("tt-view-subtitle");
    if (subtitleEl) {
      subtitleEl.textContent = currentTimetableData.class_name || "Klasse 7D";
      subtitleEl.title = `${currentTimetableData.school_name || ""} • Schuljahr ${currentTimetableData.school_year || ""}`.trim();
    }

    // A/B Buttons Status setzen
    const btnA = document.getElementById("btn-tt-week-a");
    const btnB = document.getElementById("btn-tt-week-b");
    const autoWeekTag = document.getElementById("tt-auto-week-tag");
    if (btnA && btnB) {
      if (currentTimetableWeek === "A") {
        btnA.classList.add("active");
        btnB.classList.remove("active");
      } else {
        btnB.classList.add("active");
        btnA.classList.remove("active");
      }
    }
    if (autoWeekTag) {
      autoWeekTag.textContent = `Aktiv: ${currentTimetableWeek}-Woche`;
    }

    // Differenzen Text
    const diffEl = document.getElementById("tt-differences-text");
    if (diffEl && currentTimetableData.week_differences && currentTimetableData.week_differences.length > 0) {
      diffEl.textContent = currentTimetableData.week_differences.join(" • ");
    }

    renderTimetableGrid();
  } catch (err) {
    console.error("Fehler beim Laden des Stundenplans:", err);
  }
}

function renderTimetableGrid() {
  const gridEl = document.getElementById("timetable-full-grid");
  if (!gridEl || !currentTimetableData) return;

  gridEl.innerHTML = "";

  const weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"];
  const jsDay = new Date().getDay(); // 0 Sonntag, 1 Montag ... 5 Freitag
  const todayName = (jsDay >= 1 && jsDay <= 5) ? weekdays[jsDay - 1] : "Montag";

  // 1. Header-Zeile: Zeit + 5 Wochentage
  const timeHeader = document.createElement("div");
  timeHeader.className = "tt-grid-header tt-corner-header";
  timeHeader.innerHTML = "";
  gridEl.appendChild(timeHeader);

  weekdays.forEach((day) => {
    const dayHeader = document.createElement("div");
    const isToday = (day === todayName);
    dayHeader.className = `tt-grid-header ${isToday ? "today" : ""}`;
    dayHeader.innerHTML = `
      <span>${day}</span>
    `;
    gridEl.appendChild(dayHeader);
  });

  // 2. Zeilen für jede Unterrichtsstunde (1 bis 9)
  const periods = currentTimetableData.periods || [];
  const slots = currentTimetableData.slots || [];

  if (periods.length > 0) {
    gridEl.style.gridTemplateRows = `minmax(20px, 2.8vh) repeat(${periods.length}, minmax(0, 1fr))`;
  }

  periods.forEach((period) => {
    // A) Zeit-Zelle links
    const timeCell = document.createElement("div");
    timeCell.className = "tt-time-cell";
    const periodNumStr = (period.label || String(period.period)).replace(/\s*Std\.?/i, "").trim();
    timeCell.innerHTML = `
      <span class="tt-period-num">${escapeHtml(periodNumStr)}</span>
      <span class="tt-period-time">${escapeHtml(period.start_time || "")}</span>
    `;
    gridEl.appendChild(timeCell);

    // B) 5 Tageszellen
    weekdays.forEach((day) => {
      const isToday = (day === todayName);
      const slotCell = document.createElement("div");
      slotCell.className = `tt-slot-cell ${isToday ? "today-col" : ""}`;

      // Passenden Slot für diesen Tag & Stunde finden
      const matchingSlot = slots.find((s) => {
        return (
          s.day_of_week === day &&
          s.period === period.period &&
          (s.week_type === currentTimetableWeek || s.week_type === "both")
        );
      });

      if (matchingSlot) {
        if (matchingSlot.is_break) {
          const isLunch = (matchingSlot.subject_name || "").toLowerCase().includes("mittag") || (matchingSlot.subject_name || "").toLowerCase().includes("mensa");
          const breakIcon = isLunch ? "/static/Icons/Mittagspause.svg" : "/static/Icons/Pause.svg";
          slotCell.innerHTML = `
            <div class="tt-lesson-card tt-lesson-break" title="${escapeHtml(matchingSlot.subject_name || 'Pause')}">
              <img src="${breakIcon}" class="tt-break-svg" alt="">
            </div>
          `;
        } else {
          const card = document.createElement("div");
          card.className = "tt-lesson-card";
          card.style.cssText = subjectStyle(matchingSlot.subject_name);

          let roomStr = matchingSlot.room || "";


          card.innerHTML = `
            <div class="tt-lesson-top">
              ${subjectIcon(matchingSlot.subject_name, "tt-slot-icon")}
              <span class="tt-lesson-name">${escapeHtml(matchingSlot.subject_name)}</span>
            </div>
            <div class="tt-lesson-meta">
              <span class="tt-lesson-room">${escapeHtml(roomStr)}</span>
              <span class="tt-lesson-teacher">${escapeHtml(matchingSlot.teacher || "")}</span>
            </div>
          `;

          card.addEventListener("click", () => {
            if (matchingSlot.subject_id) {
              openSubjectDetail(matchingSlot.subject_id, "timetable");
            } else {
              openTimetableSlotDetailModal(matchingSlot, period);
            }
          });
          slotCell.appendChild(card);
        }
      } else {
        slotCell.innerHTML = `<div class="tt-cell-empty">—</div>`;
      }

      gridEl.appendChild(slotCell);
    });
  });
}

// Modal für Fach-Detail aus Stundenplan
let activeDetailSlot = null;

function openTimetableSlotDetailModal(slot, period) {
  activeDetailSlot = slot;
  const modal = document.getElementById("modal-tt-slot-detail");
  if (!modal) return;

  const iconEl = document.getElementById("tt-slot-modal-icon");
  const titleEl = document.getElementById("tt-slot-modal-title");
  const timeEl = document.getElementById("tt-slot-modal-time");
  const roomEl = document.getElementById("tt-slot-modal-room");
  const teacherEl = document.getElementById("tt-slot-modal-teacher");
  const weekEl = document.getElementById("tt-slot-modal-week");
  const noteRow = document.getElementById("tt-slot-modal-note-row");
  const noteEl = document.getElementById("tt-slot-modal-note");

  if (iconEl) {
    iconEl.innerHTML = subjectIcon(slot.subject_name, "tt-modal-subject-icon");
  }
  if (titleEl) titleEl.textContent = slot.subject_name;
  if (timeEl) {
    const pLabel = slot.period_label || (period ? period.label : `${slot.period}. Std`);
    const sTime = slot.start_time || (period ? period.start_time : "");
    const eTime = slot.end_time || (period ? period.end_time : "");
    timeEl.textContent = `${slot.day_of_week} • ${pLabel} • ${sTime} – ${eTime}`;
  }
  if (roomEl) {
    let r = slot.room || "–";
    if (r !== "–" && !r.toLowerCase().includes("halle") && !r.startsWith("R")) r = `Raum ${r}`;
    roomEl.textContent = r;
  }
  if (teacherEl) teacherEl.textContent = slot.teacher || "–";
  if (weekEl) {
    weekEl.textContent = slot.week_type === "both" ? "Wöchentlich (A- & B-Woche)" : `${slot.week_type}-Woche`;
  }
  if (noteRow && noteEl) {
    if (slot.note) {
      noteRow.style.display = "flex";
      noteEl.textContent = slot.note;
    } else {
      noteRow.style.display = "none";
    }
  }

  modal.style.display = "flex";
}

function closeTimetableSlotDetailModal() {
  const modal = document.getElementById("modal-tt-slot-detail");
  if (modal) modal.style.display = "none";
  activeDetailSlot = null;
}

// Dashboard Heutiger Stundenplan Widget
async function loadTodayDashboardWidget() {
  const container = document.getElementById("dash-tt-slots-row");
  if (!container) return;

  try {
    const res = await apiFetch("/api/v1/timetable/today");
    if (!res.ok) throw new Error("Fehler beim Laden des Tagesplans.");
    const data = await res.json();

    const titleEl = document.getElementById("dash-tt-day-title");
    const weekPill = document.getElementById("dash-tt-week-pill");

    if (titleEl) {
      titleEl.textContent = data.is_weekend
        ? "Montag"
        : data.day;
    }
    if (weekPill) {
      weekPill.textContent = data.active_week;
    }

    container.innerHTML = "";
    const lessons = (data.lessons || []).filter((l) => !l.is_break);

    if (lessons.length === 0) {
      container.innerHTML = `<div class="dash-tt-empty">Heute kein regulärer Unterricht eingetragen. ${icon("Feier")}</div>`;
      return;
    }

    lessons.forEach((l) => {
      const card = document.createElement("div");
      card.className = "dash-tt-slot-card";
      const subColor = subjectColor(l.subject_name);
      card.style.borderLeftColor = subColor;
      card.setAttribute("role", "button");
      card.setAttribute("tabindex", "0");
      card.setAttribute("title", `${l.subject_name} öffnen`);

      let roomStr = l.room || "";


      card.innerHTML = `
        <div class="dash-tt-slot-top">
          <div class="dash-tt-slot-icon-wrap" style="background: ${subColor}20; border-color: ${subColor}40;">
            ${subjectIcon(l.subject_name, "dash-tt-slot-icon")}
          </div>
          <span class="dash-tt-slot-time">${escapeHtml(String(l.period_label || l.period).replace(/\.?\s*Std\.?$/, ""))} · ${escapeHtml(l.start_time || "")}</span>
        </div>
        <div class="dash-tt-slot-subject">
          <span>${escapeHtml(l.subject_name)}</span>
        </div>
        <div class="dash-tt-slot-meta">
          ${roomStr ? `<span class="dash-tt-badge-room">${escapeHtml(roomStr)}</span>` : ""}
          ${l.teacher ? `<span class="dash-tt-badge-teacher">${escapeHtml(l.teacher)}</span>` : ""}
        </div>
      `;

      const handleSlotOpen = () => {
        if (l.subject_id) {
          openSubjectDetail(l.subject_id, "dashboard");
        } else {
          switchToTab("timetable");
        }
      };

      card.addEventListener("click", handleSlotOpen);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleSlotOpen();
        }
      });

      container.appendChild(card);
    });
  } catch (err) {
    console.error("Fehler beim Laden des Dashboard-Stundenplans:", err);
  }
}

async function viewMaterialById(matId) {
  try {
    const res = await apiFetch(`/api/v1/materials/${matId}`);
    if (res.ok) {
      const mat = await res.json();
      openDocumentViewerModal(mat);
    }
  } catch (err) {
    console.error("Fehler beim Laden des Dokuments:", err);
  }
}

// Event Listeners für Stundenplan
const btnTtWeekA = document.getElementById("btn-tt-week-a");
const btnTtWeekB = document.getElementById("btn-tt-week-b");
const btnTtViewScan = document.getElementById("btn-tt-view-scan");
const btnTtUploadNew = document.getElementById("btn-tt-upload-new");
const btnDashGotoTt = document.getElementById("btn-dash-goto-timetable");
const btnCloseTtSlotModal = document.getElementById("btn-close-tt-slot-modal");
const btnTtGotoMaterials = document.getElementById("btn-tt-goto-materials");
const btnTtGotoWb = document.getElementById("btn-tt-goto-whiteboard");

if (btnTtWeekA) {
  btnTtWeekA.addEventListener("click", () => {
    currentTimetableWeek = "A";
    btnTtWeekA.classList.add("active");
    if (btnTtWeekB) btnTtWeekB.classList.remove("active");
    renderTimetableGrid();
  });
}

if (btnTtWeekB) {
  btnTtWeekB.addEventListener("click", () => {
    currentTimetableWeek = "B";
    btnTtWeekB.classList.add("active");
    if (btnTtWeekA) btnTtWeekA.classList.remove("active");
    renderTimetableGrid();
  });
}

if (btnTtViewScan) {
  btnTtViewScan.addEventListener("click", () => {
    if (currentTimetableData && currentTimetableData.scan_material_id) {
      viewMaterialById(currentTimetableData.scan_material_id);
    } else {
      alert("Es wurde noch kein Original-Scan hochgeladen. Du kannst oben auf 'Plan aktualisieren' klicken.");
    }
  });
}

if (btnTtUploadNew) {
  btnTtUploadNew.addEventListener("click", () => {
    const fileIn = document.getElementById("timetable-file-input");
    if (fileIn) fileIn.click();
  });
}

if (btnDashGotoTt) {
  btnDashGotoTt.addEventListener("click", () => {
    switchToTab("timetable");
  });
}

if (btnCloseTtSlotModal) {
  btnCloseTtSlotModal.addEventListener("click", closeTimetableSlotDetailModal);
}

const modalTtSlotDetail = document.getElementById("modal-tt-slot-detail");
if (modalTtSlotDetail) {
  modalTtSlotDetail.addEventListener("click", (e) => {
    if (e.target === modalTtSlotDetail) closeTimetableSlotDetailModal();
  });
}

if (btnTtGotoMaterials) {
  btnTtGotoMaterials.addEventListener("click", () => {
    if (!activeDetailSlot) return;
    const sId = activeDetailSlot.subject_id;
    closeTimetableSlotDetailModal();
    if (sId) {
      openSubjectDetail(sId, "timetable");
    } else {
      switchToTab("dashboard");
    }
  });
}

if (btnTtGotoWb) {
  btnTtGotoWb.addEventListener("click", () => {
    if (!activeDetailSlot) return;
    const sId = activeDetailSlot.subject_id;
    closeTimetableSlotDetailModal();
    switchToTab("whiteboard");
    const wbSelect = document.getElementById("wb-subject-select");
    if (wbSelect && sId) {
      wbSelect.value = sId;
      wbSelect.dispatchEvent(new Event("change"));
    }
  });
}

