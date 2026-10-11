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

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function switchToTab(tabName) {
  const btn = document.querySelector(`.nav-tab[data-tab="${tabName}"]`);
  if (btn) btn.click();
}

// Tab Navigation
document.querySelectorAll(".nav-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));

    btn.classList.add("active");
    const target = document.getElementById(`tab-${btn.dataset.tab}`);
    if (target) target.classList.add("active");

    if (btn.dataset.tab !== "books" && bookSaveTimer) {
      saveCurrentBookAnnotations();
    }

    if (btn.dataset.tab === "subjects") {
      checkInboxStatus();
    }
    if (btn.dataset.tab === "timetable") {
      loadTimetable();
    }
    if (btn.dataset.tab === "books") {
      loadBooks();
      setTimeout(syncBookAnnotationCanvasSize, 100);
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
    if (!currentEnvInfo) {
      try {
        const envRes = await fetch("/api/v1/env");
        if (envRes.ok) currentEnvInfo = await envRes.json();
      } catch (e) {}
    }

    const res = await fetch("/api/v1/inbox/status");
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

      await loadTaxonomy();
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
  btnRefreshInbox.addEventListener("click", async () => {
    const origHtml = btnRefreshInbox.innerHTML;
    btnRefreshInbox.disabled = true;
    btnRefreshInbox.innerHTML = `<span class="inbox-spin-icon">🔄</span> Prüfe...`;
    try {
      await checkInboxStatus();
      btnRefreshInbox.innerHTML = `✓ Geprüft`;
    } catch (e) {
      btnRefreshInbox.innerHTML = `⚠️ Fehler`;
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

let activeKindFilter = "all";

document.querySelectorAll("#materials-filter-bar .filter-pill").forEach((pill) => {
  pill.addEventListener("click", () => {
    document.querySelectorAll("#materials-filter-bar .filter-pill").forEach((p) => p.classList.remove("active"));
    pill.classList.add("active");
    activeKindFilter = pill.dataset.kind || "all";
    renderMaterialsList(currentMaterials);
  });
});

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

  const filtered = materials.filter((m) => {
    if (activeKindFilter === "all") return true;
    if (activeKindFilter === "Stundenplan") return (m.kind || "").includes("Stundenplan");
    if (activeKindFilter === "Arbeitsblatt") return m.kind === "Arbeitsblatt";
    if (activeKindFilter === "Hefter") return (m.kind || "").includes("Heft");
    if (activeKindFilter === "Buch") return (m.kind || "").includes("Buch");
    if (activeKindFilter === "Test") {
      const k = m.kind || "";
      return k.includes("Test") || k.includes("Klassenarbeit") || k.includes("Übung") || k.includes("Klausur");
    }
    return true;
  });

  if (filtered.length === 0) {
    const hint = activeKindFilter === "all"
      ? `Tippe oben auf <strong>„➕ Dokument hochladen“</strong> oder ziehe Schulbücher, Hefter, Arbeitsblätter oder Klassenarbeiten in deinen Finder-Netzwerkordner.`
      : `Noch keine Dokumente in der Kategorie <strong>${activeKindFilter}</strong> vorhanden.`;

    materialsList.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 36px 16px; background: rgba(255, 255, 255, 0.02); border: 1px dashed var(--border-color); border-radius: 14px; color: var(--text-secondary);">
        <span style="font-size: 2.2rem; display: block; margin-bottom: 8px;">📭</span>
        <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">Keine Dokumente gefunden</div>
        <p style="font-size: 0.85rem; max-width: 440px; margin: 0 auto;">${hint}</p>
      </div>
    `;
    return;
  }

  filtered.forEach((m) => {
    const card = document.createElement("div");
    card.className = "material-card";

    const isPdf = m.mime_type.includes("pdf");
    let docIcon = "📄";
    if (m.kind && m.kind.includes("Stundenplan")) docIcon = "📅";
    else if (m.kind && m.kind.includes("Buch")) docIcon = "📚";
    else if (m.kind && m.kind.includes("Heft")) docIcon = "📁";
    else if (m.kind && (m.kind.includes("Klassenarbeit") || m.kind.includes("Test"))) docIcon = "📝";
    else if (!isPdf) docIcon = "🖼️";
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
        ${m.kind && m.kind.includes("Stundenplan") ? `
          <button class="btn-mat-action btn-mat-tt" style="background: rgba(99, 102, 241, 0.2); border-color: var(--accent); color: var(--accent-light); font-weight: 700;" title="Als interaktives Stundenplan-Widget öffnen">
            🗓️ Stundenplan
          </button>
        ` : ""}
        <button class="btn-mat-action btn-mat-view" title="${m.kind && m.kind.includes('Stundenplan') ? 'Original-Scan als Dokument ansehen' : 'Dokument im Popup ansehen'}">
          👁️ ${m.kind && m.kind.includes('Stundenplan') ? 'Scan' : 'Öffnen'}
        </button>
        <button class="btn-mat-action btn-mat-reader" title="Im Dokument-Reader öffnen & mit Apple Pencil beschreiben">
          📖 Reader
        </button>
        <button class="btn-mat-action btn-mat-del" data-id="${m.id}" title="Material löschen">
          🗑️
        </button>
      </div>
    `;

    const ttBtn = card.querySelector(".btn-mat-tt");
    if (ttBtn) {
      ttBtn.addEventListener("click", () => {
        switchToTab("timetable");
      });
    }

    card.querySelector(".btn-mat-view").addEventListener("click", () => {
      openDocumentViewerModal(m);
    });

    const readerBtn = card.querySelector(".btn-mat-reader");
    if (readerBtn) {
      readerBtn.addEventListener("click", () => {
        openMaterialInReader(m);
      });
    }

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
const btnViewerZoomOut = document.getElementById("btn-viewer-zoom-out");
const btnViewerZoomIn = document.getElementById("btn-viewer-zoom-in");
const btnViewerZoomLabel = document.getElementById("viewer-zoom-label");
const btnViewerFitPage = document.getElementById("btn-viewer-fit-page");
const btnViewerFitWidth = document.getElementById("btn-viewer-fit-width");

let currentViewerZoomPercent = 100;

function setViewerZoomPercent(percent) {
  // Maximal 100% (volle Breite), minimal 30% (weit herausgezoomt)
  currentViewerZoomPercent = Math.min(100, Math.max(30, Math.round(percent)));
  const viewerImg = document.getElementById("viewer-img");
  const label = document.getElementById("viewer-zoom-label");
  const btnIn = document.getElementById("btn-viewer-zoom-in");
  const btnOut = document.getElementById("btn-viewer-zoom-out");

  if (viewerImg) {
    viewerImg.classList.remove("viewer-img-fitpage");
    viewerImg.classList.add("viewer-img-fullwidth");
    viewerImg.style.width = `${currentViewerZoomPercent}%`;
    viewerImg.style.maxWidth = "100%";
    viewerImg.style.height = "auto";
  }
  if (label) {
    label.textContent = `${currentViewerZoomPercent}%`;
  }
  if (btnIn) {
    btnIn.disabled = currentViewerZoomPercent >= 100;
  }
  if (btnOut) {
    btnOut.disabled = currentViewerZoomPercent <= 30;
  }
}

function fitViewerToPage() {
  const viewerImg = document.getElementById("viewer-img");
  const container = document.getElementById("viewer-content-container");
  if (!viewerImg || !container) return;

  const availHeight = container.clientHeight - 32;
  const availWidth = container.clientWidth - 32;
  if (availHeight <= 0 || availWidth <= 0) return;

  const natWidth = viewerImg.naturalWidth || 1000;
  const natHeight = viewerImg.naturalHeight || 1414;

  const targetImgWidth = availHeight * (natWidth / natHeight);
  const targetPercent = Math.round((targetImgWidth / availWidth) * 100);

  setViewerZoomPercent(targetPercent);
  container.scrollTop = 0;
}

function openDocumentViewerModal(material) {
  activeViewerMaterial = material;
  currentViewerPage = 1;
  setViewerZoomPercent(100); // Standardmäßig maximal in voller Breite!

  const titleEl = document.getElementById("viewer-doc-title");
  const badgeEl = document.getElementById("viewer-doc-badge");
  const dlBtn = document.getElementById("btn-viewer-download");
  const pagerBar = document.getElementById("viewer-pager-bar");
  const container = document.getElementById("viewer-content-container");

  if (container) container.scrollTop = 0;
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
  const spinner = document.getElementById("viewer-loading-spinner");
  const container = document.getElementById("viewer-content-container");
  const pageCount = activeViewerMaterial.page_count || 1;

  if (container) container.scrollTop = 0;
  if (pageLabel) {
    pageLabel.textContent = `Seite ${currentViewerPage} / ${pageCount}`;
  }
  if (viewerImg) {
    if (spinner) spinner.style.display = "block";
    viewerImg.style.opacity = "0.2";

    viewerImg.onload = () => {
      if (spinner) spinner.style.display = "none";
      viewerImg.style.opacity = "1";
    };
    viewerImg.onerror = () => {
      if (spinner) spinner.style.display = "none";
      viewerImg.style.opacity = "1";
    };

    viewerImg.src = `/api/v1/materials/${activeViewerMaterial.id}/preview?page=${currentViewerPage}`;

    // Nächste Seite im Hintergrund vorladen
    if (currentViewerPage < pageCount) {
      const nextPreload = new Image();
      nextPreload.src = `/api/v1/materials/${activeViewerMaterial.id}/preview?page=${currentViewerPage + 1}`;
    }
  }
}

function closeDocumentViewerModal() {
  if (modalMaterialViewer) modalMaterialViewer.style.display = "none";
  const viewerImg = document.getElementById("viewer-img");
  if (viewerImg) {
    viewerImg.src = "";
    viewerImg.onload = null;
    viewerImg.onerror = null;
  }
  const spinner = document.getElementById("viewer-loading-spinner");
  if (spinner) spinner.style.display = "none";
  activeViewerMaterial = null;
}

function openMaterialInReader(material) {
  switchToTab("books");
  const ch = {
    id: material.id,
    title: material.title,
    page_count: material.page_count || 1,
    start_page: material.start_page || 1,
    end_page: material.end_page || material.page_count || 1,
    topic_name: material.topic_name || "Material",
    focus: material.summary || "Dokumentansicht mit handschriftlichen Notizen"
  };
  openChapter(ch);
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
      openMaterialInReader(mat);
    }
  });
}

if (btnViewerZoomOut) {
  btnViewerZoomOut.addEventListener("click", () => {
    setViewerZoomPercent(currentViewerZoomPercent - 15);
  });
}

if (btnViewerZoomIn) {
  btnViewerZoomIn.addEventListener("click", () => {
    setViewerZoomPercent(currentViewerZoomPercent + 15);
  });
}

if (btnViewerZoomLabel) {
  btnViewerZoomLabel.addEventListener("click", () => {
    setViewerZoomPercent(100);
  });
}

if (btnViewerFitWidth) {
  btnViewerFitWidth.addEventListener("click", () => {
    setViewerZoomPercent(100);
    const container = document.getElementById("viewer-content-container");
    if (container) container.scrollTop = 0;
  });
}

if (btnViewerFitPage) {
  btnViewerFitPage.addEventListener("click", () => {
    fitViewerToPage();
  });
}

// Doppelklick auf Bild wechselt zwischen Ganze Seite und 100% Volle Breite
const viewerImgEl = document.getElementById("viewer-img");
if (viewerImgEl) {
  viewerImgEl.addEventListener("dblclick", () => {
    if (activeViewerMaterial) {
      if (currentViewerZoomPercent >= 90) {
        fitViewerToPage();
      } else {
        setViewerZoomPercent(100);
      }
    }
  });
}

// Mausrad mit Strg/Cmd oder Trackpad-Pinch zum stufenlosen Zoomen
const viewerContainerEl = document.getElementById("viewer-content-container");
if (viewerContainerEl) {
  viewerContainerEl.addEventListener("wheel", (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 5 : -5;
      setViewerZoomPercent(currentViewerZoomPercent + delta);
    }
  }, { passive: false });
}

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

      const res = await fetch("/api/v1/taxonomy/import-timetable", {
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
        if (newlyAddedCount > 0) {
          ttResultStatusTitle.textContent = `🎉 ${newlyAddedCount} neue(s) Schulfach/Fächer angelegt!`;
        } else {
          ttResultStatusTitle.textContent = "✅ Stundenplan erfolgreich erfasst!";
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
          docText += `<div style="margin-top: 6px; font-size: 0.8rem; color: var(--accent-light);">🔄 ${grid.wechsel_details}</div>`;
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
            pill.textContent = `✨ ${s.icon || "📚"} ${s.name || ""}`.trim();
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
              pill.textContent = `${s.icon || "📖"} ${s.name || ""}`.trim();
            } else {
              const matched = allRecognized.find((sub) => sub.name.toLowerCase() === String(s).toLowerCase());
              pill.textContent = matched ? `${matched.icon || "📖"} ${matched.name}` : `📖 ${s}`;
            }
            ttAllSubjectsList.appendChild(pill);
          });
        } else {
          ttAllSubjectsList.innerHTML = `<span style="font-size: 0.85rem; color: var(--text-secondary); font-style: italic;">Keine Fächerkürzel erkannt.</span>`;
        }
      }

      // Refresh taxonomy and materials across the whole app
      await loadTaxonomy();
      await loadMaterials();

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
    const res = await fetch(`/api/v1/timetable?week_type=${weekParam}`);
    if (!res.ok) throw new Error("Fehler beim Laden des Stundenplans.");
    currentTimetableData = await res.json();
    currentTimetableWeek = currentTimetableData.current_week_type || "A";

    // Header aktualisieren
    const subtitleEl = document.getElementById("tt-view-subtitle");
    if (subtitleEl) {
      subtitleEl.textContent = `${currentTimetableData.class_name} • ${currentTimetableData.school_name} • Schuljahr ${currentTimetableData.school_year}`;
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
  timeHeader.className = "tt-grid-header";
  timeHeader.innerHTML = `<span>Zeit / Std</span>`;
  gridEl.appendChild(timeHeader);

  weekdays.forEach((day) => {
    const dayHeader = document.createElement("div");
    const isToday = (day === todayName);
    dayHeader.className = `tt-grid-header ${isToday ? "today" : ""}`;
    dayHeader.innerHTML = `
      <span>${day}</span>
      ${isToday ? `<span class="tt-today-badge">Heute</span>` : ""}
    `;
    gridEl.appendChild(dayHeader);
  });

  // 2. Zeilen für jede Unterrichtsstunde (1 bis 8)
  const periods = currentTimetableData.periods || [];
  const slots = currentTimetableData.slots || [];

  periods.forEach((period) => {
    // A) Zeit-Zelle links
    const timeCell = document.createElement("div");
    timeCell.className = "tt-time-cell";
    timeCell.innerHTML = `
      <span class="tt-period-num">${period.label}</span>
      <span class="tt-period-time">${period.start_time}–${period.end_time}</span>
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
          slotCell.innerHTML = `
            <div class="tt-lesson-card tt-lesson-break">
              <span>🥗 ${matchingSlot.subject_name || "Mittagspause"}</span>
            </div>
          `;
        } else {
          const card = document.createElement("div");
          card.className = "tt-lesson-card";
          card.style.borderLeftColor = matchingSlot.subject_color || "var(--accent)";

          let roomStr = matchingSlot.room || "";
          if (roomStr && !roomStr.toLowerCase().includes("halle") && !roomStr.startsWith("R")) {
            roomStr = `R ${roomStr}`;
          }

          card.innerHTML = `
            <div class="tt-lesson-top">
              <span class="tt-lesson-name" title="${matchingSlot.subject_name}">
                ${matchingSlot.subject_icon || "📚"} ${matchingSlot.subject_name}
              </span>
              ${matchingSlot.subject_code ? `<span class="tt-lesson-code">${matchingSlot.subject_code}</span>` : ""}
            </div>
            <div class="tt-lesson-meta">
              <span class="tt-lesson-room">${roomStr}</span>
              <span class="tt-lesson-teacher">${matchingSlot.teacher || ""}</span>
              ${matchingSlot.week_type !== "both" ? `<span class="tt-tag-turnus">${matchingSlot.week_type}-Woche</span>` : ""}
            </div>
          `;

          card.addEventListener("click", () => {
            openTimetableSlotDetailModal(matchingSlot, period);
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

  if (iconEl) iconEl.textContent = slot.subject_icon || "📚";
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
    const res = await fetch("/api/v1/timetable/today");
    if (!res.ok) throw new Error("Fehler beim Laden des Tagesplans.");
    const data = await res.json();

    const titleEl = document.getElementById("dash-tt-day-title");
    const weekPill = document.getElementById("dash-tt-week-pill");

    if (titleEl) {
      titleEl.textContent = data.is_weekend
        ? `Dein Schultag am Montag (Wochenende frei! 🌴)`
        : `Dein Schultag heute (${data.day})`;
    }
    if (weekPill) {
      weekPill.textContent = `${data.active_week === "A" ? "🅰️" : "🅱️"} ${data.active_week}-Woche`;
    }

    container.innerHTML = "";
    const lessons = (data.lessons || []).filter((l) => !l.is_break);

    if (lessons.length === 0) {
      container.innerHTML = `<div class="dash-tt-empty">Heute kein regulärer Unterricht eingetragen. 🎉</div>`;
      return;
    }

    lessons.forEach((l) => {
      const card = document.createElement("div");
      card.className = "dash-tt-slot-card";
      card.style.borderLeftColor = l.subject_color || "var(--accent)";

      let roomStr = l.room || "";
      if (roomStr && !roomStr.toLowerCase().includes("halle") && !roomStr.startsWith("R")) {
        roomStr = `R ${roomStr}`;
      }

      card.innerHTML = `
        <div class="dash-tt-slot-time">${l.period_label || l.period + '. Std'} • ${l.start_time || ""}</div>
        <div class="dash-tt-slot-subject">
          <span>${l.subject_icon || "📚"}</span>
          <span>${l.subject_name}</span>
        </div>
        <div class="dash-tt-slot-meta">
          <span>${roomStr}</span>
          <span>${l.teacher || ""}</span>
        </div>
      `;

      card.addEventListener("click", () => {
        switchToTab("timetable");
      });

      container.appendChild(card);
    });
  } catch (err) {
    console.error("Fehler beim Laden des Dashboard-Stundenplans:", err);
  }
}

async function viewMaterialById(matId) {
  try {
    const res = await fetch(`/api/v1/materials/${matId}`);
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
    switchToTab("subjects");
    if (sId) {
      const filterPills = document.querySelectorAll(".filter-pill");
      filterPills.forEach((p) => p.classList.remove("active"));
      const allPill = document.querySelector('.filter-pill[data-kind="all"]');
      if (allPill) allPill.classList.add("active");
      activeKindFilter = "all";
      const subCards = document.querySelectorAll(".subject-detail-card");
      subCards.forEach((c) => {
        if (c.dataset.subjectId === sId) {
          c.scrollIntoView({ behavior: "smooth", block: "start" });
          c.style.boxShadow = "0 0 15px rgba(99, 102, 241, 0.6)";
          setTimeout(() => { c.style.boxShadow = ""; }, 2000);
        }
      });
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

// ==========================================================================
// 📖 BÜCHER-BROWSER LOGIK (#tab-books)
// ==========================================================================

let currentBooks = [];
let activeBookId = null;
let activeBookDetail = null;
let activeChapter = null;
let currentChapterPage = 1;
let bookZoomMode = "width"; // Standard: Volle Dokumentbreite (100% Breite)

async function loadBooks() {
  try {
    const res = await fetch("/api/v1/books");
    if (!res.ok) return;
    currentBooks = await res.json();
    renderBooksShelf();

    if (currentBooks.length > 0) {
      if (!activeBookId || !currentBooks.some(b => b.id === activeBookId)) {
        await selectBook(currentBooks[0].id);
      }
    }
  } catch (err) {
    console.error("Fehler beim Laden der Schulbücher:", err);
  }
}

function renderBooksShelf() {
  const container = document.getElementById("books-shelf-selector");
  if (!container) return;
  container.innerHTML = "";

  currentBooks.forEach((book) => {
    const card = document.createElement("div");
    card.className = `shelf-book-card ${book.id === activeBookId ? "active" : ""}`;
    card.dataset.bookId = book.id;
    card.innerHTML = `
      <span class="shelf-book-icon">${book.subject_icon || "📚"}</span>
      <div class="shelf-book-meta">
        <span class="shelf-book-title">${escapeHtml(book.title)}</span>
        <span class="shelf-book-sub">${book.chapters_count} Lerneinheiten • ${book.total_pages} Seiten</span>
      </div>
    `;
    card.addEventListener("click", () => selectBook(book.id));
    container.appendChild(card);
  });
}

async function selectBook(bookId) {
  activeBookId = bookId;
  renderBooksShelf();

  try {
    const res = await fetch(`/api/v1/books/${bookId}`);
    if (!res.ok) return;
    activeBookDetail = await res.json();

    // Katalog-Header befüllen
    const iconEl = document.getElementById("catalog-book-icon");
    const titleEl = document.getElementById("catalog-book-title");
    const subEl = document.getElementById("catalog-book-subtitle");
    const drawerSubEl = document.getElementById("drawer-book-subtitle");

    if (iconEl) iconEl.textContent = activeBookDetail.subject_icon || "📚";
    if (titleEl) titleEl.textContent = activeBookDetail.title;
    if (subEl) subEl.textContent = `${activeBookDetail.chapters_count} Lerneinheiten • ${activeBookDetail.total_pages} Seiten`;
    if (drawerSubEl) drawerSubEl.textContent = activeBookDetail.title;

    // Standardmäßig Katalog anzeigen (oder Reader aktualisieren falls bereits geöffnet)
    const readerView = document.getElementById("book-reader-view");
    const isReaderOpen = readerView && readerView.style.display !== "none";

    renderBookCatalog();
    renderDrawerTOC();

    if (isReaderOpen && activeChapter) {
      // Wenn das Buch gewechselt wurde während der Reader offen war, erstes Kapitel des neuen Buchs laden
      const chaps = activeBookDetail.chapters || [];
      const newChap = chaps.find(c => c.id === activeChapter.id) || (chaps.find(c => c.chapter_number === 1) || chaps[0]);
      if (newChap) openChapter(newChap);
    }
  } catch (err) {
    console.error("Fehler beim Abruf der Buch-Details:", err);
  }
}

// Ansicht 1: Übersicht aller Kapitel / Lerneinheiten als Kacheln
function renderBookCatalog(filterTerm = "") {
  const container = document.getElementById("book-catalog-grid");
  if (!container || !activeBookDetail) return;
  container.innerHTML = "";

  const term = (filterTerm || "").toLowerCase().trim();
  const chapters = (activeBookDetail.chapters || []).filter((ch) => {
    if (!term) return true;
    return (
      ch.title.toLowerCase().includes(term) ||
      (ch.topic_name && ch.topic_name.toLowerCase().includes(term)) ||
      (ch.focus && ch.focus.toLowerCase().includes(term))
    );
  });

  if (chapters.length === 0) {
    container.innerHTML = `<div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted); font-size: 0.95rem; background: var(--bg-card); border-radius: 14px; border: 1px solid var(--border-color);">Keine Lerneinheiten für "${escapeHtml(filterTerm)}" gefunden.</div>`;
    return;
  }

  chapters.forEach((ch) => {
    const card = document.createElement("div");
    card.className = "catalog-chapter-card";
    card.dataset.chapterId = ch.id;

    const unitLabel = ch.chapter_number === 0 ? "Titelei" : `Einheit ${ch.chapter_number}`;
    card.innerHTML = `
      <div class="catalog-card-header">
        <span class="catalog-badge">${unitLabel}</span>
        <span class="catalog-pages">S. ${ch.start_page}–${ch.end_page} (${ch.page_count} Seiten)</span>
      </div>
      <div class="catalog-card-title">${escapeHtml(ch.title)}</div>
      ${ch.topic_name ? `<div class="catalog-card-topic"><span>📐</span> ${escapeHtml(ch.topic_name)}</div>` : ""}
      <div class="catalog-card-focus">${escapeHtml(ch.focus || "Lerneinheit aus dem Schulbuch.")}</div>
      <div class="catalog-card-footer">
        <span>Kapitel aufschlagen</span> <span>📖 ➔</span>
      </div>
    `;
    card.addEventListener("click", () => openChapter(ch));
    container.appendChild(card);
  });
}

// Ansicht 2: Vollbreiten-Reader für ein gewähltes Kapitel öffnen
function openChapter(ch) {
  if (!ch) return;
  activeChapter = ch;
  currentChapterPage = 1;

  // Umschalten auf Reader-Ansicht
  const catalogView = document.getElementById("book-catalog-view");
  const readerView = document.getElementById("book-reader-view");
  if (catalogView) catalogView.style.display = "none";
  if (readerView) readerView.style.display = "flex";

  // Breadcrumbs & Header
  const bcBook = document.getElementById("bc-book-name");
  const bcChap = document.getElementById("bc-chapter-name");
  if (bcBook && activeBookDetail) bcBook.textContent = activeBookDetail.title;
  if (bcChap) bcChap.textContent = ch.title;

  const badgeEl = document.getElementById("reader-chapter-badge");
  const titleEl = document.getElementById("reader-chapter-title");
  const topicEl = document.getElementById("reader-chapter-topic");
  const pagesEl = document.getElementById("reader-chapter-pages");
  const focusEl = document.getElementById("reader-chapter-focus");
  const downloadBtn = document.getElementById("btn-book-download-pdf");

  if (badgeEl) badgeEl.textContent = ch.chapter_number === 0 ? "Titelei" : `Einheit ${ch.chapter_number}`;
  if (titleEl) titleEl.textContent = ch.title;
  if (topicEl) topicEl.textContent = `📐 ${ch.topic_name || "Mathematik 7"}`;
  if (pagesEl) pagesEl.textContent = `S. ${ch.start_page} – ${ch.end_page} (${ch.page_count} Seiten)`;
  if (focusEl) focusEl.textContent = ch.focus || "Lerneinheit aus dem Schulbuch.";
  if (downloadBtn) {
    downloadBtn.href = ch.file_url;
    downloadBtn.setAttribute("download", ch.filename);
  }

  // Vorh. / Nächste Einheit Buttons aktualisieren
  updateChapterNavButtons();

  // Drawer aktiv markieren
  updateDrawerActiveState();

  // Drawer schließen falls offen
  closeTOCDrawer();

  // Seiten-Pills & erste Seite anzeigen
  renderBookPageStrip();
  renderChapterPage();

  // Nach oben scrollen für optimales Leseerlebnis
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function closeReaderToCatalog() {
  if (bookSaveTimer) {
    saveCurrentBookAnnotations();
  }
  const catalogView = document.getElementById("book-catalog-view");
  const readerView = document.getElementById("book-reader-view");
  if (readerView) readerView.style.display = "none";
  if (catalogView) catalogView.style.display = "flex";
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
    openChapter(chaps[targetIdx]);
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
    return (
      ch.title.toLowerCase().includes(term) ||
      (ch.topic_name && ch.topic_name.toLowerCase().includes(term))
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
    item.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span class="catalog-badge">${unitLabel}</span>
        <span style="font-size: 0.74rem; color: var(--text-muted); font-weight: 600;">S. ${ch.start_page}–${ch.end_page}</span>
      </div>
      <div style="font-size: 0.92rem; font-weight: 700; color: var(--text-primary);">${escapeHtml(ch.title)}</div>
      ${ch.topic_name ? `<div style="font-size: 0.76rem; color: #94a3b8;">📐 ${escapeHtml(ch.topic_name)}</div>` : ""}
    `;
    item.addEventListener("click", () => openChapter(ch));
    container.appendChild(item);
  });
}

function updateDrawerActiveState() {
  document.querySelectorAll(".drawer-chapter-item").forEach((it) => {
    it.classList.toggle("active", activeChapter && it.dataset.chapterId === activeChapter.id);
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

  // Wenn noch ein Autosave der vorherigen Seite aussteht, sofort speichern
  if (bookSaveTimer) {
    await saveCurrentBookAnnotations();
  }

  const counterEl = document.getElementById("book-page-counter");
  const prevBtn = document.getElementById("btn-book-prev-page");
  const nextBtn = document.getElementById("btn-book-next-page");
  const imgEl = document.getElementById("book-page-img");
  const loadingEl = document.getElementById("book-page-loading");

  const absPage = activeChapter.start_page + currentChapterPage - 1;
  if (counterEl) {
    counterEl.innerHTML = `Seite ${currentChapterPage} von ${activeChapter.page_count} <small id="book-page-absolute">(Buchseite ${absPage})</small>`;
  }

  if (prevBtn) prevBtn.disabled = currentChapterPage <= 1;
  if (nextBtn) nextBtn.disabled = currentChapterPage >= activeChapter.page_count;

  // Aktive Pill markieren und ins Sichtfeld scrollen (nur wenn Bücher-Tab aktiv ist)
  document.querySelectorAll(".book-page-pill").forEach((pill) => {
    const isAct = parseInt(pill.dataset.page, 10) === currentChapterPage;
    pill.classList.toggle("active", isAct);
    if (isAct) {
      const booksTab = document.getElementById("tab-books");
      if (booksTab && booksTab.classList.contains("active")) {
        try {
          pill.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
        } catch (e) {
          pill.scrollIntoView();
        }
      }
    }
  });

  // Bild in voller Breite laden
  if (imgEl) {
    if (loadingEl) loadingEl.style.display = "flex";
    imgEl.className = `book-page-img mode-${bookZoomMode}`;
    const targetUrl = `/api/v1/materials/${activeChapter.id}/preview?page=${currentChapterPage}`;

    const onImageLoaded = () => {
      if (loadingEl) loadingEl.style.display = "none";
      syncBookAnnotationCanvasSize();
      loadBookAnnotations(activeChapter.id, currentChapterPage);
    };

    imgEl.onload = onImageLoaded;
    imgEl.onerror = () => {
      if (loadingEl) loadingEl.style.display = "none";
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
    fetch(`/api/v1/materials/${activeChapter.id}/prefetch?page=${p}`, {
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

  // Seiten-Navigation Buttons
  const prevBtn = document.getElementById("btn-book-prev-page");
  const nextBtn = document.getElementById("btn-book-next-page");

  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (activeChapter && currentChapterPage > 1) {
        currentChapterPage--;
        renderChapterPage();
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (activeChapter && currentChapterPage < activeChapter.page_count) {
        currentChapterPage++;
        renderChapterPage();
      }
    });
  }

  // Zoom Fit / Width Umschalter
  const zoomFitBtn = document.getElementById("btn-book-zoom-fit");
  const zoomWidthBtn = document.getElementById("btn-book-zoom-width");
  const imgEl = document.getElementById("book-page-img");

  if (zoomFitBtn) {
    zoomFitBtn.addEventListener("click", () => {
      bookZoomMode = "fit";
      zoomFitBtn.classList.add("active");
      if (zoomWidthBtn) zoomWidthBtn.classList.remove("active");
      if (imgEl) imgEl.className = "book-page-img mode-fit";
      setTimeout(syncBookAnnotationCanvasSize, 220);
    });
  }

  if (zoomWidthBtn) {
    zoomWidthBtn.addEventListener("click", () => {
      bookZoomMode = "width";
      zoomWidthBtn.classList.add("active");
      if (zoomFitBtn) zoomFitBtn.classList.remove("active");
      if (imgEl) imgEl.className = "book-page-img mode-width";
      setTimeout(syncBookAnnotationCanvasSize, 220);
    });
  }

  // Inking Engine starten
  initBookInking();
}

// ====================================================================
// Handschrift- & Notizen-Engine im Dokument-/Buch-Reader (Apple Pencil / Touch)
// ====================================================================
let bookAnnotationCanvas = null;
let bookAnnotationCtx = null;
let bookAnnotationStrokes = []; // Array von { id, tool, color, width, points: [{x, y, p}] }
let bookUndoStack = [];
let currentBookStroke = null;
let currentBookTool = "pen"; // "pen", "highlighter", "eraser"
let currentBookColor = "#2563eb";
let bookPenOnlyMode = true; // STANDARD: TRUE! Nur Apple Pencil (oder Maus) zeichnet, Handballenschutz aktiv
let bookSaveTimer = null;
let isBookDrawing = false;
let activeBookPointerId = null;
let bookActiveTouches = new Map();
let bookAnnotationLoadedKey = null;
let currentBookAnnotationMaterialId = null;
let currentBookAnnotationPage = null;
let lastBookScreenPoint = null;
let bookCanvasRect = null;
let currentBookSmoothWidth = 3.5;

function initBookInking() {
  bookAnnotationCanvas = document.getElementById("book-annotation-canvas");
  if (!bookAnnotationCanvas) return;
  try {
    bookAnnotationCtx = bookAnnotationCanvas.getContext("2d", { desynchronized: true });
  } catch (_) {
    bookAnnotationCtx = bookAnnotationCanvas.getContext("2d");
  }

  // Nur-Stift / Handballenschutz Umschalter
  const btnPenOnly = document.getElementById("btn-book-pen-only");
  if (btnPenOnly) {
    btnPenOnly.addEventListener("click", () => {
      bookPenOnlyMode = !bookPenOnlyMode;
      btnPenOnly.classList.toggle("active", bookPenOnlyMode);
    });
  }

  // Werkzeug-Buttons (Stift, Marker, Radierer)
  document.querySelectorAll(".btn-ink-tool").forEach((btn) => {
    if (btn.id === "btn-book-pen-only") return;
    btn.addEventListener("click", () => {
      document.querySelectorAll(".btn-ink-tool").forEach((b) => {
        if (b.id !== "btn-book-pen-only") b.classList.remove("active");
      });
      btn.classList.add("active");
      currentBookTool = btn.dataset.tool;
    });
  });

  // Farb-Buttons
  document.querySelectorAll(".ink-color-dot").forEach((dot) => {
    dot.addEventListener("click", () => {
      document.querySelectorAll(".ink-color-dot").forEach((d) => d.classList.remove("active"));
      dot.classList.add("active");
      currentBookColor = dot.dataset.color;
      if (currentBookTool === "eraser") {
        currentBookTool = "pen";
        document.querySelectorAll(".btn-ink-tool").forEach((b) => {
          if (b.id !== "btn-book-pen-only") {
            b.classList.toggle("active", b.dataset.tool === "pen");
          }
        });
      }
    });
  });

  // Undo Button
  const undoBtn = document.getElementById("btn-book-ink-undo");
  if (undoBtn) {
    undoBtn.addEventListener("click", undoBookStroke);
  }

  // Clear Button
  const clearBtn = document.getElementById("btn-book-ink-clear");
  if (clearBtn) {
    clearBtn.addEventListener("click", clearBookAnnotations);
  }

  // 100% Unterdrückung des iOS Safari 'Teilen...' Menüs und nativer Gesten
  const blockNativeGesture = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  bookAnnotationCanvas.addEventListener("contextmenu", blockNativeGesture, { capture: true });
  const stage = document.getElementById("book-page-stage");
  if (stage) stage.addEventListener("contextmenu", blockNativeGesture, { capture: true });
  const wrapper = document.getElementById("book-page-canvas-wrapper");
  if (wrapper) wrapper.addEventListener("contextmenu", blockNativeGesture, { capture: true });

  bookAnnotationCanvas.addEventListener("gesturestart", (e) => e.preventDefault(), { passive: false, capture: true });
  bookAnnotationCanvas.addEventListener("gesturechange", (e) => e.preventDefault(), { passive: false, capture: true });
  bookAnnotationCanvas.addEventListener("gestureend", (e) => e.preventDefault(), { passive: false, capture: true });

  // 1:1 Handballenschutz wie Whiteboard: Nur genau 2 Finger scrollen, 1 Finger/Handballen tut NICHTS!
  let twoFingerTouchStartY = null;
  let twoFingerScrollStartTop = 0;

  const handleTwoFingerTouchStart = (e) => {
    e.preventDefault();
    if (e.touches.length === 2) {
      if (isBookDrawing) {
        cancelCurrentBookStroke();
      }
      const wrap = document.getElementById("book-page-canvas-wrapper");
      if (wrap) {
        twoFingerTouchStartY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        twoFingerScrollStartTop = wrap.scrollTop;
      }
    } else {
      twoFingerTouchStartY = null;
    }
  };

  const handleTwoFingerTouchMove = (e) => {
    e.preventDefault();
    if (e.touches.length === 2 && twoFingerTouchStartY !== null) {
      const wrap = document.getElementById("book-page-canvas-wrapper");
      if (wrap) {
        const currentMidY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        const dy = currentMidY - twoFingerTouchStartY;
        wrap.scrollTop = twoFingerScrollStartTop - dy;
      }
    }
  };

  const handleTwoFingerTouchEnd = (e) => {
    e.preventDefault();
    if (e.touches.length < 2) {
      twoFingerTouchStartY = null;
    }
  };

  bookAnnotationCanvas.addEventListener("touchstart", handleTwoFingerTouchStart, { passive: false, capture: true });
  bookAnnotationCanvas.addEventListener("touchmove", handleTwoFingerTouchMove, { passive: false, capture: true });
  bookAnnotationCanvas.addEventListener("touchend", handleTwoFingerTouchEnd, { passive: false, capture: true });
  bookAnnotationCanvas.addEventListener("touchcancel", handleTwoFingerTouchEnd, { passive: false, capture: true });

  if (wrapper) {
    wrapper.addEventListener("touchstart", handleTwoFingerTouchStart, { passive: false, capture: true });
    wrapper.addEventListener("touchmove", handleTwoFingerTouchMove, { passive: false, capture: true });
    wrapper.addEventListener("touchend", handleTwoFingerTouchEnd, { passive: false, capture: true });
    wrapper.addEventListener("touchcancel", handleTwoFingerTouchEnd, { passive: false, capture: true });
  }

  // Pointer Events auf Canvas für Apple Pencil & Touch
  bookAnnotationCanvas.addEventListener("pointerdown", onBookPointerDown, { passive: false });
  bookAnnotationCanvas.addEventListener("pointermove", onBookPointerMove, { passive: false });
  bookAnnotationCanvas.addEventListener("pointerup", onBookPointerUp, { passive: false });
  bookAnnotationCanvas.addEventListener("pointercancel", onBookPointerUp, { passive: false });

  window.addEventListener("resize", () => {
    syncBookAnnotationCanvasSize();
  });
}

function onBookPointerDown(e) {
  if (!bookAnnotationCanvas) return;
  e.preventDefault();

  // 1. PALM REJECTION: Wenn 'Nur Stift' aktiv ist und ein Touch (Finger / Handballen) berührt:
  if (bookPenOnlyMode && e.pointerType === "touch") {
    // Handballenschutz: Berührung mit Finger oder Handballen wird ignoriert, KEIN Scrollen & KEIN Malen!
    return;
  }

  // Multi-Touch-Handling falls Palm Rejection aus ist
  if (e.pointerType === "touch") {
    bookActiveTouches.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (bookActiveTouches.size >= 2) {
      if (isBookDrawing) {
        cancelCurrentBookStroke();
      }
      return;
    }
  }

  // Wenn bereits mit Stift gezeichnet wird und ein Handballen-Touch ankommt: Touch ignorieren
  if (isBookDrawing && activeBookPointerId !== null && e.pointerType === "touch") {
    return;
  }

  bookCanvasRect = bookAnnotationCanvas.getBoundingClientRect();
  const rect = bookCanvasRect;
  if (rect.width === 0 || rect.height === 0) return;

  const screenX = e.clientX - rect.left;
  const screenY = e.clientY - rect.top;
  const normX = Math.max(0, Math.min(1, screenX / rect.width));
  const normY = Math.max(0, Math.min(1, screenY / rect.height));
  const pressure = (typeof e.pressure === "number" && e.pressure > 0) ? e.pressure : 0.5;

  isBookDrawing = true;
  activeBookPointerId = e.pointerId;
  try {
    bookAnnotationCanvas.setPointerCapture(e.pointerId);
  } catch (_) {}

  if (currentBookTool === "eraser") {
    eraseBookStrokesAt(normX, normY, 24 / rect.width);
    return;
  }

  const baseWidth = currentBookTool === "highlighter" ? 18 : 2.6;
  let strokeColor = currentBookColor;
  if (currentBookTool === "highlighter" && (strokeColor === "#2563eb" || strokeColor === "#0f172a")) {
    strokeColor = "#facc15";
  }

  currentBookStroke = {
    id: "str_" + Date.now() + "_" + Math.floor(Math.random() * 10000),
    tool: currentBookTool,
    color: strokeColor,
    width: baseWidth,
    points: [{ x: normX, y: normY }]
  };

  bookAnnotationStrokes.push(currentBookStroke);
  bookUndoStack.push({ type: "add", stroke: currentBookStroke });

  // Styles vorbereiten (source-over für maximale Performance ohne GPU-Readback)
  const ctx = bookAnnotationCtx;
  if (ctx) {
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.globalCompositeOperation = "source-over";
    ctx.lineWidth = baseWidth;

    if (currentBookTool === "highlighter") {
      ctx.globalAlpha = 0.35;
      ctx.strokeStyle = strokeColor;
      ctx.fillStyle = strokeColor;
    } else {
      ctx.globalAlpha = 1.0;
      ctx.strokeStyle = strokeColor;
      ctx.fillStyle = strokeColor;
    }

    // Sofortiger Startpunkt direkt im Displaybuffer
    ctx.beginPath();
    const dotR = Math.max(0.5, baseWidth / 2);
    ctx.arc(screenX, screenY, dotR, 0, Math.PI * 2);
    ctx.fill();
  }

  lastBookScreenPoint = { x: screenX, y: screenY };
}

function onBookPointerMove(e) {
  if (bookPenOnlyMode && e.pointerType === "touch") return;
  if (!isBookDrawing || e.pointerId !== activeBookPointerId) return;
  e.preventDefault();

  const rect = bookCanvasRect || bookAnnotationCanvas.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;

  // Apple Pencil Coalesced Events für maximale Präzision (240Hz iPad Pro)
  const events = (e.getCoalescedEvents && e.getCoalescedEvents().length > 0)
    ? e.getCoalescedEvents()
    : [e];

  if (currentBookTool === "eraser") {
    for (let i = 0; i < events.length; i++) {
      const ev = events[i];
      const normX = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
      const normY = Math.max(0, Math.min(1, (ev.clientY - rect.top) / rect.height));
      eraseBookStrokesAt(normX, normY, 24 / rect.width);
    }
    return;
  }

  if (!currentBookStroke || !lastBookScreenPoint) return;
  const ctx = bookAnnotationCtx;
  if (!ctx) return;

  // Konstante Strichstärke (Fineliner-Modus):
  // Keine dynamischen lineWidth-Mutationen pro Teilstück.
  // Alle 240Hz Coalesced Sub-Events werden in einem einzigen hardware-beschleunigten GPU-Pfad gezeichnet.
  ctx.beginPath();
  ctx.moveTo(lastBookScreenPoint.x, lastBookScreenPoint.y);

  for (let i = 0; i < events.length; i++) {
    const ev = events[i];
    const screenX = ev.clientX - rect.left;
    const screenY = ev.clientY - rect.top;
    const normX = Math.max(0, Math.min(1, screenX / rect.width));
    const normY = Math.max(0, Math.min(1, screenY / rect.height));

    currentBookStroke.points.push({ x: normX, y: normY });
    ctx.lineTo(screenX, screenY);
    lastBookScreenPoint = { x: screenX, y: screenY };
  }

  ctx.stroke();
}

function onBookPointerUp(e) {
  if (e.pointerType === "touch") {
    bookActiveTouches.delete(e.pointerId);
  }
  if (bookPenOnlyMode && e.pointerType === "touch") return;

  if (isBookDrawing && e.pointerId === activeBookPointerId) {
    isBookDrawing = false;
    activeBookPointerId = null;
    lastBookScreenPoint = null;
    bookCanvasRect = null;
    try {
      if (bookAnnotationCanvas.hasPointerCapture(e.pointerId)) {
        bookAnnotationCanvas.releasePointerCapture(e.pointerId);
      }
    } catch (_) {}

    currentBookStroke = null;
    scheduleBookAnnotationSave();
  }
}

function cancelCurrentBookStroke() {
  if (currentBookStroke) {
    bookAnnotationStrokes = bookAnnotationStrokes.filter((s) => s.id !== currentBookStroke.id);
    bookUndoStack = bookUndoStack.filter((a) => !(a.type === "add" && a.stroke.id === currentBookStroke.id));
    currentBookStroke = null;
    redrawBookAnnotations();
  }
  isBookDrawing = false;
  activeBookPointerId = null;
  lastBookScreenPoint = null;
  bookCanvasRect = null;
}

function eraseBookStrokesAt(normX, normY, radiusNorm) {
  if (bookAnnotationStrokes.length === 0) return;
  const remaining = [];
  const removed = [];

  for (const stroke of bookAnnotationStrokes) {
    let hit = false;
    for (const pt of stroke.points) {
      const dx = pt.x - normX;
      const dy = pt.y - normY;
      if (Math.sqrt(dx * dx + dy * dy) < radiusNorm) {
        hit = true;
        break;
      }
    }
    if (hit) {
      removed.push(stroke);
    } else {
      remaining.push(stroke);
    }
  }

  if (removed.length > 0) {
    bookAnnotationStrokes = remaining;
    bookUndoStack.push({ type: "delete", strokes: removed });
    redrawBookAnnotations();
    scheduleBookAnnotationSave();
  }
}

function undoBookStroke() {
  if (bookUndoStack.length === 0) return;
  const action = bookUndoStack.pop();
  if (action.type === "add") {
    bookAnnotationStrokes = bookAnnotationStrokes.filter((s) => s.id !== action.stroke.id);
  } else if (action.type === "delete") {
    bookAnnotationStrokes.push(...action.strokes);
  } else if (action.type === "clear") {
    bookAnnotationStrokes = action.strokes;
  }
  redrawBookAnnotations();
  scheduleBookAnnotationSave();
}

function clearBookAnnotations() {
  if (bookAnnotationStrokes.length === 0) return;
  if (!confirm("Möchtest du alle handschriftlichen Notizen auf dieser Seite löschen?")) return;
  bookUndoStack.push({ type: "clear", strokes: [...bookAnnotationStrokes] });
  bookAnnotationStrokes = [];
  redrawBookAnnotations();
  scheduleBookAnnotationSave();
}

function syncBookAnnotationCanvasSize() {
  const imgEl = document.getElementById("book-page-img");
  const canvas = document.getElementById("book-annotation-canvas");
  if (!imgEl || !canvas) return;

  const w = imgEl.clientWidth;
  const h = imgEl.clientHeight;
  if (w === 0 || h === 0) return;

  const dpr = window.devicePixelRatio || 1;
  const targetPixelW = Math.round(w * dpr);
  const targetPixelH = Math.round(h * dpr);

  if (canvas.width !== targetPixelW || canvas.height !== targetPixelH) {
    canvas.width = targetPixelW;
    canvas.height = targetPixelH;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    const ctx = bookAnnotationCtx || canvas.getContext("2d");
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  bookCanvasRect = null;
  redrawBookAnnotations();
}

function redrawBookAnnotations() {
  const canvas = document.getElementById("book-annotation-canvas");
  if (!canvas) return;
  const ctx = bookAnnotationCtx || canvas.getContext("2d");
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const cssW = canvas.clientWidth || (canvas.width / dpr);
  const cssH = canvas.clientHeight || (canvas.height / dpr);
  if (cssW === 0 || cssH === 0) return;

  for (const stroke of bookAnnotationStrokes) {
    if (!stroke.points || stroke.points.length === 0) continue;

    if (stroke.tool === "highlighter") {
      ctx.globalAlpha = 0.38;
      ctx.globalCompositeOperation = "multiply";
      ctx.strokeStyle = stroke.color || "#facc15";
      ctx.lineWidth = stroke.width || 22;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      ctx.beginPath();
      const first = stroke.points[0];
      ctx.moveTo(first.x * cssW, first.y * cssH);
      for (let i = 1; i < stroke.points.length; i++) {
        const pt = stroke.points[i];
        ctx.lineTo(pt.x * cssW, pt.y * cssH);
      }
      ctx.stroke();
    } else {
      ctx.globalAlpha = 1.0;
      ctx.globalCompositeOperation = "source-over";
      ctx.strokeStyle = stroke.color || "#2563eb";
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      const baseWidth = stroke.width || 2.6;
      if (stroke.points.length === 1) {
        const pt = stroke.points[0];
        const r = Math.max(0.5, baseWidth / 2);
        ctx.fillStyle = stroke.color || "#2563eb";
        ctx.beginPath();
        ctx.arc(pt.x * cssW, pt.y * cssH, r, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.beginPath();
        const p0 = stroke.points[0];
        ctx.moveTo(p0.x * cssW, p0.y * cssH);
        for (let i = 1; i < stroke.points.length; i++) {
          const pt = stroke.points[i];
          ctx.lineTo(pt.x * cssW, pt.y * cssH);
        }
        ctx.lineWidth = baseWidth;
        ctx.stroke();
      }
    }
  }
}

function setBookSaveStatus(status) {
  const el = document.getElementById("book-ink-save-status");
  if (!el) return;
  if (status === "saving") {
    el.textContent = "⏳ Speichert...";
    el.className = "ink-save-status saving";
  } else if (status === "saved") {
    el.textContent = "✓ Gespeichert";
    el.className = "ink-save-status";
  } else if (status === "error") {
    el.textContent = "⚠ Fehler";
    el.className = "ink-save-status saving";
  }
}

function scheduleBookAnnotationSave() {
  clearTimeout(bookSaveTimer);
  setBookSaveStatus("saving");
  bookSaveTimer = setTimeout(() => {
    saveCurrentBookAnnotations();
  }, 600);
}

async function saveCurrentBookAnnotations() {
  const matId = currentBookAnnotationMaterialId || (activeChapter ? activeChapter.id : null);
  const pageNum = currentBookAnnotationPage !== null ? currentBookAnnotationPage : currentChapterPage;
  if (!matId || !pageNum) return;

  clearTimeout(bookSaveTimer);
  bookSaveTimer = null;

  try {
    const payload = {
      material_id: matId,
      page_number: pageNum,
      strokes: bookAnnotationStrokes,
      strokes_json: JSON.stringify(bookAnnotationStrokes)
    };
    const res = await fetch(`/api/v1/materials/${matId}/pages/${pageNum}/annotations`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      setBookSaveStatus("saved");
    } else {
      setBookSaveStatus("error");
      const errText = await res.text();
      console.error("Fehler beim Speichern der Notizen:", res.status, errText);
    }
  } catch (err) {
    console.error("Fehler beim Speichern der Notizen:", err);
    setBookSaveStatus("error");
  }
}

async function loadBookAnnotations(materialId, pageNum) {
  clearTimeout(bookSaveTimer);
  bookSaveTimer = null;

  currentBookAnnotationMaterialId = materialId;
  currentBookAnnotationPage = pageNum;

  bookAnnotationStrokes = [];
  bookUndoStack = [];
  redrawBookAnnotations();

  const key = `${materialId}_${pageNum}`;
  bookAnnotationLoadedKey = key;

  try {
    const res = await fetch(`/api/v1/materials/${materialId}/pages/${pageNum}/annotations`);
    if (res.ok) {
      const data = await res.json();
      if (bookAnnotationLoadedKey === key) {
        let loaded = [];
        if (Array.isArray(data.strokes) && data.strokes.length > 0) {
          loaded = data.strokes;
        } else if (data.strokes_json) {
          try {
            loaded = JSON.parse(data.strokes_json) || [];
          } catch (e) {
            loaded = [];
          }
        }
        bookAnnotationStrokes = loaded;
        redrawBookAnnotations();
        setBookSaveStatus("saved");
      }
    } else {
      console.warn("Laden der Annotationen HTTP Status:", res.status);
    }
  } catch (err) {
    console.error("Fehler beim Laden der Notizen:", err);
  }
}

// Init
async function initApp() {
  const safeRun = async (fn, name) => {
    try {
      await fn();
    } catch (err) {
      console.error(`Init error in ${name}:`, err);
    }
  };

  await safeRun(checkEnvironment, "checkEnvironment");
  await safeRun(loadProfile, "loadProfile");
  await safeRun(loadTaxonomy, "loadTaxonomy");
  await safeRun(loadPlan, "loadPlan");
  await safeRun(loadMaterials, "loadMaterials");
  await safeRun(checkInboxStatus, "checkInboxStatus");
  await safeRun(loadTodayDashboardWidget, "loadTodayDashboardWidget");
  await safeRun(loadTimetable, "loadTimetable");
  await safeRun(loadBooks, "loadBooks");
  safeRun(setupBookBrowserEvents, "setupBookBrowserEvents");
  safeRun(connectWebSocket, "connectWebSocket");
}

initApp();
