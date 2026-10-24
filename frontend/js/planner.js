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

    todayTitle.textContent = plan.today_plan.day_name.split(",")[0];
    todayMinutes.innerHTML = `${icon("Countdown")} ${plan.today_plan.total_minutes} Min.`;

    todayTasksList.innerHTML = "";
    if (plan.today_plan.is_blocked) {
      todayTasksList.innerHTML = `
        <div class="empty-placeholder" style="padding: 24px;">
          <h3>${icon("Sperrtag")}</h3>
          ${plan.today_plan.block_info ? `<p>${escapeHtml(plan.today_plan.block_info)}</p>` : ""}
        </div>
      `;
    } else if (plan.today_plan.tasks.length === 0) {
      todayTasksList.innerHTML = `
        <div class="empty-placeholder" style="padding: 24px;">
          <h3>${icon("Feier")} Frei</h3>
        </div>
      `;
    } else {
      plan.today_plan.tasks.forEach((tsk) => {
        const card = document.createElement("div");
        card.className = `plan-task-card ${tsk.is_completed ? "completed" : ""}`;
        card.style.borderLeft = `5px solid ${subjectColor(tsk.subject_name)}`;

        const phaseClass = `phase-p${tsk.phase_number}`;

        card.innerHTML = `
          <div class="task-left">
            <div class="task-subject-icon">${subjectIcon(tsk.subject_name)}</div>
            <div class="task-meta">
              <div class="task-title">
                <span>${tsk.subject_name} – ${tsk.test_kind}</span>
                <span class="phase-pill ${phaseClass}">${tsk.phase_name}</span>
              </div>
              <div class="task-desc">${tsk.phase_description} ${tsk.test_note ? `• <em>${tsk.test_note}</em>` : ""}</div>
            </div>
          </div>
          <div class="task-right">
            <div class="task-time-pill">${icon("Countdown")} ${tsk.target_minutes} Min.</div>
            <button class="btn-task-check" data-test-id="${tsk.test_id}" data-date="${plan.today_date}" data-completed="${tsk.is_completed}">
              ${tsk.is_completed ? icon("Haken") : ""}
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
        taskListHtml = `<span>${icon("Sperrtag")} Sperrtag</span>`;
      } else if (day.tasks.length === 0) {
        taskListHtml = `<span>Frei</span>`;
      } else {
        taskListHtml = day.tasks.map((t) => `
          <div>${subjectLabel(t.subject_name)} (${t.target_minutes}m)</div>
        `).join("");
      }

      dayCard.innerHTML = `
        <div class="day-card-header">${day.day_name.split(",")[0]}</div>
        <div class="day-card-tasks">${taskListHtml}</div>
        ${day.total_minutes ? `<div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 6px;">${day.total_minutes} Min.</div>` : ""}
      `;
      weekTimeline.appendChild(dayCard);
    });

    // 6.3 Anstehende Prüfungen Grid
    const testsGrid = document.getElementById("planner-tests-grid");
    testsGrid.innerHTML = "";
    if (plan.upcoming_tests.length === 0) {
      testsGrid.innerHTML = `
        <div class="empty-placeholder" style="padding: 24px; grid-column: 1 / -1;">
          <p>Keine Prüfungen</p>
        </div>
      `;
    } else {
      plan.upcoming_tests.forEach((t) => {
        const card = document.createElement("div");
        card.className = "test-card";
        card.style.borderLeft = `4px solid ${subjectColor(t.subject_name)}`;

        // Datum und Tage berechnen
        const examDate = new Date(t.date);
        const todayD = new Date(plan.today_date);
        const diffDays = Math.round((examDate - todayD) / (1000 * 60 * 60 * 24));
        const badgeText = diffDays === 0 ? "Heute!" : (diffDays === 1 ? "Morgen" : `in ${diffDays} Tagen`);

        card.innerHTML = `
          <div class="test-card-top">
            <div class="test-card-title">${subjectLabel(t.subject_name)} – ${t.kind}</div>
            <span class="countdown-badge">${badgeText}</span>
          </div>
          ${topicChipsHtml(t.topics, t.subject_name, t.sections)}
          ${t.note ? `<div class="test-note">${escapeHtml(t.note)}</div>` : ""}
          <div class="test-card-footer">
            <span>${icon("Kalender")} ${t.date}</span>
            <span>
              <button class="btn-edit-test parent-only" title="Ändern" aria-label="Ändern">${icon("Schreibwerkzeuge")}</button>
              <button class="btn-del-test parent-only" data-id="${t.id}">Löschen</button>
            </span>
          </div>
        `;
        card.querySelector(".btn-edit-test").addEventListener("click", () => openTestModal(t));

        card.querySelector(".btn-del-test[data-id]").addEventListener("click", async (e) => {
          if (confirm(`Möchtest du diese ${t.kind} wirklich löschen?`)) {
            await deleteTest(e.currentTarget.dataset.id);
          }
        });

        testsGrid.appendChild(card);
      });
    }
    await loadCurrentTopics();

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

document.getElementById("btn-open-test-modal").addEventListener("click", () => openTestModal());

let editingTestId = null;

// Neue Prüfung (test = null) oder eine bestehende ändern; das Fach steht beim Ändern fest
async function openTestModal(test = null) {
  editingTestId = test ? test.id : null;
  document.getElementById("modal-test-title").textContent = test ? `${test.subject_name} – ${test.kind}` : "Neue Prüfung";
  const sel = document.getElementById("input-test-subject");
  sel.innerHTML = currentSubjects.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join("");
  sel.disabled = !!test;
  if (test) sel.value = test.subject_id;
  document.getElementById("input-test-kind").value = test ? test.kind : "Klassenarbeit";
  const d = new Date();
  d.setDate(d.getDate() + 7);  // neu: in 7 Tagen
  document.getElementById("input-test-date").value = test ? test.date : d.toISOString().split("T")[0];
  document.getElementById("input-test-note").value = test ? (test.note || "") : "";
  modalTest.style.display = "flex";
  await fillTestTopics(test ? test.topics.map((tp) => tp.id) : [], test ? test.sections : []);
}

// Nur die Antwort zum zuletzt gewählten Fach zählt (beim schnellen Umschalten kommen ältere später an)
let testTopicsFill = 0;

async function fillTestTopics(checkedIds, checkedSections) {
  const subjectId = document.getElementById("input-test-subject").value;
  const fill = ++testTopicsFill;
  const [topics, books] = await Promise.all([fetchTopics(subjectId), fetchBookSections(subjectId)]);
  if (fill !== testTopicsFill) return;
  renderTopicChecklist(document.getElementById("input-test-topics"), topics, checkedIds);
  renderSectionChecklist(document.getElementById("input-test-sections"), books, checkedSections);
}

document.getElementById("input-test-subject").addEventListener("change", () => fillTestTopics([], []));

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

  const topic_ids = checkedTopicIds(document.getElementById("input-test-topics"));
  const sections = checkedSections(document.getElementById("input-test-sections"));
  const res = editingTestId
    ? await apiFetch(`/api/v1/tests/${editingTestId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, date: dateVal, note, topic_ids, sections })
      })
    : await apiFetch("/api/v1/tests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject_id, kind, date: dateVal, note, topic_ids, sections })
      });

  if (res.ok) {
    modalTest.style.display = "none";
    document.getElementById("input-test-note").value = "";
    await loadPlan();
  } else {
    alert("Fehler beim Speichern der Prüfung.");
  }
});

// ---------- Themen (Test-Themen und „gerade dran“): aus dem Themenkatalog gewählt ----------

async function fetchTopics(subjectId = null) {
  const res = await apiFetch(`/api/v1/taxonomy/topics${subjectId ? `?subject_id=${encodeURIComponent(subjectId)}` : ""}`);
  return res.ok ? res.json() : [];
}

function renderTopicChecklist(box, topics, checkedIds) {
  const byArea = {};
  topics.forEach((tp) => (byArea[tp.area || ""] ||= []).push(tp));
  const areas = Object.keys(byArea).sort((a, b) => (a === "") - (b === "") || a.localeCompare(b, "de"));
  box.innerHTML = topics.length ? areas.map((area) => `
    ${area ? `<div class="topic-area">${escapeHtml(area)}</div>` : ""}
    ${byArea[area].map((tp) => `
      <label class="topic-check">
        <input type="checkbox" value="${tp.id}"${checkedIds.includes(tp.id) ? " checked" : ""}>
        <span>${escapeHtml(tp.name)}</span>
      </label>`).join("")}`).join("") : `<div class="topic-area">–</div>`;
}

function checkedTopicIds(box) {
  return [...box.querySelectorAll("input:checked")].map((el) => el.value);
}

function topicChipsHtml(topics, subjectName, sections = []) {
  const color = subjectColor(subjectName);
  const chips = (topics || []).map((tp) =>
    `<span class="topic-chip" style="--chip-color: ${color}" title="${escapeHtml(tp.area || "")}">${escapeHtml(tp.name)}</span>`)
    .concat((sections || []).map((sc) => sectionChipHtml(sc, color)));
  return chips.length ? `<div class="topic-chips">${chips.join("")}</div>` : "";
}

function sectionChipHtml(sc, color) {
  const where = `${sc.book_title || ""}${sc.book_page ? `, S. ${sc.book_page}` : ""}`;
  return `<span class="topic-chip" style="--chip-color: ${color}" title="${escapeHtml(where)}">${icon("Bücher")} ${escapeHtml(sc.title)}</span>`;
}

// ---------- Kapitel und Abschnitte aus Büchern und Arbeitsheften des Fachs ----------

// Bücher des Fachs mit Kapiteln; jeder Abschnitt reicht bis vor den nächsten derselben oder höheren Ebene
async function fetchBookSections(subjectId) {
  const res = await apiFetch("/api/v1/books");
  if (!res.ok) return [];
  const books = (await res.json()).filter((b) => b.subject_id === subjectId && b.chapters_count > 0);
  const details = await Promise.all(books.map((b) => apiJson(`/api/v1/books/${encodeURIComponent(b.id)}`).catch(() => null)));
  return details.filter(Boolean).map((b) => ({
    title: b.title,
    chapters: b.chapters.map((ch) => {
      const secs = (ch.sections || []).filter((x) => x.relative_page >= 1 && x.relative_page <= ch.page_count);
      return {
        id: ch.id, title: ch.title, pageCount: ch.page_count,
        sections: secs.map((x, i) => {
          const next = secs.slice(i + 1).find((y) => (y.level || 2) <= (x.level || 2));
          return { title: x.title, level: x.level || 2, start: x.relative_page, bookPage: x.book_page,
                   end: next ? Math.max(x.relative_page, next.relative_page - 1) : ch.page_count };
        }),
      };
    }),
  }));
}

const sectionKey = (mat, start, end) => `${mat}|${start}|${end}`;

function sectionInput(mat, start, end, title, bookPage, checked) {
  return `<input type="checkbox" data-mat="${escapeHtml(mat)}" data-start="${start}" data-end="${end}"
    data-title="${escapeHtml(title)}" data-book-page="${bookPage ?? ""}"${checked.has(sectionKey(mat, start, end)) ? " checked" : ""}>`;
}

function renderSectionChecklist(box, books, checkedList) {
  const checked = new Set((checkedList || []).map((sc) => sectionKey(sc.material_id, sc.start_page, sc.end_page)));
  box.innerHTML = books.length ? books.map((b) => `
    <div class="topic-area">${escapeHtml(b.title)}</div>
    ${b.chapters.map((ch) => {
      const open = ch.sections.some((x) => checked.has(sectionKey(ch.id, x.start, x.end)));
      return `
      <div class="topic-chapter">
        <label class="topic-check">${sectionInput(ch.id, 1, ch.pageCount, ch.title, null, checked)}<span>${escapeHtml(ch.title)}</span></label>
        ${ch.sections.length ? `<button type="button" class="topic-chapter-toggle" title="Abschnitte" aria-label="Abschnitte">${icon("Aufklappen")}</button>` : ""}
      </div>
      <div class="topic-chapter-sections"${open ? "" : " hidden"}>
        ${ch.sections.map((x) => `
          <label class="topic-check level-${x.level}">${sectionInput(ch.id, x.start, x.end, x.title, x.bookPage, checked)}<span>${escapeHtml(x.title)}</span></label>`).join("")}
      </div>`;
    }).join("")}`).join("") : `<div class="topic-area">–</div>`;
  box.querySelectorAll(".topic-chapter-toggle").forEach((btn) => btn.addEventListener("click", () => {
    const list = btn.parentElement.nextElementSibling;
    list.hidden = !list.hidden;
  }));
}

function checkedSections(box) {
  return [...box.querySelectorAll("input:checked")].map((el) => ({
    material_id: el.dataset.mat, start_page: Number(el.dataset.start), end_page: Number(el.dataset.end),
    title: el.dataset.title, book_page: el.dataset.bookPage ? Number(el.dataset.bookPage) : null,
  }));
}

function subjectNameOf(subjectId) {
  const s = currentSubjects.find((x) => x.id === subjectId);
  return s ? s.name : "";
}

async function loadCurrentTopics() {
  const box = document.getElementById("planner-current-topics");
  if (!box) return;
  const [topics, sections] = await Promise.all([fetchTopics(), apiJson("/api/v1/plan/current-sections").catch(() => [])]);
  box.innerHTML = topics.filter((tp) => tp.current_since).map((tp) =>
    `<span class="topic-chip" style="--chip-color: ${subjectColor(subjectNameOf(tp.subject_id))}" title="${escapeHtml(subjectNameOf(tp.subject_id))}">${escapeHtml(tp.name)}</span>`)
    .concat(sections.map((sc) => sectionChipHtml(sc, subjectColor(subjectNameOf(sc.subject_id))))).join("");
}

const modalCurrentTopics = document.getElementById("modal-current-topics");
let currentTopicsShown = [];

let currentTopicsFill = 0;

async function fillCurrentTopics() {
  const subjectId = document.getElementById("input-current-subject").value;
  const fill = ++currentTopicsFill;
  const [topics, books, sections] = await Promise.all([fetchTopics(subjectId), fetchBookSections(subjectId),
    apiJson(`/api/v1/plan/current-sections?subject_id=${encodeURIComponent(subjectId)}`).catch(() => [])]);
  if (fill !== currentTopicsFill) return;
  currentTopicsShown = topics;
  renderTopicChecklist(document.getElementById("input-current-topics"), topics,
    topics.filter((tp) => tp.current_since).map((tp) => tp.id));
  renderSectionChecklist(document.getElementById("input-current-sections"), books, sections);
}

document.getElementById("btn-open-current-topics").addEventListener("click", async () => {
  const sel = document.getElementById("input-current-subject");
  sel.innerHTML = currentSubjects.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join("");
  modalCurrentTopics.style.display = "flex";
  await fillCurrentTopics();
});
document.getElementById("input-current-subject").addEventListener("change", fillCurrentTopics);
document.getElementById("btn-close-current-topics").addEventListener("click", () => {
  modalCurrentTopics.style.display = "none";
});

document.getElementById("btn-submit-current-topics").addEventListener("click", async () => {
  const checked = new Set(checkedTopicIds(document.getElementById("input-current-topics")));
  const changed = currentTopicsShown.filter((tp) => checked.has(tp.id) !== !!tp.current_since);
  const results = await Promise.all(changed.map((tp) => apiFetch(`/api/v1/taxonomy/topics/${tp.id}/current`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current: checked.has(tp.id) })
  })).concat(apiFetch("/api/v1/plan/current-sections", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject_id: document.getElementById("input-current-subject").value,
                           sections: checkedSections(document.getElementById("input-current-sections")) })
  })));
  if (results.every((r) => r.ok)) {
    modalCurrentTopics.style.display = "none";
    await loadCurrentTopics();
  } else {
    alert("Fehler beim Speichern der Themen.");
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

