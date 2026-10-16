// ==========================================================================
// Material Reorganization Subsystem (Edit Metadata, Reorder Pages, Merge)
// ==========================================================================

async function refreshAllMaterialViews() {
  await loadMaterials();
  await loadUploadsHistory();
  if (currentDetailSubjectId) {
    await loadSubjectMaterials(currentDetailSubjectId);
  }
}

// --- 1. Edit Material Modal (Fach, Thema, Titel, Art) ---
const modalEditMaterial = document.getElementById("modal-edit-material");
const btnCloseEditMaterial = document.getElementById("btn-close-edit-material-modal");
const btnCancelEditMaterial = document.getElementById("btn-cancel-edit-material");
const btnSaveEditMaterial = document.getElementById("btn-save-edit-material");
const editMatSubject = document.getElementById("edit-mat-subject");
const editMatTopic = document.getElementById("edit-mat-topic");

function updateEditTopicOptions(subjectId, selectedTopicId = null) {
  if (!editMatTopic) return;
  editMatTopic.innerHTML = '<option value="">-- Kein spezifisches Thema --</option>';
  const topics = allTopicsCache.filter((t) => t.subject_id === subjectId);
  topics.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = `${t.name} (Stufe ${t.rlp_level_code || "E"})`;
    if (selectedTopicId && t.id === selectedTopicId) opt.selected = true;
    editMatTopic.appendChild(opt);
  });
}

function openEditMaterialModal(material) {
  if (!modalEditMaterial) return;
  const idInput = document.getElementById("edit-mat-id");
  const titleInput = document.getElementById("edit-mat-title");
  const summaryInput = document.getElementById("edit-mat-summary");

  if (idInput) idInput.value = material.id;
  if (titleInput) titleInput.value = material.title || "";
  if (summaryInput) summaryInput.value = material.summary || "";

  if (editMatSubject) {
    editMatSubject.innerHTML = currentSubjects
      .map((s) => `<option value="${s.id}" ${s.id === material.subject_id ? "selected" : ""}>${escapeHtml(s.name)}</option>`)
      .join("");

    updateEditTopicOptions(material.subject_id, material.topic_id);
    editMatSubject.onchange = () => {
      updateEditTopicOptions(editMatSubject.value, null);
    };
  }

  const kindSelect = document.getElementById("edit-mat-kind");
  if (kindSelect) {
    let matched = false;
    for (let i = 0; i < kindSelect.options.length; i++) {
      if (kindSelect.options[i].value === material.kind) {
        kindSelect.selectedIndex = i;
        matched = true;
        break;
      }
    }
    if (!matched && material.kind) {
      const customOpt = document.createElement("option");
      customOpt.value = material.kind;
      customOpt.textContent = material.kind;
      customOpt.selected = true;
      kindSelect.appendChild(customOpt);
    }
  }

  modalEditMaterial.style.display = "flex";
}

function closeEditMaterialModal() {
  if (modalEditMaterial) modalEditMaterial.style.display = "none";
}

if (btnCloseEditMaterial) btnCloseEditMaterial.addEventListener("click", closeEditMaterialModal);
if (btnCancelEditMaterial) btnCancelEditMaterial.addEventListener("click", closeEditMaterialModal);
if (modalEditMaterial) {
  modalEditMaterial.addEventListener("click", (e) => {
    if (e.target === modalEditMaterial) closeEditMaterialModal();
  });
}

if (btnSaveEditMaterial) {
  btnSaveEditMaterial.addEventListener("click", async () => {
    const matId = document.getElementById("edit-mat-id").value;
    const title = document.getElementById("edit-mat-title").value.trim();
    const subjectId = editMatSubject ? editMatSubject.value : null;
    const topicId = editMatTopic ? (editMatTopic.value || null) : null;
    const kind = document.getElementById("edit-mat-kind").value;
    const summary = document.getElementById("edit-mat-summary").value.trim();

    if (!title) {
      alert("Bitte gib einen Titel für das Dokument an.");
      return;
    }

    btnSaveEditMaterial.disabled = true;
    btnSaveEditMaterial.textContent = "Speichere...";
    try {
      const res = await apiFetch(`/api/v1/materials/${matId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          subject_id: subjectId,
          topic_id: topicId,
          kind,
          summary
        })
      });

      if (res.ok) {
        closeEditMaterialModal();
        await refreshAllMaterialViews();
        if (kind === "Buch" || kind === "Buchauszug") {
          await loadBooks();
        }
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Fehler beim Aktualisieren: ${err.detail || "Unbekannter Fehler"}`);
      }
    } catch (e) {
      console.error(e);
      alert("Netzwerkfehler beim Aktualisieren.");
    } finally {
      btnSaveEditMaterial.disabled = false;
      btnSaveEditMaterial.textContent = "Änderungen speichern";
    }
  });
}

// --- 2. Reorder Pages Modal (Seitenreihenfolge ändern & löschen) ---
let activeReorderMaterial = null;
let currentReorderPages = [];
const modalReorderPages = document.getElementById("modal-reorder-pages");
const btnCloseReorderModal = document.getElementById("btn-close-reorder-modal");
const btnReorderReset = document.getElementById("btn-reorder-reset");
const btnSaveReorderPages = document.getElementById("btn-save-reorder-pages");

function openReorderPagesModal(material) {
  if (!modalReorderPages) return;
  activeReorderMaterial = material;
  const count = material.page_count || 1;
  currentReorderPages = Array.from({ length: count }, (_, i) => i + 1);

  const titleEl = document.getElementById("reorder-doc-title");
  if (titleEl) {
    titleEl.textContent = `Seiten von „${material.title}“ ordnen`;
  }
  renderReorderPagesGrid();
  modalReorderPages.style.display = "flex";
}

function closeReorderPagesModal() {
  if (modalReorderPages) modalReorderPages.style.display = "none";
  activeReorderMaterial = null;
  currentReorderPages = [];
}

function renderReorderPagesGrid() {
  const grid = document.getElementById("reorder-pages-grid");
  const badge = document.getElementById("reorder-summary-badge");
  if (!grid || !activeReorderMaterial) return;

  const totalOrig = activeReorderMaterial.page_count || 1;
  if (badge) {
    badge.textContent = `${currentReorderPages.length} von ${totalOrig} Seiten aktiv`;
  }

  grid.innerHTML = "";

  if (currentReorderPages.length === 0) {
    grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-secondary);">Keine Seiten mehr vorhanden. Klicke auf Zurücksetzen, um alle Seiten wiederherzustellen.</div>`;
    return;
  }

  currentReorderPages.forEach((origPage, idx) => {
    const card = document.createElement("div");
    card.className = "reorder-page-card";

    const isFirst = idx === 0;
    const isLast = idx === currentReorderPages.length - 1;

    card.innerHTML = `
      <div class="reorder-page-header">
        <span class="reorder-page-badge">Seite ${idx + 1}</span>
        <span class="reorder-orig-badge">(Orig. S. ${origPage})</span>
      </div>
      <div class="reorder-page-thumb-wrap">
        <img class="reorder-page-thumb" src="/api/v1/materials/${activeReorderMaterial.id}/preview?page=${origPage}" alt="Seite ${origPage}" loading="lazy">
      </div>
      <div class="reorder-card-actions">
        <button type="button" class="reorder-btn reorder-btn-left" title="Nach links verschieben" ${isFirst ? "disabled" : ""}>${icon("Pfeil links")}</button>
        <button type="button" class="reorder-btn reorder-btn-del" title="Diese Seite entfernen" ${currentReorderPages.length <= 1 ? "disabled" : ""}>${icon("Papierkorb")}</button>
        <button type="button" class="reorder-btn reorder-btn-right" title="Nach rechts verschieben" ${isLast ? "disabled" : ""}>${icon("Pfeil rechts")}</button>
      </div>
    `;

    const leftBtn = card.querySelector(".reorder-btn-left");
    if (leftBtn) {
      leftBtn.onclick = () => {
        if (idx > 0) {
          const temp = currentReorderPages[idx];
          currentReorderPages[idx] = currentReorderPages[idx - 1];
          currentReorderPages[idx - 1] = temp;
          renderReorderPagesGrid();
        }
      };
    }

    const rightBtn = card.querySelector(".reorder-btn-right");
    if (rightBtn) {
      rightBtn.onclick = () => {
        if (idx < currentReorderPages.length - 1) {
          const temp = currentReorderPages[idx];
          currentReorderPages[idx] = currentReorderPages[idx + 1];
          currentReorderPages[idx + 1] = temp;
          renderReorderPagesGrid();
        }
      };
    }

    const delBtn = card.querySelector(".reorder-btn-del");
    if (delBtn) {
      delBtn.onclick = () => {
        if (currentReorderPages.length > 1) {
          currentReorderPages.splice(idx, 1);
          renderReorderPagesGrid();
        } else {
          alert("Ein Dokument muss mindestens eine Seite behalten.");
        }
      };
    }

    grid.appendChild(card);
  });
}

if (btnReorderReset) {
  btnReorderReset.addEventListener("click", () => {
    if (activeReorderMaterial) {
      const count = activeReorderMaterial.page_count || 1;
      currentReorderPages = Array.from({ length: count }, (_, i) => i + 1);
      renderReorderPagesGrid();
    }
  });
}

if (btnCloseReorderModal) btnCloseReorderModal.addEventListener("click", closeReorderPagesModal);
if (modalReorderPages) {
  modalReorderPages.addEventListener("click", (e) => {
    if (e.target === modalReorderPages) closeReorderPagesModal();
  });
}

if (btnSaveReorderPages) {
  btnSaveReorderPages.addEventListener("click", async () => {
    if (!activeReorderMaterial || currentReorderPages.length === 0) return;

    btnSaveReorderPages.disabled = true;
    btnSaveReorderPages.textContent = "Speichere Seiten...";

    try {
      const res = await apiFetch(`/api/v1/materials/${activeReorderMaterial.id}/reorder-pages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page_order: currentReorderPages })
      });

      if (res.ok) {
        const updatedMat = await res.json();
        closeReorderPagesModal();
        await refreshAllMaterialViews();
        if (activeViewerMaterial && activeViewerMaterial.id === updatedMat.id) {
          activeViewerMaterial.page_count = updatedMat.page_count;
          if (currentViewerPage > updatedMat.page_count) currentViewerPage = updatedMat.page_count;
          renderViewerPage();
        }
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Fehler beim Speichern der Seitenreihenfolge: ${err.detail || "Unbekannter Fehler"}`);
      }
    } catch (e) {
      console.error(e);
      alert("Netzwerkfehler beim Speichern der Seitenreihenfolge.");
    } finally {
      btnSaveReorderPages.disabled = false;
      btnSaveReorderPages.innerHTML = iconText("Speichern", "Neue Reihenfolge speichern");
    }
  });
}

// --- 3. Merge Materials Modal (Dokumente zusammenführen) ---
let mergeSelectedDocIds = [];
const modalMergeMaterials = document.getElementById("modal-merge-materials");
const btnCloseMergeModal = document.getElementById("btn-close-merge-modal");
const mergeFilterSubject = document.getElementById("merge-filter-subject");
const mergeTargetSubject = document.getElementById("merge-target-subject");
const mergeTargetTopic = document.getElementById("merge-target-topic");
const btnSubmitMerge = document.getElementById("btn-submit-merge");

function updateMergeTargetTopicOptions(subjectId) {
  if (!mergeTargetTopic) return;
  mergeTargetTopic.innerHTML = '<option value="">-- Kein Thema --</option>';
  const topics = allTopicsCache.filter((t) => t.subject_id === subjectId);
  topics.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = `${t.name} (Stufe ${t.rlp_level_code || "E"})`;
    mergeTargetTopic.appendChild(opt);
  });
}

function openMergeMaterialsModal(preselectedSubjectId = null) {
  if (!modalMergeMaterials) return;
  mergeSelectedDocIds = [];

  // Filter dropdown
  if (mergeFilterSubject) {
    mergeFilterSubject.innerHTML = '<option value="all">Alle Fächer</option>' +
      currentSubjects.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join("");
    if (preselectedSubjectId) {
      mergeFilterSubject.value = preselectedSubjectId;
    } else {
      mergeFilterSubject.value = "all";
    }
    mergeFilterSubject.onchange = renderMergeAvailableDocs;
  }

  // Target subject dropdown
  if (mergeTargetSubject) {
    mergeTargetSubject.innerHTML = currentSubjects
      .map((s) => `<option value="${s.id}" ${s.id === preselectedSubjectId ? "selected" : ""}>${escapeHtml(s.name)}</option>`)
      .join("");
    const chosenSubject = preselectedSubjectId || (currentSubjects[0] ? currentSubjects[0].id : "");
    updateMergeTargetTopicOptions(chosenSubject);
    mergeTargetSubject.onchange = () => {
      updateMergeTargetTopicOptions(mergeTargetSubject.value);
    };
  }

  const titleInput = document.getElementById("merge-target-title");
  if (titleInput) {
    const todayStr = new Date().toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
    titleInput.value = `Zusammenfassung (${todayStr})`;
  }

  renderMergeAvailableDocs();
  renderMergeOrderList();
  modalMergeMaterials.style.display = "flex";
}

function closeMergeMaterialsModal() {
  if (modalMergeMaterials) modalMergeMaterials.style.display = "none";
  mergeSelectedDocIds = [];
}

function renderMergeAvailableDocs() {
  const container = document.getElementById("merge-available-list");
  if (!container) return;
  container.innerHTML = "";

  const filterSubjectId = mergeFilterSubject ? mergeFilterSubject.value : "all";
  const docs = currentMaterials.filter((m) => {
    if (filterSubjectId === "all") return true;
    return m.subject_id === filterSubjectId;
  });

  if (docs.length === 0) {
    container.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 0.85rem;">Keine Dokumente für diese Auswahl gefunden.</div>`;
    return;
  }

  docs.forEach((m) => {
    const isSelected = mergeSelectedDocIds.includes(m.id);
    const item = document.createElement("div");
    item.className = `merge-doc-item ${isSelected ? "selected" : ""}`;

    item.innerHTML = `
      <input type="checkbox" style="pointer-events: none;" ${isSelected ? "checked" : ""}>
      <div class="merge-doc-info">
        <div class="merge-doc-title">${escapeHtml(m.title)}</div>
        <div class="merge-doc-meta">
          <span>${subjectLabel(m.subject_name)}</span>
          <span>• ${m.kind || "Dokument"}</span>
          <span>• ${m.page_count} S.</span>
        </div>
      </div>
    `;

    item.onclick = () => {
      const idx = mergeSelectedDocIds.indexOf(m.id);
      if (idx >= 0) {
        mergeSelectedDocIds.splice(idx, 1);
      } else {
        mergeSelectedDocIds.push(m.id);
      }
      renderMergeAvailableDocs();
      renderMergeOrderList();
    };

    container.appendChild(item);
  });
}

function renderMergeOrderList() {
  const container = document.getElementById("merge-order-list");
  const countBadge = document.getElementById("merge-selected-count");
  if (!container) return;

  if (countBadge) countBadge.textContent = mergeSelectedDocIds.length;
  container.innerHTML = "";

  if (mergeSelectedDocIds.length === 0) {
    container.innerHTML = `<div class="merge-empty-state">Wähle links mindestens 2 Dokumente aus</div>`;
    return;
  }

  mergeSelectedDocIds.forEach((id, idx) => {
    const m = currentMaterials.find((doc) => doc.id === id);
    if (!m) return;

    const isFirst = idx === 0;
    const isLast = idx === mergeSelectedDocIds.length - 1;

    const row = document.createElement("div");
    row.className = "merge-order-item";
    row.innerHTML = `
      <div class="merge-order-index">#${idx + 1}</div>
      <div class="merge-doc-info">
        <div class="merge-doc-title">${escapeHtml(m.title)}</div>
        <div class="merge-doc-meta">${m.page_count} S. • ${m.subject_name ? subjectLabel(m.subject_name) : ""}</div>
      </div>
      <div class="merge-order-actions">
        <button type="button" class="merge-order-btn btn-merge-up" title="Nach oben" ${isFirst ? "disabled" : ""}>${icon("Pfeil hoch")}</button>
        <button type="button" class="merge-order-btn btn-merge-down" title="Nach unten" ${isLast ? "disabled" : ""}>${icon("Pfeil runter")}</button>
        <button type="button" class="merge-order-btn btn-merge-remove" title="Aus Auswahl entfernen">${icon("Schließen")}</button>
      </div>
    `;

    const upBtn = row.querySelector(".btn-merge-up");
    if (upBtn) {
      upBtn.onclick = (e) => {
        e.stopPropagation();
        if (idx > 0) {
          const temp = mergeSelectedDocIds[idx];
          mergeSelectedDocIds[idx] = mergeSelectedDocIds[idx - 1];
          mergeSelectedDocIds[idx - 1] = temp;
          renderMergeOrderList();
        }
      };
    }

    const downBtn = row.querySelector(".btn-merge-down");
    if (downBtn) {
      downBtn.onclick = (e) => {
        e.stopPropagation();
        if (idx < mergeSelectedDocIds.length - 1) {
          const temp = mergeSelectedDocIds[idx];
          mergeSelectedDocIds[idx] = mergeSelectedDocIds[idx + 1];
          mergeSelectedDocIds[idx + 1] = temp;
          renderMergeOrderList();
        }
      };
    }

    const remBtn = row.querySelector(".btn-merge-remove");
    if (remBtn) {
      remBtn.onclick = (e) => {
        e.stopPropagation();
        mergeSelectedDocIds.splice(idx, 1);
        renderMergeAvailableDocs();
        renderMergeOrderList();
      };
    }

    container.appendChild(row);
  });
}

if (btnCloseMergeModal) btnCloseMergeModal.addEventListener("click", closeMergeMaterialsModal);
if (modalMergeMaterials) {
  modalMergeMaterials.addEventListener("click", (e) => {
    if (e.target === modalMergeMaterials) closeMergeMaterialsModal();
  });
}

if (btnSubmitMerge) {
  btnSubmitMerge.addEventListener("click", async () => {
    if (mergeSelectedDocIds.length < 2) {
      alert("Bitte wähle mindestens 2 Dokumente zum Zusammenführen aus.");
      return;
    }

    const title = document.getElementById("merge-target-title").value.trim();
    const subjectId = mergeTargetSubject ? mergeTargetSubject.value : null;
    const topicId = mergeTargetTopic ? (mergeTargetTopic.value || null) : null;
    const kind = document.getElementById("merge-target-kind").value;
    const deleteSources = document.getElementById("merge-delete-sources").checked;

    if (!title) {
      alert("Bitte gib einen Titel für das zusammengeführte Dokument an.");
      return;
    }
    if (!subjectId) {
      alert("Bitte wähle ein Schulfach aus.");
      return;
    }

    btnSubmitMerge.disabled = true;
    btnSubmitMerge.textContent = "Verbinde Dokumente...";

    try {
      const res = await apiFetch("/api/v1/materials/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_material_ids: mergeSelectedDocIds,
          title,
          subject_id: subjectId,
          topic_id: topicId,
          kind,
          delete_sources: deleteSources
        })
      });

      if (res.ok) {
        closeMergeMaterialsModal();
        await refreshAllMaterialViews();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Fehler beim Zusammenführen: ${err.detail || "Unbekannter Fehler"}`);
      }
    } catch (e) {
      console.error(e);
      alert("Netzwerkfehler beim Zusammenführen der Dokumente.");
    } finally {
      btnSubmitMerge.disabled = false;
      btnSubmitMerge.innerHTML = iconText("Verknüpfen", "Dokumente zusammenführen");
    }
  });
}

// Toolbar-Buttons für Zusammenführen
const btnUploadsMerge = document.getElementById("btn-open-uploads-merge-modal");
if (btnUploadsMerge) {
  btnUploadsMerge.addEventListener("click", () => {
    openMergeMaterialsModal();
  });
}

const btnSubjectMerge = document.getElementById("btn-open-subject-merge-modal");
if (btnSubjectMerge) {
  btnSubjectMerge.addEventListener("click", () => {
    openMergeMaterialsModal(currentDetailSubjectId);
  });
}

