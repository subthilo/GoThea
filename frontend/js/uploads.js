// ==========================================================================
// Material Ingestion Subsystem (Milestone 4)
// ==========================================================================

let currentMaterials = [];
let currentUploadToken = null;
let currentUploadSignals = {}; // KI-Signale der Voranalyse (Lösungsseiten, bearbeitet, bewertet)
let currentPreselectedSubjectId = null;
let allTopicsCache = [];

const btnOpenMaterialModal = document.getElementById("btn-open-material-modal");
const modalMaterial = document.getElementById("modal-material");
const btnCloseMaterialModal = document.getElementById("btn-close-material-modal");

const matStepUpload = document.getElementById("mat-step-upload");
const matStepConfirm = document.getElementById("mat-step-confirm");
const matDropzone = document.getElementById("mat-dropzone");
const matFileInput = document.getElementById("mat-file-input");
const btnTriggerFile = document.getElementById("btn-trigger-file");
const matUploadSpinner = document.getElementById("mat-upload-spinner");

const matPreviewFilename = document.getElementById("mat-preview-filename");
const matPreviewMeta = document.getElementById("mat-preview-meta");
const matPreviewSnippet = document.getElementById("mat-preview-snippet");
const matPreviewIcon = document.getElementById("mat-preview-icon");

// Inbox / Samba Dropzone DOM
const inboxCard = document.getElementById("inbox-card");
const inboxEnvBadge = document.getElementById("inbox-env-badge");
const inboxSubtitle = document.getElementById("inbox-subtitle");
const inboxFileList = document.getElementById("inbox-file-list");
const inboxBadgeDot = document.getElementById("inbox-badge-dot");
const btnRefreshInbox = document.getElementById("btn-refresh-inbox");
const btnProcessInbox = document.getElementById("btn-process-inbox");
const inboxProcessStatus = document.getElementById("inbox-process-status");
const inboxStatusMsg = document.getElementById("inbox-status-msg");
const inboxSpinner = document.getElementById("inbox-spinner");
const navInboxBadge = document.getElementById("nav-inbox-badge");

const matConfirmSubject = document.getElementById("mat-confirm-subject");
const matConfirmTopic = document.getElementById("mat-confirm-topic");
const matConfirmTitle = document.getElementById("mat-confirm-title");
const matConfirmKind = document.getElementById("mat-confirm-kind");
const matConfirmSummary = document.getElementById("mat-confirm-summary");
const btnBackMaterialStep = document.getElementById("btn-back-material-step");
const btnSubmitMaterial = document.getElementById("btn-submit-material");

// Prüft den Inhalt der Samba Dropzone (GET /api/v1/inbox/status)
async function checkInboxStatus() {
  if (!inboxCard) return;
  try {
    if (!currentEnvInfo) {
      try {
        const envRes = await apiFetch("/api/v1/env");
        if (envRes.ok) currentEnvInfo = await envRes.json();
      } catch (e) {}
    }

    const res = await apiFetch("/api/v1/inbox/status");
    if (!res.ok) {
      console.error("Inbox Status HTTP Fehler:", res.status);
      if (inboxSubtitle) {
        inboxSubtitle.textContent = `Fehler beim Prüfen des Netzwerkordners (HTTP ${res.status}).`;
      }
      return;
    }
    const data = await res.json();

    const pending = data.pending_count || 0;
    const files = data.files || [];
    const shareName = (currentEnvInfo && currentEnvInfo.is_staging) ? "GoThea-Staging" : "GoThea-Prod";

    if (inboxEnvBadge) {
      inboxEnvBadge.textContent = `Finder: ${shareName}`;
    }

    // Navigation Tab Badge aktualisieren
    if (navInboxBadge) {
      if (pending > 0) {
        navInboxBadge.textContent = pending;
        navInboxBadge.style.display = "inline-block";
      } else {
        navInboxBadge.style.display = "none";
      }
    }

    // Card-Zustand anpassen
    if (pending > 0) {
      inboxCard.classList.add("has-pending");
      if (inboxBadgeDot) inboxBadgeDot.style.display = "block";
      if (inboxSubtitle) {
        inboxSubtitle.textContent = `${pending} neue${pending === 1 ? "s" : ""} Dokument${pending === 1 ? "" : "e"} im Ordner bereit zum Einsortieren.`;
      }
      if (btnProcessInbox) {
        btnProcessInbox.disabled = false;
        btnProcessInbox.innerHTML = `${icon("Eingang")} Jetzt einsortieren (${pending})`;
      }
    } else {
      inboxCard.classList.remove("has-pending");
      if (inboxBadgeDot) inboxBadgeDot.style.display = "none";
      if (inboxSubtitle) {
        inboxSubtitle.textContent = `Keine wartenden Dateien im Netzwerkordner.`;
      }
      if (btnProcessInbox) {
        btnProcessInbox.disabled = true;
        btnProcessInbox.innerHTML = `${icon("Eingang")} Jetzt einsortieren`;
      }
    }

    // Dateiliste rendern
    if (inboxFileList) {
      inboxFileList.innerHTML = "";
      if (files.length === 0) {
        inboxFileList.innerHTML = `
          <div class="inbox-empty-hint">
            <span>${icon("Luna")}</span>
            <span>Ziehe PDFs oder Bilder in deinen Mac-Finder Netzwerkordner <code>${shareName}</code>, um sie automatisch hier einzulesen.</span>
          </div>
        `;
      } else {
        files.forEach((f) => {
          const chip = document.createElement("div");
          chip.className = "inbox-file-chip";
          const isPdf = (f.mime_type || "").includes("pdf") || (f.filename || "").toLowerCase().endsWith(".pdf");
          const fileIcon = icon(isPdf ? "Dokumente" : "Bild");
          const sizeKb = Math.round((f.file_size || 0) / 1024);
          const sizeStr = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;

          chip.innerHTML = `
            <span>${fileIcon}</span>
            <span style="font-weight: 600;">${escapeHtml(f.filename)}</span>
            <span class="inbox-file-size">${sizeStr}</span>
          `;
          inboxFileList.appendChild(chip);
        });
      }
    }
  } catch (err) {
    console.error("Fehler beim Prüfen des Inbox-Status:", err);
  }
}

// Startet die Ingestion der Inbox (POST /api/v1/inbox/process)
async function processInbox() {
  if (!btnProcessInbox || btnProcessInbox.disabled) return;
  btnProcessInbox.disabled = true;

  if (inboxProcessStatus) {
    inboxProcessStatus.className = "inbox-process-status";
    inboxProcessStatus.style.display = "flex";
    if (inboxSpinner) inboxSpinner.style.display = "block";
    if (inboxStatusMsg) {
      inboxStatusMsg.textContent = "Dokumente werden analysiert, Text extrahiert & Fächern zugeordnet...";
    }
  }

  try {
    const res = await apiFetch("/api/v1/inbox/process", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      const pCount = data.processed_count || 0;
      const eCount = data.errors_count || 0;

      if (inboxSpinner) inboxSpinner.style.display = "none";

      if (pCount > 0 && eCount === 0) {
        inboxProcessStatus.className = "inbox-process-status success";
        if (inboxStatusMsg) {
          inboxStatusMsg.innerHTML = iconText("Erledigt", `Erfolgreich: ${pCount} Dokument${pCount === 1 ? "" : "e"} analysiert und einsortiert!`);
        }
      } else if (pCount > 0 && eCount > 0) {
        inboxProcessStatus.className = "inbox-process-status warning";
        if (inboxStatusMsg) {
          inboxStatusMsg.innerHTML = iconText("Warnung", `${pCount} Dokument${pCount === 1 ? "" : "e"} verarbeitet, ${eCount} fehlerhafte Datei(en) nach _errors/ verschoben.`);
        }
      } else if (pCount === 0 && eCount > 0) {
        inboxProcessStatus.className = "inbox-process-status warning";
        if (inboxStatusMsg) {
          inboxStatusMsg.innerHTML = iconText("Warnung", `Fehler bei ${eCount} Datei(en). Details in _errors/.`);
        }
      } else {
        inboxProcessStatus.className = "inbox-process-status";
        if (inboxStatusMsg) {
          inboxStatusMsg.textContent = "Keine neuen Dateien zur Verarbeitung gefunden.";
        }
      }

      await loadTaxonomy();
      await loadMaterials();
      await loadUploadsHistory();
      if (currentDetailSubjectId) await loadSubjectMaterials(currentDetailSubjectId);
      await checkInboxStatus();

      setTimeout(() => {
        if (inboxProcessStatus) inboxProcessStatus.style.display = "none";
      }, 6000);
    } else {
      const err = await res.json().catch(() => ({}));
      if (inboxSpinner) inboxSpinner.style.display = "none";
      inboxProcessStatus.className = "inbox-process-status warning";
      if (inboxStatusMsg) {
        inboxStatusMsg.innerHTML = iconText("Fehler", `Fehler bei der Verarbeitung: ${err.detail || "Serverfehler"}`);
      }
    }
  } catch (err) {
    console.error("Netzwerkfehler beim Verarbeiten des Posteingangs:", err);
    if (inboxSpinner) inboxSpinner.style.display = "none";
    inboxProcessStatus.className = "inbox-process-status warning";
    if (inboxStatusMsg) {
      inboxStatusMsg.innerHTML = iconText("Fehler", "Netzwerkfehler beim Verarbeiten.");
    }
  } finally {
    await checkInboxStatus();
  }
}

if (btnRefreshInbox) {
  btnRefreshInbox.addEventListener("click", async () => {
    const origHtml = btnRefreshInbox.innerHTML;
    btnRefreshInbox.disabled = true;
    btnRefreshInbox.innerHTML = `<span class="inbox-spin-icon">${icon("Aktualisieren")}</span> Prüfe...`;
    try {
      await checkInboxStatus();
      btnRefreshInbox.innerHTML = iconText("Haken", "Geprüft");
    } catch (e) {
      btnRefreshInbox.innerHTML = iconText("Warnung", "Fehler");
    } finally {
      setTimeout(() => {
        btnRefreshInbox.innerHTML = origHtml;
        btnRefreshInbox.disabled = false;
      }, 1000);
    }
  });
}

if (btnProcessInbox) {
  btnProcessInbox.addEventListener("click", () => {
    processInbox();
  });
}

function buildMaterialCard(m, onDeleted) {
  const card = document.createElement("div");
  card.className = "material-card";
  card.style.borderLeft = `4px solid ${subjectColor(m.subject_name)}`;

  const isPdf = (m.mime_type || "").includes("pdf");
  const kindIcon = documentIconName(m.kind);
  const docIcon = icon(kindIcon === "Dokumente" && !isPdf ? "Bild" : kindIcon);

  const sizeKb = Math.round((m.file_size || 0) / 1024);
  const sizeStr = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;

  card.innerHTML = `
    <div>
      <div class="mat-card-header">
        <div class="mat-card-title">${escapeHtml(m.title)}</div>
        <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
          ${m.dossier_title ? `<span class="mat-dossier-badge" title="Zugeordneter Hefter">${icon("Ordner")} ${escapeHtml(m.dossier_title)}</span>` : ""}
          <span class="mat-card-badge" style="background: rgba(99, 102, 241, 0.15); color: var(--accent-light); border: 1px solid rgba(99, 102, 241, 0.3);">
            ${escapeHtml(m.kind || "Dokument")}
          </span>
        </div>
      </div>
      <div class="mat-card-meta">
        <span style="color: ${subjectColor(m.subject_name)}; font-weight: 600;">
          ${subjectLabel(m.subject_name)}
        </span>
        ${m.topic_name ? `<span>• ${icon("Thema")} ${escapeHtml(m.topic_name)}</span>` : ""}
        <span>• ${docIcon} ${m.page_count} S. (${sizeStr})</span>
        ${m.start_page && m.end_page ? `<span>• S. ${m.start_page}–${m.end_page}</span>` : ""}
      </div>
      ${m.summary ? `<div class="mat-card-summary">“${escapeHtml(m.summary)}”</div>` : ""}
    </div>
    <div class="mat-card-actions">
      ${m.kind && m.kind.includes("Stundenplan") ? `
        <button class="btn-mat-action btn-mat-tt" style="background: rgba(99, 102, 241, 0.2); border-color: var(--accent); color: var(--accent-light); font-weight: 700;" title="Als interaktives Stundenplan-Widget öffnen">
          ${icon("Stundenplan")} Stundenplan
        </button>
      ` : ""}
      <button class="btn-mat-action btn-mat-view" title="${m.kind && m.kind.includes('Stundenplan') ? 'Original-Scan als Dokument ansehen' : 'Dokument im Popup ansehen'}">
        ${icon("Anzeigen")} ${m.kind && m.kind.includes('Stundenplan') ? 'Scan' : 'Öffnen'}
      </button>
      <button class="btn-mat-action btn-mat-reader" title="Im Dokument-Reader öffnen & mit Apple Pencil beschreiben">
        ${icon("Lesen")} Reader
      </button>
      <button class="btn-mat-action btn-mat-wb" title="Dieses Dokument auf der digitalen Tafel mit KI-Tutorin Luna üben">
        ${icon("Tafel")} Tafel
      </button>
      <button class="btn-mat-action btn-mat-cloze" title="Lückentext-Übung direkt aus diesem Dokument erstellen">
        ${icon("Übungen")} Üben
      </button>
      <button class="btn-mat-action btn-mat-edit parent-only" title="Dokument anpassen (Fach, Thema, Titel)">
        ${icon("Schreibwerkzeuge")} Ändern
      </button>
      ${(m.page_count > 1 || (m.mime_type || "").includes("pdf")) ? `
        <button class="btn-mat-action btn-mat-reorder parent-only" title="Seitenreihenfolge ändern & verwalten">
          ${icon("Seiten anzeigen")} Seiten
        </button>
      ` : ""}
      <button class="btn-mat-action btn-mat-del parent-only" data-id="${m.id}" title="Material löschen">
        ${icon("Papierkorb")}
      </button>
    </div>
  `;

  const ttBtn = card.querySelector(".btn-mat-tt");
  if (ttBtn) {
    ttBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      switchToTab("timetable");
    });
  }

  const wbBtn = card.querySelector(".btn-mat-wb");
  if (wbBtn) {
    wbBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (typeof window.openMaterialOnWhiteboard === "function") {
        window.openMaterialOnWhiteboard(m.id, m.subject_id);
      } else {
        switchToTab("whiteboard");
      }
    });
  }

  const clozeBtn = card.querySelector(".btn-mat-cloze");
  if (clozeBtn) {
    clozeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (typeof window.openClozeTrainer === "function") {
        const subName = (cachedSubjects.find(s => s.id === m.subject_id) || {}).name || "Schulfach";
        window.openClozeTrainer({
          subjectId: m.subject_id,
          subjectName: subName,
          materialId: m.id,
          sourceMaterialTitle: m.title
        });
      }
    });
  }

  const viewBtn = card.querySelector(".btn-mat-view");
  if (viewBtn) {
    viewBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openDocumentViewerModal(m);
    });
  }

  const readerBtn = card.querySelector(".btn-mat-reader");
  if (readerBtn) {
    readerBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openMaterialInReader(m);
    });
  }

  const editBtn = card.querySelector(".btn-mat-edit");
  if (editBtn) {
    editBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openEditMaterialModal(m);
    });
  }

  const reorderBtn = card.querySelector(".btn-mat-reorder");
  if (reorderBtn) {
    reorderBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openReorderPagesModal(m);
    });
  }

  const delBtn = card.querySelector(".btn-mat-del");
  if (delBtn) {
    delBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm(`Möchtest du das Material „${m.title}“ wirklich löschen?`)) return;
      try {
        const delRes = await apiFetch(`/api/v1/materials/${m.id}`, { method: "DELETE" });
        if (delRes.ok) {
          if (typeof onDeleted === "function") {
            onDeleted();
          } else {
            await loadMaterials();
            await loadUploadsHistory();
            if (currentDetailSubjectId) await loadSubjectMaterials(currentDetailSubjectId);
          }
        } else {
          alert("Fehler beim Löschen des Materials.");
        }
      } catch (err) {
        alert("Netzwerkfehler beim Löschen.");
      }
    });
  }

  return card;
}

async function loadMaterials() {
  try {
    const res = await apiFetch("/api/v1/materials");
    if (res.ok) {
      currentMaterials = await res.json();
      renderUploadsHistory(currentMaterials);
    }
  } catch (err) {
    console.error("Fehler beim Laden der Materialien:", err);
  }
}

async function loadUploadsHistory() {
  const historyList = document.getElementById("uploads-history-list");
  if (!historyList) return;
  try {
    const res = await apiFetch("/api/v1/materials");
    if (res.ok) {
      currentMaterials = await res.json();
      renderUploadsHistory(currentMaterials);
    }
  } catch (err) {
    console.error("Fehler beim Laden der Upload-Historie:", err);
  }
}

// Suche & Filter der Dokumentliste (bleiben beim Neuladen nach Ändern/Löschen erhalten)
const uploadsFilter = { term: "", subject: "all", showChapters: false };

function isBookChapter(m) {
  return (m.kind || "") === "Buchauszug";
}

function materialMatchesTerm(m, term) {
  if (!term) return true;
  return [m.title, m.subject_name, m.kind, m.topic_name, m.dossier_title, m.filename]
    .some((v) => v && String(v).toLowerCase().includes(term));
}

function renderUploadsHistory(materials) {
  const historyList = document.getElementById("uploads-history-list");
  const countBadge = document.getElementById("uploads-history-count");
  if (!historyList) return;
  historyList.innerHTML = "";

  if (materials.length === 0) {
    if (countBadge) countBadge.textContent = "0 Dokumente";
    renderUploadsSubjectPills([]);
    historyList.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 40px 16px; background: rgba(255, 255, 255, 0.02); border: 1px dashed var(--border-color); border-radius: 14px; color: var(--text-secondary);">
        <span style="font-size: 2.2rem; display: block; margin-bottom: 8px;">${icon("Eingang")}</span>
        <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">Noch keine Uploads vorhanden</div>
        <p style="font-size: 0.85rem; max-width: 440px; margin: 0 auto;">Ziehe Dateien in die Upload-Zone oben oder in deinen Finder-Netzwerkordner, um sie automatisch hier einzulesen.</p>
      </div>
    `;
    return;
  }

  // Stufe 1: Kapitel-Schalter und Suchbegriff → Grundlage für die Fach-Chips (mit Anzahl)
  const term = uploadsFilter.term.toLowerCase().trim();
  const base = materials.filter((m) => (uploadsFilter.showChapters || !isBookChapter(m)) && materialMatchesTerm(m, term));
  renderUploadsSubjectPills(base);
  // Stufe 2: Fach
  const shown = uploadsFilter.subject === "all" ? base : base.filter((m) => (m.subject_name || "") === uploadsFilter.subject);

  const listed = materials.filter((m) => uploadsFilter.showChapters || !isBookChapter(m)).length;
  if (countBadge) {
    countBadge.textContent = shown.length === listed
      ? `${listed} Dokument${listed === 1 ? "" : "e"}`
      : `${shown.length} von ${listed}`;
  }

  if (shown.length === 0) {
    historyList.innerHTML = `<div class="uploads-filter-empty">Keine Dokumente${term ? ` zu „${escapeHtml(uploadsFilter.term)}“` : ""}${uploadsFilter.subject !== "all" ? ` in ${escapeHtml(uploadsFilter.subject)}` : ""}.</div>`;
    return;
  }

  shown.forEach((m) => {
    const card = buildMaterialCard(m, async () => {
      await loadMaterials();
      await loadUploadsHistory();
      if (currentDetailSubjectId) await loadSubjectMaterials(currentDetailSubjectId);
    });
    historyList.appendChild(card);
  });
}

// Fach-Chips in Fachfarbe mit Anzahl; ein gewähltes Fach ohne Treffer bleibt sichtbar
function renderUploadsSubjectPills(materials) {
  const wrap = document.getElementById("uploads-subject-pills");
  if (!wrap) return;
  const counts = {};
  materials.forEach((m) => {
    const name = m.subject_name || "Ohne Fach";
    counts[name] = (counts[name] || 0) + 1;
  });
  if (uploadsFilter.subject !== "all" && !(uploadsFilter.subject in counts)) counts[uploadsFilter.subject] = 0;
  const names = Object.keys(counts).sort((a, b) => a.localeCompare(b, "de"));
  const pill = (value, label, count, style = "") => `
    <button type="button" class="filter-pill uploads-subject-pill ${uploadsFilter.subject === value ? "active" : ""}" data-subject="${escapeHtml(value)}" style="${style}">
      ${label} <span class="uploads-pill-count">${count}</span>
    </button>`;
  wrap.innerHTML = pill("all", "Alle Fächer", materials.length) +
    names.map((n) => pill(n, subjectLabel(n), counts[n], subjectStyle(n))).join("");
}

function setupUploadsPageEvents() {
  // Suche & Filter der Dokumentliste
  const filterInput = document.getElementById("uploads-filter-input");
  if (filterInput) {
    filterInput.addEventListener("input", () => {
      uploadsFilter.term = filterInput.value;
      renderUploadsHistory(currentMaterials);
    });
  }
  const chaptersToggle = document.getElementById("uploads-show-chapters");
  if (chaptersToggle) {
    chaptersToggle.addEventListener("change", () => {
      uploadsFilter.showChapters = chaptersToggle.checked;
      renderUploadsHistory(currentMaterials);
    });
  }
  const subjectPills = document.getElementById("uploads-subject-pills");
  if (subjectPills) {
    subjectPills.addEventListener("click", (e) => {
      const btn = e.target.closest(".uploads-subject-pill");
      if (!btn) return;
      const value = btn.dataset.subject;
      uploadsFilter.subject = uploadsFilter.subject === value ? "all" : value;
      renderUploadsHistory(currentMaterials);
    });
  }

  const dropzone = document.getElementById("page-upload-dropzone");
  const fileInput = document.getElementById("page-file-input");
  const btnTrigger = document.getElementById("btn-trigger-page-upload");

  if (btnTrigger && fileInput) {
    btnTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", (e) => {
      if (e.target !== btnTrigger) {
        fileInput.click();
      }
    });

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("drag-over");
    });

    dropzone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      dropzone.classList.remove("drag-over");
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("drag-over");
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        openMaterialUploadModal();
        handleFilesUpload(Array.from(e.dataTransfer.files));
      }
    });
  }

  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        const files = Array.from(e.target.files);
        openMaterialUploadModal();
        handleFilesUpload(files);
      }
    });
  }
}

function updateMaterialTopicOptions(subjectId, selectedTopicId = null) {
  if (!matConfirmTopic) return;
  matConfirmTopic.innerHTML = '<option value="">-- Kein spezifisches Thema --</option>';
  const subjectTopics = allTopicsCache.filter((t) => t.subject_id === subjectId);
  subjectTopics.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = `${t.name} (Stufe ${t.rlp_level_code || 'E'})`;
    if (selectedTopicId && t.id === selectedTopicId) {
      opt.selected = true;
    }
    matConfirmTopic.appendChild(opt);
  });
}

async function handleFilesUpload(files) {
  if (!files || files.length === 0) return;
  if (files.length === 1) {
    await handleSingleFileUpload(files[0]);
  } else {
    await handleBatchFileUpload(files);
  }
}

async function handleSingleFileUpload(file) {
  if (!file) return;

  if (matDropzone) matDropzone.style.display = "none";
  if (matUploadSpinner) matUploadSpinner.style.display = "block";
  const pBar = document.getElementById("mat-batch-progress-bar");
  if (pBar) pBar.style.display = "none";
  const pStat = document.getElementById("mat-batch-status");
  if (pStat) pStat.textContent = "";
  const spinnerText = document.getElementById("mat-spinner-text");
  if (spinnerText) spinnerText.textContent = "Analysiere Dokument & Schlagwörter...";

  const formData = new FormData();
  formData.append("file", file);
  if (currentPreselectedSubjectId) {
    formData.append("subject_id", currentPreselectedSubjectId);
  }

  try {
    const res = await apiFetch("/api/v1/materials/pre-analyze", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      alert(errData.detail || "Fehler bei der Analyse.");
      resetMaterialModal();
      return;
    }

    const data = await res.json();
    currentUploadToken = data.upload_token;
    currentUploadSignals = pickAnalysisSignals(data);

    matStepUpload.style.display = "none";
    matStepConfirm.style.display = "block";

    matPreviewFilename.textContent = data.filename;
    const sizeKb = Math.round(data.file_size / 1024);
    const sizeStr = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;
    matPreviewMeta.textContent = `${data.page_count} Seite${data.page_count === 1 ? "" : "n"} • ${sizeStr}`;
    matPreviewIcon.innerHTML = icon(data.mime_type.includes("pdf") ? "Dokumente" : "Bild");

    if (data.preview_snippet) {
      matPreviewSnippet.style.display = "block";
      matPreviewSnippet.textContent = `„${data.preview_snippet}“`;
    } else {
      matPreviewSnippet.style.display = "none";
    }

    matConfirmSubject.innerHTML = "";
    const activeSubId = currentPreselectedSubjectId || data.predicted_subject_id;
    currentSubjects.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.name;
      if (activeSubId && s.id === activeSubId) {
        opt.selected = true;
      }
      matConfirmSubject.appendChild(opt);
    });

    const fixedBadge = document.getElementById("mat-fixed-subject-badge");
    if (currentPreselectedSubjectId) {
      matConfirmSubject.disabled = true;
      if (fixedBadge) fixedBadge.style.display = "block";
    } else {
      matConfirmSubject.disabled = false;
      if (fixedBadge) fixedBadge.style.display = "none";
    }

    updateMaterialTopicOptions(activeSubId, data.predicted_topic_id);

    matConfirmTitle.value = data.predicted_title || "Lernmaterial";
    matConfirmKind.value = data.predicted_kind || "Arbeitsblatt";
    matConfirmSummary.value = "";
  } catch (err) {
    alert("Netzwerkfehler beim Upload.");
    resetMaterialModal();
  }
}

function pickAnalysisSignals(preData) {
  return {
    solution_pages: preData.solution_pages || [],
    worked_on_paper: preData.worked_on_paper ?? null,
    teacher_graded: preData.teacher_graded ?? null,
  };
}

async function handleBatchFileUpload(files) {
  if (!files || files.length === 0) return;

  if (matDropzone) matDropzone.style.display = "none";
  if (matUploadSpinner) matUploadSpinner.style.display = "block";

  const pBar = document.getElementById("mat-batch-progress-bar");
  const pFill = document.getElementById("mat-batch-progress-fill");
  const pStat = document.getElementById("mat-batch-status");
  const spinnerText = document.getElementById("mat-spinner-text");

  if (pBar) pBar.style.display = "block";

  const targetSub = currentPreselectedSubjectId
    ? currentSubjects.find((s) => s.id === currentPreselectedSubjectId)
    : null;

  let successCount = 0;
  const failures = [];
  const total = files.length;

  for (let i = 0; i < total; i++) {
    const file = files[i];
    const pct = Math.round((i / total) * 100);
    if (pFill) pFill.style.width = `${pct}%`;
    if (spinnerText) {
      spinnerText.textContent = targetSub
        ? `Verarbeite Dokumente für ${targetSub.name}...`
        : "Verarbeite Dokumente...";
    }
    if (pStat) {
      pStat.textContent = `Datei ${i + 1} von ${total}: ${file.name}`;
    }

    try {
      const formData = new FormData();
      formData.append("file", file);
      if (currentPreselectedSubjectId) {
        formData.append("subject_id", currentPreselectedSubjectId);
      }

      const preRes = await apiFetch("/api/v1/materials/pre-analyze", {
        method: "POST",
        body: formData
      });

      if (!preRes.ok) {
        const err = await preRes.json().catch(() => ({}));
        failures.push(`${file.name}: ${err.detail || `Voranalyse fehlgeschlagen (HTTP ${preRes.status})`}`);
        continue;
      }

      const preData = await preRes.json();
      const payload = {
        upload_token: preData.upload_token,
        subject_id: currentPreselectedSubjectId || preData.predicted_subject_id,
        topic_id: preData.predicted_topic_id || null,
        title: preData.predicted_title || file.name,
        kind: preData.predicted_kind || "Arbeitsblatt",
        summary: preData.preview_snippet || null,
        ...pickAnalysisSignals(preData)
      };

      const confRes = await apiFetch("/api/v1/materials/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (confRes.ok) {
        successCount++;
      } else {
        const err = await confRes.json().catch(() => ({}));
        failures.push(`${file.name}: ${err.detail || `Speichern fehlgeschlagen (HTTP ${confRes.status})`}`);
      }
    } catch (e) {
      failures.push(`${file.name}: ${e.message || "Netzwerkfehler"}`);
    }
  }

  if (pFill) pFill.style.width = "100%";
  if (spinnerText) {
    spinnerText.innerHTML = failures.length
      ? iconText("Warnung", `${successCount} von ${total} Dokumenten hochgeladen – ${failures.length} fehlgeschlagen`)
      : iconText("Erledigt", `${successCount} von ${total} Dokumenten erfolgreich hochgeladen!`);
  }
  if (pStat) {
    if (failures.length) {
      // Fehler sichtbar lassen, nicht automatisch schließen
      pStat.innerHTML = failures.map((f) => `<div>${iconText("Fehler", f)}</div>`).join("");
      await loadMaterials();
      await loadUploadsHistory();
      if (currentDetailSubjectId) await loadSubjectMaterials(currentDetailSubjectId);
      return;
    }
    pStat.textContent = targetSub
      ? `Alle Dokumente wurden zu ${targetSub.name} hinzugefügt.`
      : "Alle Dokumente wurden erfolgreich verarbeitet.";
  }

  setTimeout(async () => {
    if (modalMaterial) modalMaterial.style.display = "none";
    resetMaterialModal();
    await loadMaterials();
    await loadUploadsHistory();
    if (currentDetailSubjectId) await loadSubjectMaterials(currentDetailSubjectId);
  }, 1200);
}

function resetMaterialModal() {
  currentUploadToken = null;
  currentUploadSignals = {};
  currentPreselectedSubjectId = null;
  if (matFileInput) matFileInput.value = "";
  if (matDropzone) matDropzone.style.display = "flex";
  if (matUploadSpinner) matUploadSpinner.style.display = "none";
  if (matStepUpload) matStepUpload.style.display = "block";
  if (matStepConfirm) matStepConfirm.style.display = "none";

  const pBar = document.getElementById("mat-batch-progress-bar");
  if (pBar) pBar.style.display = "none";
  const pFill = document.getElementById("mat-batch-progress-fill");
  if (pFill) pFill.style.width = "0%";
  const pStat = document.getElementById("mat-batch-status");
  if (pStat) pStat.textContent = "";
  const spinnerText = document.getElementById("mat-spinner-text");
  if (spinnerText) spinnerText.textContent = "Analysiere Dokument & Schlagwörter...";

  const fixedBadge = document.getElementById("mat-fixed-subject-badge");
  if (fixedBadge) fixedBadge.style.display = "none";
  if (matConfirmSubject) matConfirmSubject.disabled = false;
}

function openMaterialUploadModal(preselectedSubjectId = null) {
  resetMaterialModal();
  currentPreselectedSubjectId = preselectedSubjectId;

  const titleEl = document.getElementById("modal-material-title");
  const subEl = document.getElementById("mat-modal-subtitle");
  const dzText = document.getElementById("mat-dropzone-text");
  const dzSub = document.getElementById("mat-dropzone-sub");
  const targetSub = currentPreselectedSubjectId
    ? currentSubjects.find((s) => s.id === currentPreselectedSubjectId)
    : null;

  if (targetSub) {
    if (titleEl) titleEl.innerHTML = iconText("Dokumente", `Neues Dokument für ${targetSub.name} hochladen`);
    if (subEl) subEl.textContent = `Dokumente werden automatisch dem Fach ${targetSub.name} zugeordnet (Mehrfachauswahl möglich).`;
    if (dzText) dzText.textContent = `Dateien für ${targetSub.name} hierher ziehen oder auswählen`;
    if (dzSub) dzSub.textContent = "PDF oder Foto (Mehrfachauswahl möglich)";
  } else {
    if (titleEl) titleEl.innerHTML = iconText("Dokumente", "Dokument hinzufügen");
    if (subEl) subEl.textContent = "Lade ein Schulbuch, ein Arbeitsblatt, eine Mitschrift oder einen Test hoch.";
    if (dzText) dzText.textContent = "Datei hierher ziehen oder tippen";
    if (dzSub) dzSub.textContent = "PDF oder Foto (Mehrfachauswahl möglich)";
  }

  if (modalMaterial) modalMaterial.style.display = "flex";
}

if (matConfirmSubject) {
  matConfirmSubject.addEventListener("change", () => {
    updateMaterialTopicOptions(matConfirmSubject.value);
  });
}

if (btnOpenMaterialModal) {
  btnOpenMaterialModal.addEventListener("click", () => {
    openMaterialUploadModal();
  });
}

if (btnCloseMaterialModal) {
  btnCloseMaterialModal.addEventListener("click", () => {
    if (modalMaterial) modalMaterial.style.display = "none";
    resetMaterialModal();
  });
}

if (modalMaterial) {
  modalMaterial.addEventListener("click", (e) => {
    if (e.target === modalMaterial) {
      modalMaterial.style.display = "none";
      resetMaterialModal();
    }
  });
}

if (btnTriggerFile && matFileInput) {
  btnTriggerFile.addEventListener("click", () => matFileInput.click());
}

if (matDropzone && matFileInput) {
  matDropzone.addEventListener("click", (e) => {
    if (e.target !== btnTriggerFile) {
      matFileInput.click();
    }
  });

  matDropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    matDropzone.classList.add("drag-over");
  });

  matDropzone.addEventListener("dragleave", () => {
    matDropzone.classList.remove("drag-over");
  });

  matDropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    matDropzone.classList.remove("drag-over");
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesUpload(Array.from(e.dataTransfer.files));
    }
  });
}

if (matFileInput) {
  matFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFilesUpload(Array.from(e.target.files));
    }
  });
}

if (btnBackMaterialStep) {
  btnBackMaterialStep.addEventListener("click", () => {
    resetMaterialModal();
  });
}

if (btnSubmitMaterial) {
  btnSubmitMaterial.addEventListener("click", async () => {
    if (!currentUploadToken) {
      alert("Keine gültige Sitzung vorhanden.");
      return;
    }
    const titleVal = matConfirmTitle.value.trim();
    if (!titleVal) {
      alert("Bitte gib einen Titel für das Material ein.");
      return;
    }

    const chosenSubId = currentPreselectedSubjectId || matConfirmSubject.value;
    const payload = {
      upload_token: currentUploadToken,
      subject_id: chosenSubId,
      topic_id: matConfirmTopic.value || null,
      title: titleVal,
      kind: matConfirmKind.value,
      summary: matConfirmSummary.value.trim() || null,
      ...currentUploadSignals
    };

    btnSubmitMaterial.disabled = true;
    btnSubmitMaterial.textContent = "Speichere...";

    try {
      const res = await apiFetch("/api/v1/materials/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        if (modalMaterial) modalMaterial.style.display = "none";
        resetMaterialModal();
        await loadMaterials();
        await loadUploadsHistory();
        if (currentDetailSubjectId) await loadSubjectMaterials(currentDetailSubjectId);
      } else {
        const errData = await res.json().catch(() => ({}));
        alert(errData.detail || "Fehler beim Speichern des Materials.");
      }
    } catch (err) {
      alert("Netzwerkfehler.");
    } finally {
      btnSubmitMaterial.disabled = false;
      btnSubmitMaterial.textContent = "Bestätigen & Speichern";
    }
  });
}

