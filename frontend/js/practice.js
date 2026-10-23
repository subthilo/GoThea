// ==========================================================================
// Üben: Übungen aus echten Aufgaben (Probebetrieb, Schalter GOTHEA_EXERCISE_TRIAL)
// --------------------------------------------------------------------------
// Der Kern für alle Fächer und Übungstypen: Liste mit Lunas Vorschlag, Stand
// pro Stufe und Wiederholen; Öffnen und Schließen einer Übung, Kopfzeile mit
// den Stufen, Wechsel auf die Übungstafel. Was eine Aufgabenform ausmacht,
// bringt ihr Typ mit (js/practice_<typ>.js, nach dieser Datei geladen).
// Welche Stufen es gibt, sagt der Server (stufen, tafel_stufen); Entwürfe
// liefert er nur im Eltern-Modus.
// ==========================================================================

// Übungstypen melden ihre Ansicht hier an:
//   stages: { <Stufe>: { title, name?, icon? } } – Bezeichnung der Stufen
//   open(ex, stage, core) – zeichnet die Übung in die Ansicht, liefert die tatsächlich geöffnete Stufe
//   close() – eigenen Zustand verwerfen
//   rowNote(ex)? – Zusatz in der Listenzeile (z. B. „antiproportional“)
// core: topbarHtml(ex, stage), close(), open(id, stage), setZen(on)
const PRACTICE_TYPES = {};

function registerPracticeType(typ, view) {
  PRACTICE_TYPES[typ] = view;
}

(function () {
  const navBtn = document.querySelector('.nav-tab[data-tab="practice"]');
  const listView = document.getElementById("practice-list-view");
  const listEl = document.getElementById("practice-list");
  const runView = document.getElementById("practice-run-view");
  if (!navBtn || !listView || !listEl || !runView) return;

  let current = null;  // geöffnete Übung: { ex, stage, view }

  const esc = (s) => escapeHtml(String(s));
  const show = (el, on) => { el.style.display = on ? "" : "none"; };

  // Stufen-Bezeichnung des Typs; ohne Angabe die Zahl
  const stageInfo = (typ, n) => ((PRACTICE_TYPES[typ] || {}).stages || {})[n] || {};
  const stageMark = (typ, n) => (stageInfo(typ, n).icon ? icon(stageInfo(typ, n).icon) : String(n));
  const stageName = (typ, n) => stageInfo(typ, n).name || `Stufe ${n}`;
  const stageTitle = (typ, n) => stageInfo(typ, n).title || stageName(typ, n);

  function sourceLine(q) {
    const page = q.seite ? `, S. ${q.seite}` : "";
    return `${q.material}${page}, Nr. ${q.nummer}`;
  }

  // ---------- Liste: Lunas Vorschlag, Aufgaben nach Fach und Abschnitt, Wiederholen ----------
  // Stand und Vorschlag rechnet der Server aus den Versuchen (services/practice_plan.py).

  let overview = null;  // letzte Antwort von /api/v1/practice

  async function loadPracticeList() {
    const data = await apiJson("/api/v1/practice");
    listEl.innerHTML = "";
    if (!data.enabled) return;
    overview = data;
    const families = Object.fromEntries(data.exercises.map((ex) => [ex.id, ex]));
    if (data.vorschlag) listEl.appendChild(buildSuggestion(data.vorschlag, families[data.vorschlag.familie]));

    const groups = new Map();
    data.exercises.forEach((ex) => {
      const key = `${ex.fach}|${ex.abschnitt || ""}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(ex);
    });
    groups.forEach((list) => {
      const h = document.createElement("h3");
      h.className = "practice-group-title";
      h.textContent = list[0].abschnitt || "";
      listEl.appendChild(h);
      list.forEach((ex) => listEl.appendChild(buildRow(ex, data.stand[ex.id])));
    });

    if (data.wiederholen.length) {
      const h = document.createElement("h3");
      h.className = "practice-group-title icon-heading";
      h.title = "Wiederholen";
      h.innerHTML = `${icon("Wiederholen")}<span class="sr-only">Wiederholen</span>`;
      listEl.appendChild(h);
      data.wiederholen.forEach((r) => listEl.appendChild(buildRepeatRow(r, families[r.familie])));
    }
  }

  function openBoard(ex, exerciseId, stage) {
    const ableitung = exerciseId === ex.id ? ex.ableitung || "A" : "B";
    return window.openPracticeOnWhiteboard({ exerciseId, stage, subjectId: ex.fach, title: practiceBoardTitle(ex.quelle, ableitung, stage) });
  }

  // Stufen im Tab öffnen die Übung hier, Tafel-Stufen eine Übungstafel; ein angefangener Versuch öffnet seine Tafel wieder
  function startPractice({ exercise_id: exerciseId, stufe: stage, board_id: boardId }, family) {
    if (boardId && typeof window.openBoardOnWhiteboard === "function") return window.openBoardOnWhiteboard(boardId);
    const onBoard = family.tafel_stufen.includes(stage);
    if (onBoard && typeof window.openPracticeOnWhiteboard === "function") return openBoard(family, exerciseId, stage);
    const tabStages = family.stufen.filter((s) => !family.tafel_stufen.includes(s));
    return openExercise(exerciseId, onBoard ? tabStages[tabStages.length - 1] : stage);
  }

  const SUGGESTION_ICONS = { weiter: "Pfeil rechts", wiederholen: "Wiederholen", neu: "Rakete" };

  function draftMark(ex, el) {
    if (ex.status !== "entwurf") return;
    el.classList.add("practice-draft");
    el.title = `${el.title ? el.title + " · " : ""}Entwurf (nur Eltern)`;
  }

  function buildSuggestion(sug, family) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "practice-suggest";
    card.title = sug.art === "wiederholen" ? "Wiederholen" : sug.art === "neu" ? "Neue Aufgabe" : "Weiter";
    card.style.setProperty("--subject-color", subjectColor(family.fach));
    card.innerHTML = `
      ${icon("Luna", "practice-suggest-luna")}
      <span class="practice-row-text">
        <span class="practice-suggest-task">${esc(family.aufgabentext)}</span>
        <span class="practice-row-src">${esc(sourceLine(family.quelle))}${sug.exercise_id !== family.id ? " · ähnliche Aufgabe" : ""}</span>
      </span>
      <span class="practice-suggest-go">${icon(SUGGESTION_ICONS[sug.art] || "Pfeil rechts")}<span class="practice-stage-no">${stageMark(family.typ, sug.stufe)}</span></span>`;
    card.addEventListener("click", () => startPractice(sug, family));
    draftMark(family, card);
    return card;
  }

  function stageDots(ex, stand) {
    const done = new Set(stand ? stand.geschafft : []);
    const next = stand ? stand.naechste_stufe : ex.stufen[0];
    return ex.stufen.map((n) => {
      const cls = done.has(n) ? " done" : n === next ? " next" : "";
      const label = `${stageName(ex.typ, n)}: ${stageTitle(ex.typ, n)}${done.has(n) ? " (geschafft)" : ""}`;
      return `<button type="button" class="practice-dot${cls}" data-stage="${n}" title="${esc(label)}" aria-label="${esc(label)}"><span>${stageMark(ex.typ, n)}</span></button>`;
    }).join("");
  }

  function buildRow(ex, stand) {
    const row = document.createElement("div");
    row.className = "practice-row";
    row.dataset.id = ex.id;
    row.style.setProperty("--subject-color", subjectColor(ex.fach));
    const view = PRACTICE_TYPES[ex.typ] || {};
    const note = view.rowNote ? view.rowNote(ex) : "";
    const next = (stand && stand.naechste_stufe) ?? ex.stufen[0];
    row.innerHTML = `
      <button type="button" class="practice-row-main" title="Üben">
        ${subjectIcon(ex.fach, "practice-row-icon")}
        <span class="practice-row-text">
          <span class="practice-row-task">${esc(ex.aufgabentext)}</span>
          <span class="practice-row-src">${esc(sourceLine(ex.quelle))}${note ? ` · ${esc(note)}` : ""}</span>
        </span>
      </button>
      <div class="practice-dots" role="group" aria-label="Stufen">${stageDots(ex, stand)}</div>`;
    row.querySelector(".practice-row-main").addEventListener("click", () => startPractice({ exercise_id: ex.id, stufe: next }, ex));
    row.querySelectorAll(".practice-dot").forEach((dot) => dot.addEventListener("click", () =>
      startPractice({ exercise_id: ex.id, stufe: Number(dot.dataset.stage) }, ex)));
    if (ex.zwillinge.length) {
      const twin = document.createElement("button");
      twin.type = "button";
      twin.className = "practice-icon-btn";
      twin.title = "Ähnliche Aufgabe";
      twin.setAttribute("aria-label", "Ähnliche Aufgabe");
      twin.innerHTML = icon("Wiederholen");
      twin.addEventListener("click", () => startPractice({ exercise_id: ex.zwillinge[0], stufe: next }, ex));
      row.appendChild(twin);
    }
    draftMark(ex, row);
    return row;
  }

  function buildRepeatRow(r, family) {
    const row = document.createElement("div");
    row.className = "practice-row practice-repeat";
    row.style.setProperty("--subject-color", subjectColor(family.fach));
    row.innerHTML = `
      <button type="button" class="practice-row-main" title="Wiederholen">
        ${subjectIcon(family.fach, "practice-row-icon")}
        <span class="practice-row-text">
          <span class="practice-row-task">${esc(family.aufgabentext)}</span>
          <span class="practice-row-src">${esc(sourceLine(family.quelle))}${r.exercise_id !== family.id ? " · ähnliche Aufgabe" : ""}</span>
        </span>
        <span class="practice-dot next" aria-label="${stageName(family.typ, r.stufe)}"><span>${stageMark(family.typ, r.stufe)}</span></span>
      </button>`;
    row.querySelector(".practice-row-main").addEventListener("click", () => startPractice(r, family));
    draftMark(family, row);
    return row;
  }

  // ---------- Übung: öffnen, Kopfzeile, schließen ----------

  async function openExercise(id, stage = 0) {
    const ex = await apiJson(`/api/v1/practice/${encodeURIComponent(id)}`);
    const view = PRACTICE_TYPES[ex.typ];
    if (!view) {
      console.warn(`Übungstyp „${ex.typ}“ hat keine Ansicht`);
      return;
    }
    if (current && current.view !== view) current.view.close();
    if (!ex.stufen.includes(stage)) stage = ex.stufen[0];
    show(listView, false);
    show(runView, true);
    current = { ex, stage, view };
    current.stage = view.open(ex, stage, core);
    runView.scrollIntoView({ block: "start" });
  }

  function closeExercise() {
    setPracticeZen(false);
    if (current) current.view.close();
    current = null;
    show(runView, false);
    runView.innerHTML = "";
    show(listView, true);
    loadPracticeList().catch((err) => console.warn("Übungen nicht geladen:", err));
  }

  function stageButtons(ex, stage) {
    const family = ex.zwilling_von || ex.id;
    const done = new Set(overview && overview.stand[family] ? overview.stand[family].geschafft : []);
    return ex.stufen.map((n) =>
      `<button type="button" class="px-stage${n === stage ? " active" : ""}${done.has(n) ? " done" : ""}" data-stage="${n}" title="${esc(stageTitle(ex.typ, n))}" aria-label="${stageName(ex.typ, n)}: ${esc(stageTitle(ex.typ, n))}">${stageMark(ex.typ, n)}</button>`
    ).join("");
  }

  function topbarHtml(ex, stage) {
    return `
      <div class="px-topbar${ex.status === "entwurf" ? " practice-draft" : ""}">
        <button type="button" class="practice-icon-btn" data-action="back" title="Zur Liste" aria-label="Zur Liste">${icon("Pfeil links")}</button>
        <span class="px-src">${esc(sourceLine(ex.quelle))}${ex.ableitung === "B" ? " · ähnliche Aufgabe" : ""}</span>
        <div class="px-stages" role="group" aria-label="Stufe">${stageButtons(ex, stage)}</div>
      </div>`;
  }

  // Ansichten, die die ganze Bildschirmhöhe ohne Seiten-Scrollen nutzen (z. B. der Gedankengang)
  let zenWanted = false;
  function setPracticeZen(on) {
    zenWanted = on;
    document.documentElement.classList.toggle("practice-zen-mode", on);
    document.body.classList.toggle("practice-zen-mode", on);
  }
  document.querySelectorAll(".nav-tab").forEach((tab) => tab.addEventListener("click", () => {
    const on = zenWanted && tab.dataset.tab === "practice" && !!current && runView.style.display !== "none";
    document.documentElement.classList.toggle("practice-zen-mode", on);
    document.body.classList.toggle("practice-zen-mode", on);
  }));

  const core = { topbarHtml, close: closeExercise, open: openExercise, setZen: setPracticeZen };

  // Zurück, „ähnliche Aufgabe“ und Stufenwechsel gelten für alle Typen; der Rest gehört der Ansicht des Typs
  runView.addEventListener("click", (e) => {
    if (!current) return;
    const t = e.target.closest("button");
    if (!t || t.disabled) return;
    if (t.dataset.action === "back") return closeExercise();
    if (t.dataset.action === "open") return openExercise(t.dataset.id, Number(t.dataset.at || 0));
    if (t.dataset.stage !== undefined) {
      const stage = Number(t.dataset.stage);
      const ex = current.ex;
      if (!ex.tafel_stufen.includes(stage)) return stage === current.stage ? undefined : openExercise(ex.id, stage);
      if (typeof window.openPracticeOnWhiteboard !== "function") return;
      return openBoard({ ...ex, id: ex.zwilling_von || ex.id }, ex.id, stage);
    }
  });

  // ---------- Einstieg ----------

  navBtn.addEventListener("click", () => {
    if (!current) loadPracticeList().catch((err) => console.warn("Übungen nicht geladen:", err));
  });

  // Tab nur zeigen, wenn der Probebetrieb eingeschaltet ist
  apiJson("/api/v1/practice")
    .then((data) => {
      window.practiceEnabled = data.enabled;  // die Fachseite blendet danach ihre Karte „Üben“ ein
      show(navBtn, data.enabled);
    })
    .catch(() => show(navBtn, false));

  window.openPracticeExercise = openExercise;
})();
