// 6. Lernplan & Countdown laden
async function loadPlan() {
  try {
    const res = await apiFetch("/api/v1/plan");
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
            <button class="btn-del-test parent-only" data-id="${t.id}">Löschen</button>
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
    await apiFetch("/api/v1/plan/complete-task", {
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
    const res = await apiFetch(`/api/v1/tests/${testId}`, { method: "DELETE" });
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

  const res = await apiFetch("/api/v1/tests", {
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

  const res = await apiFetch("/api/v1/plan/block", {
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
      const res = await apiFetch("/api/v1/staging/seed-dummy-tests", { method: "POST" });
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
      const res = await apiFetch("/api/v1/staging/reset", { method: "POST" });
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

