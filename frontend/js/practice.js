// ==========================================================================
// Üben: Übungen aus echten Aufgaben (Probebetrieb, Schalter GOTHEA_EXERCISE_TRIAL)
// --------------------------------------------------------------------------
// Der Kern für alle Fächer und Übungstypen. Thea bekommt eine Runde: Tippen
// auf „Üben“ (alle Fächer) oder auf der Fachseite (ein Fach) → Akku-Frage →
// Aufgaben nacheinander, nach jeder nur „Weiter“ → „Geschafft!“. Was dran ist,
// rechnet der Server (services/practice_due.py). Die Eltern sehen die Liste mit
// Lunas Vorschlag, Stand pro Stufe und Wiederholen. Dazu: Öffnen und Schließen
// einer Übung, Kopfzeile mit den Stufen, Wechsel auf die Übungstafel. Was eine Aufgabenform ausmacht,
// bringt ihr Typ mit (js/practice_<typ>.js, nach dieser Datei geladen).
// Welche Stufen es gibt, sagt der Server (stufen, tafel_stufen); Entwürfe
// liefert er nur im Eltern-Modus.
// ==========================================================================

// Übungstypen melden ihre Ansicht hier an:
//   stages: { <Stufe>: { title, name?, icon? } } – Bezeichnung der Stufen
//   open(ex, stage, core) – zeichnet die Übung in die Ansicht, liefert die tatsächlich geöffnete Stufe
//   close() – eigenen Zustand verwerfen
//   rowNote(ex)? – Zusatz in der Listenzeile (z. B. „antiproportional“)
//   sheet? – Blatt für die Tafel-Stufen (whiteboard.js): { prepare?(ex) → Promise, render(ex, stage, {light, solution}, prepared) → Bild-URL }
// core: topbarHtml(ex, stage), close(), open(id, stage), setZen(on),
//   inRound() – läuft eine Runde? Dann zeigt der Typ nach dem Lösen nur roundNextHtml() statt eigener Knöpfe
const PRACTICE_TYPES = {};

function registerPracticeType(typ, view) {
  PRACTICE_TYPES[typ] = view;
}

(function () {
  const navBtn = document.querySelector('.nav-tab[data-tab="practice"]');
  const listView = document.getElementById("practice-list-view");
  const listEl = document.getElementById("practice-list");
  const runView = document.getElementById("practice-run-view");
  const roundView = document.getElementById("practice-round-view");
  if (!navBtn || !listView || !listEl || !runView || !roundView) return;

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
    const tryRound = document.createElement("button");
    tryRound.type = "button";
    tryRound.className = "practice-icon-btn practice-try-round";
    tryRound.title = "Runde wie Thea";
    tryRound.setAttribute("aria-label", "Runde wie Thea");
    tryRound.innerHTML = `${icon("Kind")}${icon("Pfeil rechts")}`;
    tryRound.addEventListener("click", () => askBattery(null));
    listEl.appendChild(tryRound);
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
    show(roundView, false);
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
    if (round) return showRoundPause();
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
        <button type="button" class="practice-icon-btn" data-action="back" title="${round ? "Pause" : "Zur Liste"}" aria-label="${round ? "Pause" : "Zur Liste"}">${icon("Pfeil links")}</button>
        <span class="px-src">${esc(sourceLine(ex.quelle))}${ex.ableitung === "B" ? " · ähnliche Aufgabe" : ""}</span>
        ${round ? roundDotsHtml() : ""}
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

  const core = { topbarHtml, close: closeExercise, open: openExercise, setZen: setPracticeZen,
                 inRound: () => !!round, roundNextHtml };

  // Zurück, „ähnliche Aufgabe“ und Stufenwechsel gelten für alle Typen; der Rest gehört der Ansicht des Typs
  runView.addEventListener("click", (e) => {
    if (!current) return;
    const t = e.target.closest("button");
    if (!t || t.disabled) return;
    if (t.dataset.action === "back") return closeExercise();
    if (t.dataset.action === "round-next") return nextInRound();
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

  // ---------- Runde für Thea ----------
  // round: { fach, akku, items, index, families } – solange sie läuft, führt „Üben“ in die Runde zurück

  let round = null;
  let pendingFach;  // von der Fachseite: Runde nur für dieses Fach

  const BATTERY = [
    { akku: "fast_leer", icon: "Akku leer", title: "Fast leer" },
    { akku: "geht_so", icon: "Akku halb", title: "Geht so" },
    { akku: "voll", icon: "Akku voll", title: "Voll" },
  ];

  function showRound(html) {
    setPracticeZen(false);
    show(listView, false);
    show(runView, false);
    roundView.innerHTML = html;
    show(roundView, true);
  }

  const lunaSays = (text) => `<div class="pr-luna">${icon("Luna", "pr-luna-icon")}<p>${esc(text)}</p></div>`;

  function askBattery(fach) {
    round = null;
    const subject = fach ? subjectNameOf(fach) : "";
    showRound(`
      ${lunaSays(subject ? `${subject}! Wie voll ist dein Akku?` : "Wie voll ist dein Akku?")}
      <div class="pr-battery" role="group" aria-label="Akku">
        ${BATTERY.map((b) => `<button type="button" class="pr-battery-btn" data-akku="${b.akku}" title="${b.title}" aria-label="${b.title}">${icon(b.icon)}</button>`).join("")}
      </div>`);
    roundView.querySelectorAll(".pr-battery-btn").forEach((btn) =>
      btn.addEventListener("click", () => startRound(fach, btn.dataset.akku)));
  }

  async function startRound(fach, akku) {
    const query = new URLSearchParams({ akku, ...(fach ? { fach } : {}) });
    const [data, list] = await Promise.all([apiJson(`/api/v1/practice/round?${query}`), apiJson("/api/v1/practice")]);
    overview = list;
    if (!data.runde.length) {
      round = null;
      return showRound(`${lunaSays("Gerade ist nichts dran. Bis später!")}
        <div class="pr-actions"><button type="button" class="px-check" data-action="round-home" title="Fertig" aria-label="Fertig">${icon("Haken")}</button></div>`);
    }
    round = { fach, akku, items: data.runde, index: 0,
              families: Object.fromEntries(list.exercises.map((ex) => [ex.id, ex])) };
    runItem();
  }

  function runItem() {
    const item = round.items[round.index];
    const family = round.families[item.familie];
    item.onBoard = family.tafel_stufen.includes(item.stufe);
    startPractice(item, family);
  }

  function nextInRound() {
    if (!round) return;
    round.index += 1;
    if (current) current.view.close();
    current = null;
    show(runView, false);
    runView.innerHTML = "";
    if (round.index < round.items.length) return runItem();
    finishRound();
  }

  function finishRound() {
    const count = round.items.length;
    round = null;
    showRound(`
      ${lunaSays("Geschafft! Super gemacht.")}
      <div class="pr-done">${icon("Feier", "pr-done-feier")}<span class="pr-done-count">${icon("Stern").repeat(count)}</span></div>
      <div class="pr-actions"><button type="button" class="px-check" data-action="round-home" title="Fertig" aria-label="Fertig">${icon("Haken")}</button></div>`);
    refreshDueHint();
  }

  // Pause (Zurück in der Kopfzeile) oder zurück von der Übungstafel: weiter mit derselben bzw. der nächsten Aufgabe
  function showRoundPause() {
    const item = round.items[round.index];
    if (item.onBoard) round.index += 1;  // die Tafel-Aufgabe gilt als erledigt, sobald Thea zurückkommt
    if (round.index >= round.items.length) return finishRound();
    showRound(`
      ${lunaSays("Pause. Weiter, wenn du bereit bist.")}
      ${roundDotsHtml()}
      <div class="pr-actions"><button type="button" class="px-check" data-action="round-resume" title="Weiter" aria-label="Weiter">${icon("Pfeil rechts")}</button></div>`);
  }

  function roundDotsHtml() {
    return `<span class="pr-dots" aria-label="Aufgabe ${round.index + 1} von ${round.items.length}">${round.items.map((_, i) =>
      `<span class="pr-dot${i < round.index ? " done" : i === round.index ? " now" : ""}"></span>`).join("")}</span>`;
  }

  function roundNextHtml() {
    const last = round && round.index === round.items.length - 1;
    return `<button type="button" class="px-check" data-action="round-next" title="${last ? "Fertig" : "Weiter"}" aria-label="${last ? "Fertig" : "Weiter"}">${icon(last ? "Haken" : "Pfeil rechts")}</button>`;
  }

  roundView.addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    if (t.dataset.action === "round-resume") return runItem();
    if (t.dataset.action === "round-home") {
      round = null;
      switchToTab("dashboard");
    }
  });

  function subjectNameOf(id) {
    const s = (typeof currentSubjects !== "undefined" ? currentSubjects : []).find((x) => x.id === id);
    return s ? s.name : "";
  }

  // Punkt am Üben-Symbol, wenn etwas dran ist
  function refreshDueHint() {
    apiJson("/api/v1/practice/round")
      .then((data) => navBtn.classList.toggle("has-due", data.anzahl_dran > 0))
      .catch(() => navBtn.classList.remove("has-due"));
  }

  // ---------- Einstieg ----------
  // Thea: Runde (läuft schon eine, geht es dort weiter); Eltern: die Liste

  navBtn.addEventListener("click", () => {
    const fach = pendingFach;
    pendingFach = undefined;
    if (current) return;
    if (document.body.classList.contains("parent-mode-active") && fach === undefined && !round) {
      show(roundView, false);
      show(listView, true);
      return loadPracticeList().catch((err) => console.warn("Übungen nicht geladen:", err));
    }
    if (round && (fach === undefined || fach === round.fach)) return showRoundPause();
    askBattery(fach || null);
  });

  // Fachseite: Runde nur für dieses Fach
  window.startPracticeRound = (fach) => {
    pendingFach = fach;
    switchToTab("practice");
  };

  // Tab nur zeigen, wenn der Probebetrieb eingeschaltet ist
  apiJson("/api/v1/practice")
    .then((data) => {
      window.practiceEnabled = data.enabled;  // die Fachseite blendet danach ihre Karte „Üben“ ein
      show(navBtn, data.enabled);
      if (data.enabled) refreshDueHint();
    })
    .catch(() => show(navBtn, false));

  window.openPracticeExercise = openExercise;
  window.practiceRoundActive = () => !!round;
})();
