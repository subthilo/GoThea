// GoThea Frontend Application Logic (Milestone 1)

let currentProfile = null;
let currentSubjects = [];

// DOM Elements
const statusBadge = document.getElementById("status-badge");
const statusText = document.getElementById("status-text");
const badgeGrade = document.getElementById("badge-grade");
const userGreeting = document.getElementById("user-greeting");
const userSubtitle = document.getElementById("user-subtitle");
const statSubjectsCount = document.getElementById("stat-subjects-count");
const statTopicsCount = document.getElementById("stat-topics-count");
const dashboardSubjectsGrid = document.getElementById("dashboard-subjects-grid");
const subjectsDetailedList = document.getElementById("subjects-detailed-list");

// Tab Navigation
document.querySelectorAll(".nav-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));

    btn.classList.add("active");
    const target = document.getElementById(`tab-${btn.dataset.tab}`);
    if (target) target.classList.add("active");

    if (btn.dataset.tab === "subjects") {
      checkInboxStatus();
    }
  });
});

// 1. Profil laden
async function loadProfile() {
  try {
    const res = await fetch("/api/v1/profile");
    if (res.ok) {
      currentProfile = await res.json();
      badgeGrade.textContent = `${currentProfile.grade_level}. Klasse`;
      userGreeting.textContent = `Hallo, ${currentProfile.name}! 👋`;
      userSubtitle.textContent = `${currentProfile.grade_level}. Klasse ${currentProfile.school_type} • Land ${currentProfile.federal_state} (Niveaustufe E)`;

      // Profil-Formular initialisieren
      document.getElementById("prof-name").value = currentProfile.name;
      document.getElementById("prof-grade").value = currentProfile.grade_level;
      document.getElementById("prof-school").value = currentProfile.school_type;
    }
  } catch (err) {
    console.error("Fehler beim Laden des Profils:", err);
  }
}

// 2. Fächer und Themen laden
async function loadTaxonomy() {
  try {
    const [subRes, topRes] = await Promise.all([
      fetch("/api/v1/taxonomy/subjects"),
      fetch("/api/v1/taxonomy/topics")
    ]);

    if (subRes.ok && topRes.ok) {
      currentSubjects = await subRes.json();
      const allTopics = await topRes.json();
      allTopicsCache = allTopics;

      statSubjectsCount.textContent = currentSubjects.length;
      statTopicsCount.textContent = allTopics.length;

      // Group topics by subject
      const topicsBySubject = {};
      allTopics.forEach((t) => {
        if (!topicsBySubject[t.subject_id]) topicsBySubject[t.subject_id] = [];
        topicsBySubject[t.subject_id].push(t);
      });

      renderDashboardSubjects(currentSubjects, topicsBySubject);
      renderDetailedSubjects(currentSubjects, topicsBySubject);
    }
  } catch (err) {
    console.error("Fehler beim Laden der Fächer:", err);
  }
}

// Render Dashboard Cards
function renderDashboardSubjects(subjects, topicsMap) {
  dashboardSubjectsGrid.innerHTML = "";
  subjects.forEach((s) => {
    const topics = topicsMap[s.id] || [];
    const card = document.createElement("div");
    card.className = "subject-card";
    card.style.borderLeft = `4px solid ${s.color_code}`;

    const topicPreview = topics.slice(0, 2).map((t) => t.name).join(", ");

    card.innerHTML = `
      <div>
        <div class="subject-header">
          <div class="subject-badge-icon">${s.icon}</div>
          <div class="subject-name">${s.name}</div>
        </div>
        <div class="subject-topics-summary">
          ${topics.length > 0 ? topicPreview : "Noch keine Themen hinterlegt"}
        </div>
      </div>
      <div class="subject-footer">
        <span>${topics.length} Themen im Katalog</span>
        <span style="color: ${s.color_code}; font-weight: 600;">Klasse ${s.min_grade}–${s.max_grade}</span>
      </div>
    `;
    dashboardSubjectsGrid.appendChild(card);
  });
}

// Render Detailed View
function renderDetailedSubjects(subjects, topicsMap) {
  subjectsDetailedList.innerHTML = "";
  subjects.forEach((s) => {
    const topics = topicsMap[s.id] || [];
    const box = document.createElement("div");
    box.className = "subject-detail-box";

    let pillsHtml = topics.map((t) => `
      <div class="topic-pill">
        <span>${t.name}</span>
        ${t.rlp_level_code ? `<span class="topic-rlp-tag">RLP ${t.rlp_level_code}</span>` : ""}
      </div>
    `).join("");

    if (topics.length === 0) {
      pillsHtml = `<span style="color: var(--text-muted);">Keine Themen für diese Klassenstufe hinterlegt.</span>`;
    }

    box.innerHTML = `
      <h3>${s.icon} ${s.name}</h3>
      <div class="topic-pills">${pillsHtml}</div>
    `;
    subjectsDetailedList.appendChild(box);
  });
}

// 3. Profil Speichern Event
document.getElementById("btn-save-profile").addEventListener("click", async () => {
  const name = document.getElementById("prof-name").value;
  const grade_level = parseInt(document.getElementById("prof-grade").value, 10);
  const school_type = document.getElementById("prof-school").value;
  const feedback = document.getElementById("prof-feedback");

  try {
    const res = await fetch("/api/v1/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, grade_level, school_type })
    });

    if (res.ok) {
      feedback.textContent = "✅ Profil erfolgreich aktualisiert!";
      feedback.style.color = "var(--success)";
      await loadProfile();
      await loadTaxonomy();
      setTimeout(() => (feedback.textContent = ""), 3000);
    } else {
      feedback.textContent = "❌ Fehler beim Speichern";
      feedback.style.color = "var(--warning)";
    }
  } catch (err) {
    feedback.textContent = "❌ Netzwerkfehler";
    feedback.style.color = "var(--warning)";
  }
});

// 4. WebSocket Verbindung
function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    statusBadge.classList.add("online");
    statusText.textContent = "Verbunden";
  };

  ws.onclose = () => {
    statusBadge.classList.remove("online");
    statusText.textContent = "Verbindung getrennt";
    setTimeout(connectWebSocket, 3000);
  };
}

// 5. Environment & Staging Check
let currentEnvInfo = null;

async function checkEnvironment() {
  try {
    const res = await fetch("/api/v1/env");
    if (res.ok) {
      const data = await res.json();
      currentEnvInfo = data;
      const stagingBanner = document.getElementById("staging-banner");
      const btnSeedDummies = document.getElementById("btn-seed-dummies");
      if (data.is_staging) {
        stagingBanner.style.display = "block";
        if (btnSeedDummies) btnSeedDummies.style.display = "inline-block";
      } else {
        stagingBanner.style.display = "none";
        if (btnSeedDummies) btnSeedDummies.style.display = "none";
      }
      if (inboxEnvBadge) {
        inboxEnvBadge.textContent = data.is_staging ? "Finder: GoThea-Staging" : "Finder: GoThea-Prod";
      }
    }
  } catch (err) {
    console.error("Fehler beim Prüfen der Umgebung:", err);
  }
}

// 6. Lernplan & Countdown laden
async function loadPlan() {
  try {
    const res = await fetch("/api/v1/plan");
    if (!res.ok) return;
    const plan = await res.json();

    // 6.1 Heutige Aufgaben
    const todayTasksList = document.getElementById("planner-today-tasks");
    const todayMinutes = document.getElementById("planner-today-minutes");
    const todayTitle = document.getElementById("planner-today-title");

    todayTitle.textContent = `Heutige Lerneinheiten (${plan.today_plan.day_name})`;
    todayMinutes.textContent = `${plan.today_plan.total_minutes} Min. verbleibend`;

    todayTasksList.innerHTML = "";
    if (plan.today_plan.is_blocked) {
      todayTasksList.innerHTML = `
        <div class="empty-placeholder" style="padding: 24px;">
          <h3>🏖️ Heute ist Sperrtag!</h3>
          <p>${plan.today_plan.block_info || "Für heute sind keine Lerneinheiten geplant."}</p>
        </div>
      `;
    } else if (plan.today_plan.tasks.length === 0) {
      todayTasksList.innerHTML = `
        <div class="empty-placeholder" style="padding: 24px;">
          <h3>🎉 Alles im grünen Bereich!</h3>
          <p>Für heute stehen keine anstehenden Klassenarbeiten im Lernfenster an.</p>
        </div>
      `;
    } else {
      plan.today_plan.tasks.forEach((tsk) => {
        const card = document.createElement("div");
        card.className = `plan-task-card ${tsk.is_completed ? "completed" : ""}`;
        card.style.borderLeft = `5px solid ${tsk.subject_color}`;

        const phaseClass = `phase-p${tsk.phase_number}`;

        card.innerHTML = `
          <div class="task-left">
            <div class="task-subject-icon">${tsk.subject_icon}</div>
            <div class="task-meta">
              <div class="task-title">
                <span>${tsk.subject_name} – ${tsk.test_kind}</span>
                <span class="phase-pill ${phaseClass}">${tsk.phase_name}</span>
              </div>
              <div class="task-desc">${tsk.phase_description} ${tsk.test_note ? `• <em>${tsk.test_note}</em>` : ""}</div>
            </div>
          </div>
          <div class="task-right">
            <div class="task-time-pill">⏱️ ${tsk.target_minutes} Min.</div>
            <button class="btn-task-check" data-test-id="${tsk.test_id}" data-date="${plan.today_date}" data-completed="${tsk.is_completed}">
              ${tsk.is_completed ? "✓" : ""}
            </button>
          </div>
        `;

        card.querySelector(".btn-task-check").addEventListener("click", async (e) => {
          const btn = e.currentTarget;
          const isComp = btn.dataset.completed === "true";
          await toggleTask(btn.dataset.testId, btn.dataset.date, !isComp);
        });

        todayTasksList.appendChild(card);
      });
    }

    // 6.2 Wochen-Vorschau (Nächste 7 Tage)
    const weekTimeline = document.getElementById("planner-week-timeline");
    weekTimeline.innerHTML = "";
    plan.next_7_days.forEach((day, idx) => {
      const dayCard = document.createElement("div");
      dayCard.className = `timeline-day-card ${idx === 0 ? "today" : ""} ${day.is_blocked ? "blocked" : ""}`;

      let taskListHtml = "";
      if (day.is_blocked) {
        taskListHtml = `<span>🏖️ Sperrtag</span>`;
      } else if (day.tasks.length === 0) {
        taskListHtml = `<span>Frei</span>`;
      } else {
        taskListHtml = day.tasks.map((t) => `
          <div>${t.subject_icon} ${t.subject_name} (${t.target_minutes}m)</div>
        `).join("");
      }

      dayCard.innerHTML = `
        <div class="day-card-header">${day.day_name.split(",")[0]}</div>
        <div class="day-card-tasks">${taskListHtml}</div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 6px;">${day.total_minutes} Min.</div>
      `;
      weekTimeline.appendChild(dayCard);
    });

    // 6.3 Anstehende Prüfungen Grid
    const testsGrid = document.getElementById("planner-tests-grid");
    testsGrid.innerHTML = "";
    if (plan.upcoming_tests.length === 0) {
      testsGrid.innerHTML = `
        <div class="empty-placeholder" style="padding: 24px; grid-column: 1 / -1;">
          <p>Keine bevorstehenden Prüfungen eingetragen. Tippe oben auf „➕ Neue Prüfung“, um einen Countdown zu starten.</p>
        </div>
      `;
    } else {
      plan.upcoming_tests.forEach((t) => {
        const card = document.createElement("div");
        card.className = "test-card";
        card.style.borderLeft = `4px solid ${t.subject_color}`;

        // Datum und Tage berechnen
        const examDate = new Date(t.date);
        const todayD = new Date(plan.today_date);
        const diffDays = Math.round((examDate - todayD) / (1000 * 60 * 60 * 24));
        const badgeText = diffDays === 0 ? "Heute!" : (diffDays === 1 ? "Morgen" : `in ${diffDays} Tagen`);

        card.innerHTML = `
          <div class="test-card-top">
            <div class="test-card-title">${t.subject_icon} ${t.subject_name} – ${t.kind}</div>
            <span class="countdown-badge">${badgeText}</span>
          </div>
          <div class="test-note">${t.note || "Keine Notiz hinterlegt"}</div>
          <div class="test-card-footer">
            <span>📅 ${t.date}</span>
            <button class="btn-del-test" data-id="${t.id}">Löschen</button>
          </div>
        `;

        card.querySelector(".btn-del-test").addEventListener("click", async (e) => {
          if (confirm(`Möchtest du diese ${t.kind} wirklich löschen?`)) {
            await deleteTest(e.currentTarget.dataset.id);
          }
        });

        testsGrid.appendChild(card);
      });
    }

  } catch (err) {
    console.error("Fehler beim Laden des Plans:", err);
  }
}

// Task Toggle
async function toggleTask(testId, dateStr, completed) {
  try {
    await fetch("/api/v1/plan/complete-task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ test_id: testId, date: dateStr, completed })
    });
    await loadPlan();
  } catch (e) {
    console.error(e);
  }
}

// Prüfung löschen
async function deleteTest(testId) {
  try {
    const res = await fetch(`/api/v1/tests/${testId}`, { method: "DELETE" });
    if (res.ok) await loadPlan();
  } catch (e) {
    console.error(e);
  }
}

// Modal Handling
const modalTest = document.getElementById("modal-test");
const modalBlock = document.getElementById("modal-block");

document.getElementById("btn-open-test-modal").addEventListener("click", () => {
  // Fächer Dropdown füllen
  const sel = document.getElementById("input-test-subject");
  sel.innerHTML = currentSubjects.map((s) => `<option value="${s.id}">${s.icon} ${s.name}</option>`).join("");
  // Default Datum: in 7 Tagen
  const d = new Date();
  d.setDate(d.getDate() + 7);
  document.getElementById("input-test-date").value = d.toISOString().split("T")[0];
  modalTest.style.display = "flex";
});

document.getElementById("btn-close-test-modal").addEventListener("click", () => {
  modalTest.style.display = "none";
});

document.getElementById("btn-open-block-modal").addEventListener("click", () => {
  document.getElementById("input-block-date").value = new Date().toISOString().split("T")[0];
  modalBlock.style.display = "flex";
});

document.getElementById("btn-close-block-modal").addEventListener("click", () => {
  modalBlock.style.display = "none";
});

// Neue Prüfung speichern
document.getElementById("btn-submit-test").addEventListener("click", async () => {
  const subject_id = document.getElementById("input-test-subject").value;
  const kind = document.getElementById("input-test-kind").value;
  const dateVal = document.getElementById("input-test-date").value;
  const note = document.getElementById("input-test-note").value;

  if (!dateVal) {
    alert("Bitte ein Datum wählen.");
    return;
  }

  const res = await fetch("/api/v1/tests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject_id, kind, date: dateVal, note })
  });

  if (res.ok) {
    modalTest.style.display = "none";
    document.getElementById("input-test-note").value = "";
    await loadPlan();
  } else {
    alert("Fehler beim Speichern der Prüfung.");
  }
});

// Sperrtag speichern
document.getElementById("btn-submit-block").addEventListener("click", async () => {
  const dateVal = document.getElementById("input-block-date").value;
  const typeVal = document.getElementById("input-block-type").value;

  if (!dateVal) {
    alert("Bitte ein Datum wählen.");
    return;
  }

  const res = await fetch("/api/v1/plan/block", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date: dateVal, type: typeVal })
  });

  if (res.ok) {
    modalBlock.style.display = "none";
    await loadPlan();
  } else {
    alert("Für dieses Datum existiert bereits ein Sperrtag.");
  }
});

// Staging Dummies anlegen
const btnSeedDummies = document.getElementById("btn-seed-dummies");
if (btnSeedDummies) {
  btnSeedDummies.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/v1/staging/seed-dummy-tests", { method: "POST" });
      if (res.ok) {
        alert("3 realistische Test-Prüfungen (Mathe, Bio, Deutsch) angelegt!");
        await loadPlan();
      }
    } catch (e) {
      console.error(e);
    }
  });
}

// Staging Reset Event
const btnResetStaging = document.getElementById("btn-reset-staging");
if (btnResetStaging) {
  btnResetStaging.addEventListener("click", async () => {
    if (!confirm("Möchtest du die Staging-Testdaten wirklich zurücksetzen?")) return;
    try {
      const res = await fetch("/api/v1/staging/reset", { method: "POST" });
      if (res.ok) {
        alert("Staging-Datenbank wurde erfolgreich zurückgesetzt.");
        await loadProfile();
        await loadTaxonomy();
        await loadPlan();
        await loadMaterials();
        await checkInboxStatus();
      } else {
        alert("Fehler beim Zurücksetzen.");
      }
    } catch (e) {
      alert("Netzwerkfehler.");
    }
  });
}

// ==========================================================================
// Material Ingestion Subsystem (Milestone 4)
// ==========================================================================

let currentMaterials = [];
let currentUploadToken = null;
let allTopicsCache = [];

const materialsList = document.getElementById("materials-list");
const materialsCountBadge = document.getElementById("materials-count-badge");
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
    const res = await fetch("/api/v1/inbox/status");
    if (!res.ok) return;
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
        btnProcessInbox.innerHTML = `📥 Jetzt einsortieren (${pending})`;
      }
    } else {
      inboxCard.classList.remove("has-pending");
      if (inboxBadgeDot) inboxBadgeDot.style.display = "none";
      if (inboxSubtitle) {
        inboxSubtitle.textContent = `Keine wartenden Dateien im Netzwerkordner.`;
      }
      if (btnProcessInbox) {
        btnProcessInbox.disabled = true;
        btnProcessInbox.innerHTML = `📥 Jetzt einsortieren`;
      }
    }

    // Dateiliste rendern
    if (inboxFileList) {
      inboxFileList.innerHTML = "";
      if (files.length === 0) {
        inboxFileList.innerHTML = `
          <div class="inbox-empty-hint">
            <span>✨</span>
            <span>Ziehe PDFs oder Bilder in deinen Mac-Finder Netzwerkordner <code>${shareName}</code>, um sie automatisch hier einzulesen.</span>
          </div>
        `;
      } else {
        files.forEach((f) => {
          const chip = document.createElement("div");
          chip.className = "inbox-file-chip";
          const isPdf = (f.mime_type || "").includes("pdf") || (f.filename || "").toLowerCase().endsWith(".pdf");
          const icon = isPdf ? "📄" : "🖼️";
          const sizeKb = Math.round((f.file_size || 0) / 1024);
          const sizeStr = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;

          chip.innerHTML = `
            <span>${icon}</span>
            <span style="font-weight: 600;">${f.filename}</span>
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
    const res = await fetch("/api/v1/inbox/process", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      const pCount = data.processed_count || 0;
      const eCount = data.errors_count || 0;

      if (inboxSpinner) inboxSpinner.style.display = "none";

      if (pCount > 0 && eCount === 0) {
        inboxProcessStatus.className = "inbox-process-status success";
        if (inboxStatusMsg) {
          inboxStatusMsg.textContent = `✅ Erfolgreich: ${pCount} Dokument${pCount === 1 ? "" : "e"} analysiert und einsortiert!`;
        }
      } else if (pCount > 0 && eCount > 0) {
        inboxProcessStatus.className = "inbox-process-status warning";
        if (inboxStatusMsg) {
          inboxStatusMsg.textContent = `⚠️ ${pCount} Dokument${pCount === 1 ? "" : "e"} verarbeitet, ${eCount} fehlerhafte Datei(en) nach _errors/ verschoben.`;
        }
      } else if (pCount === 0 && eCount > 0) {
        inboxProcessStatus.className = "inbox-process-status warning";
        if (inboxStatusMsg) {
          inboxStatusMsg.textContent = `⚠️ Fehler bei ${eCount} Datei(en). Details in _errors/.`;
        }
      } else {
        inboxProcessStatus.className = "inbox-process-status";
        if (inboxStatusMsg) {
          inboxStatusMsg.textContent = "Keine neuen Dateien zur Verarbeitung gefunden.";
        }
      }

      await loadMaterials();
      await checkInboxStatus();

      setTimeout(() => {
        if (inboxProcessStatus) inboxProcessStatus.style.display = "none";
      }, 6000);
    } else {
      const err = await res.json().catch(() => ({}));
      if (inboxSpinner) inboxSpinner.style.display = "none";
      inboxProcessStatus.className = "inbox-process-status warning";
      if (inboxStatusMsg) {
        inboxStatusMsg.textContent = `❌ Fehler bei der Verarbeitung: ${err.detail || "Serverfehler"}`;
      }
    }
  } catch (err) {
    console.error("Netzwerkfehler beim Verarbeiten des Posteingangs:", err);
    if (inboxSpinner) inboxSpinner.style.display = "none";
    inboxProcessStatus.className = "inbox-process-status warning";
    if (inboxStatusMsg) {
      inboxStatusMsg.textContent = "❌ Netzwerkfehler beim Verarbeiten.";
    }
  } finally {
    await checkInboxStatus();
  }
}

if (btnRefreshInbox) {
  btnRefreshInbox.addEventListener("click", () => {
    checkInboxStatus();
  });
}

if (btnProcessInbox) {
  btnProcessInbox.addEventListener("click", () => {
    processInbox();
  });
}

async function loadMaterials() {
  if (!materialsList) return;
  try {
    const res = await fetch("/api/v1/materials");
    if (res.ok) {
      currentMaterials = await res.json();
      if (materialsCountBadge) {
        materialsCountBadge.textContent = `${currentMaterials.length} Dokument${currentMaterials.length === 1 ? "" : "e"}`;
      }
      renderMaterialsList(currentMaterials);
    }
  } catch (err) {
    console.error("Fehler beim Laden der Materialien:", err);
  }
}

function renderMaterialsList(materials) {
  if (!materialsList) return;
  materialsList.innerHTML = "";

  if (materials.length === 0) {
    materialsList.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 36px 16px; background: rgba(255, 255, 255, 0.02); border: 1px dashed var(--border-color); border-radius: 14px; color: var(--text-secondary);">
        <span style="font-size: 2.2rem; display: block; margin-bottom: 8px;">📭</span>
        <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">Noch keine Lernmaterialien hochgeladen</div>
        <p style="font-size: 0.85rem; max-width: 440px; margin: 0 auto;">Tippe oben auf <strong>„➕ Material hochladen“</strong>, um Arbeitsblätter, Mitschriften oder Hefterseiten für deine Fächer hinzuzufügen.</p>
      </div>
    `;
    return;
  }

  materials.forEach((m) => {
    const card = document.createElement("div");
    card.className = "material-card";

    const isPdf = m.mime_type.includes("pdf");
    const docIcon = isPdf ? "📄" : "🖼️";
    const sizeKb = Math.round(m.file_size / 1024);
    const sizeStr = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;

    card.innerHTML = `
      <div>
        <div class="mat-card-header">
          <div class="mat-card-title">${m.title}</div>
          <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
            ${m.dossier_title ? `<span class="mat-dossier-badge" title="Zugeordneter Hefter">📁 ${m.dossier_title}</span>` : ""}
            <span class="mat-card-badge" style="background: rgba(99, 102, 241, 0.15); color: var(--accent-light); border: 1px solid rgba(99, 102, 241, 0.3);">
              ${m.kind}
            </span>
          </div>
        </div>
        <div class="mat-card-meta">
          <span style="color: ${m.subject_color || 'var(--text-primary)'}; font-weight: 600;">
            ${m.subject_icon || '📚'} ${m.subject_name || 'Fach'}
          </span>
          ${m.topic_name ? `<span>• 📑 ${m.topic_name}</span>` : ""}
          <span>• ${docIcon} ${m.page_count} S. (${sizeStr})</span>
          ${m.start_page && m.end_page ? `<span>• S. ${m.start_page}–${m.end_page}</span>` : ""}
        </div>
        ${m.summary ? `<div class="mat-card-summary">“${m.summary}”</div>` : ""}
      </div>
      <div class="mat-card-actions">
        <button class="btn-mat-action btn-mat-view" title="Dokument im Popup ansehen">
          👁️ Öffnen
        </button>
        <button class="btn-mat-action btn-mat-wb" title="Auf Tafel öffnen und beschreiben">
          🎨 Tafel
        </button>
        <button class="btn-mat-action btn-mat-del" data-id="${m.id}" title="Material löschen">
          🗑️
        </button>
      </div>
    `;

    card.querySelector(".btn-mat-view").addEventListener("click", () => {
      openDocumentViewerModal(m);
    });

    card.querySelector(".btn-mat-wb").addEventListener("click", () => {
      openMaterialOnWhiteboard(m);
    });

    card.querySelector(".btn-mat-del").addEventListener("click", async () => {
      if (!confirm(`Möchtest du das Material „${m.title}“ wirklich löschen?`)) return;
      try {
        const delRes = await fetch(`/api/v1/materials/${m.id}`, { method: "DELETE" });
        if (delRes.ok) {
          await loadMaterials();
        } else {
          alert("Fehler beim Löschen.");
        }
      } catch (err) {
        alert("Netzwerkfehler beim Löschen.");
      }
    });

    materialsList.appendChild(card);
  });
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

async function handleFileUpload(file) {
  if (!file) return;

  if (matDropzone) matDropzone.style.display = "none";
  if (matUploadSpinner) matUploadSpinner.style.display = "block";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/v1/materials/pre-analyze", {
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

    matStepUpload.style.display = "none";
    matStepConfirm.style.display = "block";

    matPreviewFilename.textContent = data.filename;
    const sizeKb = Math.round(data.file_size / 1024);
    const sizeStr = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;
    matPreviewMeta.textContent = `${data.page_count} Seite${data.page_count === 1 ? "" : "n"} • ${sizeStr}`;
    matPreviewIcon.textContent = data.mime_type.includes("pdf") ? "📄" : "🖼️";

    if (data.preview_snippet) {
      matPreviewSnippet.style.display = "block";
      matPreviewSnippet.textContent = `„${data.preview_snippet}“`;
    } else {
      matPreviewSnippet.style.display = "none";
    }

    matConfirmSubject.innerHTML = "";
    currentSubjects.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = `${s.icon} ${s.name}`;
      if (data.predicted_subject_id && s.id === data.predicted_subject_id) {
        opt.selected = true;
      }
      matConfirmSubject.appendChild(opt);
    });

    updateMaterialTopicOptions(matConfirmSubject.value, data.predicted_topic_id);

    matConfirmTitle.value = data.predicted_title || "Lernmaterial";
    matConfirmKind.value = data.predicted_kind || "Arbeitsblatt";
    matConfirmSummary.value = "";
  } catch (err) {
    alert("Netzwerkfehler beim Upload.");
    resetMaterialModal();
  }
}

function resetMaterialModal() {
  currentUploadToken = null;
  if (matFileInput) matFileInput.value = "";
  if (matDropzone) matDropzone.style.display = "flex";
  if (matUploadSpinner) matUploadSpinner.style.display = "none";
  if (matStepUpload) matStepUpload.style.display = "block";
  if (matStepConfirm) matStepConfirm.style.display = "none";
}

if (matConfirmSubject) {
  matConfirmSubject.addEventListener("change", () => {
    updateMaterialTopicOptions(matConfirmSubject.value);
  });
}

if (btnOpenMaterialModal) {
  btnOpenMaterialModal.addEventListener("click", () => {
    resetMaterialModal();
    if (modalMaterial) modalMaterial.style.display = "flex";
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
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });
}

if (matFileInput) {
  matFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
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

    const payload = {
      upload_token: currentUploadToken,
      subject_id: matConfirmSubject.value,
      topic_id: matConfirmTopic.value || null,
      title: titleVal,
      kind: matConfirmKind.value,
      summary: matConfirmSummary.value.trim() || null
    };

    btnSubmitMaterial.disabled = true;
    btnSubmitMaterial.textContent = "Speichere...";

    try {
      const res = await fetch("/api/v1/materials/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        if (modalMaterial) modalMaterial.style.display = "none";
        resetMaterialModal();
        await loadMaterials();
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

// ==========================================
// 8. Dokumenten-Viewer (Popup) & Tafel-Verbindung
// ==========================================
let activeViewerMaterial = null;
let currentViewerPage = 1;

const modalMaterialViewer = document.getElementById("modal-material-viewer");
const btnCloseViewerModal = document.getElementById("btn-close-viewer-modal");
const btnViewerOpenWb = document.getElementById("btn-viewer-open-wb");
const btnViewerPrevPage = document.getElementById("btn-viewer-prev-page");
const btnViewerNextPage = document.getElementById("btn-viewer-next-page");

function openDocumentViewerModal(material) {
  activeViewerMaterial = material;
  currentViewerPage = 1;

  const titleEl = document.getElementById("viewer-doc-title");
  const badgeEl = document.getElementById("viewer-doc-badge");
  const dlBtn = document.getElementById("btn-viewer-download");
  const pagerBar = document.getElementById("viewer-pager-bar");

  if (titleEl) titleEl.textContent = material.title;
  if (badgeEl) {
    badgeEl.textContent = `${material.subject_name || "Fach"} • ${material.kind || "Material"}${material.topic_name ? " • " + material.topic_name : ""}`;
  }
  if (dlBtn) {
    dlBtn.href = `/api/v1/materials/${material.id}/file`;
  }

  const pageCount = material.page_count || 1;
  if (pagerBar) {
    pagerBar.style.display = pageCount > 1 ? "flex" : "none";
  }

  renderViewerPage();
  if (modalMaterialViewer) modalMaterialViewer.style.display = "flex";
}

function renderViewerPage() {
  if (!activeViewerMaterial) return;
  const pageLabel = document.getElementById("viewer-page-label");
  const viewerImg = document.getElementById("viewer-img");
  const pageCount = activeViewerMaterial.page_count || 1;

  if (pageLabel) {
    pageLabel.textContent = `Seite ${currentViewerPage} / ${pageCount}`;
  }
  if (viewerImg) {
    viewerImg.src = `/api/v1/materials/${activeViewerMaterial.id}/preview?page=${currentViewerPage}`;
  }
}

function closeDocumentViewerModal() {
  if (modalMaterialViewer) modalMaterialViewer.style.display = "none";
  const viewerImg = document.getElementById("viewer-img");
  if (viewerImg) viewerImg.src = "";
  activeViewerMaterial = null;
}

function openMaterialOnWhiteboard(material) {
  // Tab zur Tafel wechseln
  const tabWbBtn = document.querySelector('.nav-tab[data-tab="whiteboard"]');
  if (tabWbBtn) tabWbBtn.click();

  // Fach der Vorlage einstellen
  const wbSubSelect = document.getElementById("wb-subject-select");
  if (wbSubSelect && material.subject_id) {
    wbSubSelect.value = material.subject_id;
    wbSubSelect.dispatchEvent(new Event("change"));
  }

  // Vorlage auf Tafel laden
  if (typeof window.loadWorksheetOnWhiteboard === "function") {
    window.loadWorksheetOnWhiteboard(material);
  }
}

if (btnCloseViewerModal) {
  btnCloseViewerModal.addEventListener("click", closeDocumentViewerModal);
}

if (modalMaterialViewer) {
  modalMaterialViewer.addEventListener("click", (e) => {
    if (e.target === modalMaterialViewer) {
      closeDocumentViewerModal();
    }
  });
}

if (btnViewerPrevPage) {
  btnViewerPrevPage.addEventListener("click", () => {
    if (activeViewerMaterial && currentViewerPage > 1) {
      currentViewerPage--;
      renderViewerPage();
    }
  });
}

if (btnViewerNextPage) {
  btnViewerNextPage.addEventListener("click", () => {
    if (activeViewerMaterial && currentViewerPage < (activeViewerMaterial.page_count || 1)) {
      currentViewerPage++;
      renderViewerPage();
    }
  });
}

if (btnViewerOpenWb) {
  btnViewerOpenWb.addEventListener("click", () => {
    if (activeViewerMaterial) {
      const mat = activeViewerMaterial;
      closeDocumentViewerModal();
      openMaterialOnWhiteboard(mat);
    }
  });
}

// Init
async function initApp() {
  await checkEnvironment();
  await loadProfile();
  await loadTaxonomy();
  await loadPlan();
  await loadMaterials();
  await checkInboxStatus();
  connectWebSocket();
}

initApp();
