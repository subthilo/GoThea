// ==========================================================================
// Üben: Übungen aus echten Aufgaben (Probebetrieb, Schalter GOTHEA_EXERCISE_TRIAL)
// --------------------------------------------------------------------------
// Stufe -1 „Gedankengang“: der Rechenweg steht als Sätze da, Thea ergänzt nur
// Zahlen, Schritt für Schritt (mit dem Pencil per Scribble oder per Tastatur).
// Stufe 0 „Bausteine“: Thea setzt Rechenschritte und Werte in die Dreisatz-
// Tabelle (Antippen oder Ziehen) und wählt den Antwortsatz. Vorher fragt Luna
// nach einer Schätzung. Die Prüfung läuft hier im Browser gegen die Lösung aus
// den Übungsdaten (backend/app/exercise_sets, nachgerechnet vom Server).
// ==========================================================================

(function () {
  const navBtn = document.querySelector('.nav-tab[data-tab="practice"]');
  const listView = document.getElementById("practice-list-view");
  const listEl = document.getElementById("practice-list");
  const runView = document.getElementById("practice-run-view");
  if (!navBtn || !listView || !listEl || !runView) return;

  // Stufe -1 und 0 hier im Tab; 1–4 = Blatt auf einer neuen Tafel, mit dem Pencil (weniger Gerüst je Stufe).
  // Die leichteste Stufe trägt ein Icon statt einer Zahl, damit die Nummern der Tafel-Stufen bleiben.
  const STAGES = [
    { n: -1, title: "Gedankengang: Schritt für Schritt", icon: "Tipp" },
    { n: 0, title: "Bausteine einsetzen" },
    { n: 1, title: "Tafel: Tabelle vorgegeben, Antwort angefangen" },
    { n: 2, title: "Tafel: nur Tabellenkopf" },
    { n: 3, title: "Tafel: nur R: und A:" },
    { n: 4, title: "Tafel: leeres Blatt wie im Test" },
  ];
  const stageMark = (n) => (n < 0 ? icon("Tipp") : String(n));
  const stageName = (n) => (n < 0 ? "Gedankengang" : `Stufe ${n}`);

  let run = null;  // aktuelle Übung: { ex, guess, placed, answer, checked, hint, selected }

  const esc = (s) => escapeHtml(String(s));
  const show = (el, on) => { el.style.display = on ? "" : "none"; };
  const isUp = (opt) => opt === "mehr" || opt === "länger";
  const num = (s) => Number(String(s).replace(/\./g, "").replace(",", "."));

  function fmt(x, unit) {
    const n = Number(x);
    if (unit === "€" && !Number.isInteger(n)) return n.toFixed(2).replace(".", ",");
    return String(n).replace(".", ",");
  }

  function sourceLine(q) {
    const page = q.seite ? `, S. ${q.seite}` : "";
    return `${q.material}${page}, Nr. ${q.nummer}`;
  }

  // ---------- Liste: Lunas Vorschlag, Aufgaben nach Abschnitt, Wiederholen ----------
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
      if (!groups.has(ex.abschnitt)) groups.set(ex.abschnitt, []);
      groups.get(ex.abschnitt).push(ex);
    });
    groups.forEach((list, title) => {
      const h = document.createElement("h3");
      h.className = "practice-group-title";
      h.textContent = title;
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

  // Stufe 0 im Tab, Stufen 1–4 auf einer Übungstafel; ein angefangener Versuch öffnet seine Tafel wieder
  function startPractice({ exercise_id: exerciseId, stufe: stage, board_id: boardId }, family) {
    if (boardId && typeof window.openBoardOnWhiteboard === "function") return window.openBoardOnWhiteboard(boardId);
    if (!(stage > 0) || typeof window.openPracticeOnWhiteboard !== "function") return openExercise(exerciseId, stage > 0 ? 0 : stage || 0);
    const ableitung = exerciseId === family.id ? "A" : "B";
    return window.openPracticeOnWhiteboard({ exerciseId, stage, title: practiceBoardTitle(family.quelle, ableitung, stage) });
  }

  const SUGGESTION_ICONS = { weiter: "Pfeil rechts", wiederholen: "Wiederholen", neu: "Rakete" };

  function buildSuggestion(sug, family) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "practice-suggest";
    card.title = sug.art === "wiederholen" ? "Wiederholen" : sug.art === "neu" ? "Neue Aufgabe" : "Weiter";
    card.style.setProperty("--subject-color", subjectColor("sub_math"));
    card.innerHTML = `
      ${icon("Luna", "practice-suggest-luna")}
      <span class="practice-row-text">
        <span class="practice-suggest-task">${esc(family.aufgabentext)}</span>
        <span class="practice-row-src">${esc(sourceLine(family.quelle))}${sug.exercise_id !== family.id ? " · ähnliche Aufgabe" : ""}</span>
      </span>
      <span class="practice-suggest-go">${icon(SUGGESTION_ICONS[sug.art] || "Pfeil rechts")}<span class="practice-stage-no">${stageMark(sug.stufe)}</span></span>`;
    card.addEventListener("click", () => startPractice(sug, family));
    return card;
  }

  function stageDots(stand) {
    const done = new Set(stand ? stand.geschafft : []);
    const next = stand ? stand.naechste_stufe : -1;
    return STAGES.map(({ n, title }) => {
      const cls = done.has(n) ? " done" : n === next ? " next" : "";
      const label = `${stageName(n)}: ${title}${done.has(n) ? " (geschafft)" : ""}`;
      return `<button type="button" class="practice-dot${cls}" data-stage="${n}" title="${esc(label)}" aria-label="${esc(label)}"><span>${stageMark(n)}</span></button>`;
    }).join("");
  }

  function buildRow(ex, stand) {
    const row = document.createElement("div");
    row.className = "practice-row";
    row.dataset.id = ex.id;
    row.style.setProperty("--subject-color", subjectColor("sub_math"));
    const anti = ex.schema === "dreisatz_antiproportional";
    const next = !stand ? -1 : stand.naechste_stufe ?? 0;
    row.innerHTML = `
      <button type="button" class="practice-row-main" title="Üben">
        ${subjectIcon("Mathematik", "practice-row-icon")}
        <span class="practice-row-text">
          <span class="practice-row-task">${esc(ex.aufgabentext)}</span>
          <span class="practice-row-src">${esc(sourceLine(ex.quelle))}${anti ? " · antiproportional" : ""}</span>
        </span>
      </button>
      <div class="practice-dots" role="group" aria-label="Stufen">${stageDots(stand)}</div>`;
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
    return row;
  }

  function buildRepeatRow(r, family) {
    const row = document.createElement("div");
    row.className = "practice-row practice-repeat";
    row.style.setProperty("--subject-color", subjectColor("sub_math"));
    row.innerHTML = `
      <button type="button" class="practice-row-main" title="Wiederholen">
        ${subjectIcon("Mathematik", "practice-row-icon")}
        <span class="practice-row-text">
          <span class="practice-row-task">${esc(family.aufgabentext)}</span>
          <span class="practice-row-src">${esc(sourceLine(family.quelle))}${r.exercise_id !== family.id ? " · ähnliche Aufgabe" : ""}</span>
        </span>
        <span class="practice-dot next" aria-label="${stageName(r.stufe)}"><span>${stageMark(r.stufe)}</span></span>
      </button>`;
    row.querySelector(".practice-row-main").addEventListener("click", () => startPractice(r, family));
    return row;
  }

  // ---------- Übung ----------

  async function openExercise(id, stage = 0) {
    const ex = await apiJson(`/api/v1/practice/${encodeURIComponent(id)}`);
    if (stage < 0 && !(ex.gedankengang || []).length) stage = 0;
    run = { ex, stage, guess: null, placed: {}, answer: null, reason: null, checked: false, hint: 0, selected: null,
            attempt: startPracticeAttempt(ex.id, stage),
            guided: { step: 0, values: {}, wrong: new Set(), fails: 0, tip: false, empty: false, done: false, active: null } };
    if (!ex.schaetzfrage.aktiv) run.guess = "-";
    show(listView, false);
    show(runView, true);
    renderRun();
    runView.scrollIntoView({ block: "start" });
  }

  function closeExercise() {
    run = null;
    show(runView, false);
    runView.innerHTML = "";
    show(listView, true);
    loadPracticeList().catch((err) => console.warn("Übungen nicht geladen:", err));
  }

  function slot(id, kind) {
    const value = run.placed[id];
    const state = run.checked ? (value === run.ex.bausteine.felder[id] ? " ok" : " wrong") : "";
    const filled = value ? " filled" : "";
    return `<button type="button" class="px-slot px-kind-${kind}${filled}${state}" data-slot="${id}" data-kind="${kind}"
      aria-label="${value ? "Feld: " + esc(value) : "leeres Feld"}">${value ? esc(value) : ""}</button>`;
  }

  function tableHtml(ex) {
    const [g1, g2] = ex.groessen;
    const head = (g) => esc(g.name) + (g.einheit ? ` (in ${esc(g.einheit)})` : "");
    const [[x0, y0], , [x2]] = ex.zeilen;
    const money = g2.einheit === "€";
    // Echte Tabelle statt CSS-Grid: Safari auf dem iPad rechnete die Grid-Zeilenhöhen falsch
    const valueRow = (left, right) =>
      `<tr class="px-row-val"><td></td><td class="px-l">${left}</td><td class="px-r">${right}</td><td></td></tr>`;
    const opRow = (n) =>
      `<tr class="px-row-op"><td class="px-op-l">${slot(`op_links_${n}`, "op")}<span class="px-arrow">↓</span></td>
        <td class="px-l"></td><td class="px-r"></td>
        <td class="px-op-r"><span class="px-arrow">↓</span>${slot(`op_rechts_${n}`, "op")}</td></tr>`;
    return `
      <table class="px-table">
        <thead><tr><th></th><th class="px-head">${head(g1)}</th><th class="px-head">${head(g2)}</th><th></th></tr></thead>
        <tbody>
          ${valueRow(esc(fmt(x0)), esc(fmt(y0, money ? "€" : "")))}
          ${opRow(1)}
          ${valueRow(slot("mitte_links", "val"), slot("mitte_rechts", "val"))}
          ${opRow(2)}
          ${valueRow(esc(fmt(x2)), slot("ergebnis", "val"))}
        </tbody>
      </table>`;
  }

  function calcHtml(ex) {
    const [a, b] = ex.rechnung.ausdruck.split(":").map((t) => t.trim());
    return `
      <div class="px-line"><span class="px-label">Überschlag:</span> ${esc(a)} : 1 = ${slot("ueberschlag", "val")}</div>
      <div class="px-line"><span class="px-label">R:</span> ${esc(a)} : ${esc(b)} = ${slot("umformung_links", "val")} : ${slot("umformung_rechts", "val")} = ${slot("ergebnis", "val")}</div>`;
  }

  function answersHtml(ex) {
    return ex.bausteine.antworten.map((a, i) => {
      let state = "";
      if (run.checked && run.answer === i) state = a.richtig ? " ok" : " wrong";
      return `<button type="button" class="px-answer${run.answer === i ? " chosen" : ""}${state}" data-answer="${i}">${esc(a.text)}</button>`;
    }).join("");
  }

  // Begründung (z. B. „Begründe, dass die Zuordnung proportional ist“): Vorschlag wählen
  function reasonsHtml(ex) {
    return ex.bausteine.begruendungen.map((r, i) => {
      let state = "";
      if (run.checked && run.reason === i) state = r.richtig ? " ok" : " wrong";
      return `<button type="button" class="px-answer${run.reason === i ? " chosen" : ""}${state}" data-reason="${i}">${esc(r.text)}</button>`;
    }).join("");
  }

  function paletteHtml(ex) {
    const locked = !run.guess || run.checked && allRight();
    const tokens = (list, kind) => list.map((t) =>
      `<button type="button" class="px-token px-kind-${kind}${run.selected === t ? " selected" : ""}" data-token="${esc(t)}" data-kind="${kind}"${locked ? " disabled" : ""}>${esc(t)}</button>`).join("");
    const ops = ex.bausteine.rechenschritte.length
      ? `<div class="px-palette-group" title="Rechenschritte">${tokens(ex.bausteine.rechenschritte, "op")}</div>` : "";
    return `${ops}<div class="px-palette-group" title="Werte">${tokens(ex.bausteine.werte, "val")}</div>`;
  }

  function allFilled() {
    const needsReason = run.ex.bausteine.begruendungen.length > 0;
    return Object.keys(run.ex.bausteine.felder).every((k) => run.placed[k]) && run.answer !== null
      && (!needsReason || run.reason !== null);
  }

  function allRight() {
    const f = run.ex.bausteine.felder;
    const reasons = run.ex.bausteine.begruendungen;
    const reasonOk = !reasons.length || reasons[run.reason]?.richtig;
    return Object.keys(f).every((k) => run.placed[k] === f[k]) && run.ex.bausteine.antworten[run.answer]?.richtig && reasonOk;
  }

  // Was die Prüfung ergab, für den Lernstand: welche Felder falsch, Antwortsatz/Begründung richtig?
  function checkResult() {
    const b = run.ex.bausteine;
    const result = {
      status: allRight() ? "richtig" : "noch_nicht",
      falsch: Object.keys(b.felder).filter((k) => run.placed[k] !== b.felder[k]),
      antwort_richtig: Boolean(b.antworten[run.answer]?.richtig),
    };
    if (b.begruendungen.length) result.begruendung_richtig = Boolean(b.begruendungen[run.reason]?.richtig);
    return result;
  }

  function lunaHtml() {
    const ex = run.ex, sf = ex.schaetzfrage, unit = ex.ergebnis.einheit;
    const say = (t) => `<div class="px-say">${icon("Luna", "px-luna-icon")}<p>${esc(t)}</p></div>`;
    let h = "";
    if (!sf.aktiv) {
      if (!run.checked) h += say("Fang mit dem Überschlag an: Wie viele Flaschen wären es ungefähr?");
    } else if (!run.guess) {
      if (ex.einstieg && ex.ableitung === "A") h += say(ex.einstieg);
      h += say(`Bevor du rechnest: ${sf.frage}`);
      h += `<div class="px-guess">${sf.optionen.map((o) => `<button type="button" class="px-guess-btn" data-guess="${esc(o)}">${esc(o)}</button>`).join("")}</div>`;
      return h;
    }
    if (!run.checked) return h;

    if (allRight()) {
      const ref = `${fmt(sf.vergleichswert, unit)} ${unit}`;
      const res = `${fmt(ex.ergebnis.wert, unit)} ${unit}`;
      if (!sf.aktiv) h += say("Richtig! Und dein Überschlag zeigt: Es müssen mehr Flaschen als Liter sein.");
      else if (isUp(run.guess) === isUp(sf.antwort)) h += say(`Richtig! Und es passt zu deiner Schätzung: ${res} ist ${run.guess} als ${ref}.`);
      else h += say(`Richtig gerechnet! Geschätzt hattest du ${run.guess} als ${ref}. Überleg mal, warum es ${sf.antwort} sein muss.`);
      return h;
    }

    // Fehler: erst die Schätzung als Kontrolle, dann gestufte Hilfe
    const placedResult = run.placed.ergebnis;
    if (sf.aktiv && placedResult && placedResult !== ex.bausteine.felder.ergebnis) {
      const contradicts = (num(placedResult) > Number(sf.vergleichswert)) !== isUp(run.guess);
      if (contradicts) {
        h += say(`Du hattest gesagt: ${run.guess} als ${fmt(sf.vergleichswert, unit)} ${unit}. Eingesetzt hast du ${placedResult}. Schau noch mal.`);
      }
    }
    const wrongCount = Object.keys(ex.bausteine.felder).filter((k) => run.placed[k] !== ex.bausteine.felder[k]).length;
    const chosen = ex.bausteine.antworten[run.answer];
    if (wrongCount) h += say(wrongCount === 1 ? "Fast! Ein Feld stimmt noch nicht." : `${wrongCount} Felder stimmen noch nicht.`);
    const reason = ex.bausteine.begruendungen[run.reason];
    if (reason && !reason.richtig) h += say(`Bei der Begründung: ${reason.grund}`);
    if (chosen && !chosen.richtig) h += say(`Beim Antwortsatz: ${chosen.grund}.`);
    const hints = [ex.hilfen.denkanstoss];
    if (ex.nachschlagen) hints.push(`Schau mal in ${ex.nachschlagen.material}, S. ${ex.nachschlagen.seite}, ${ex.nachschlagen.stelle}.`);
    hints.push(ex.hilfen.hinweis);
    hints.slice(0, run.hint).forEach((t) => { h += say(t); });
    if (run.hint < hints.length) {
      h += `<button type="button" class="px-hint-btn" data-hint="1" title="Tipp">${icon("Tipp")}</button>`;
    }
    return h;
  }

  function topbarHtml() {
    const ex = run.ex;
    return `
      <div class="px-topbar">
        <button type="button" class="practice-icon-btn" data-action="back" title="Zur Liste" aria-label="Zur Liste">${icon("Pfeil links")}</button>
        <span class="px-src">${esc(sourceLine(ex.quelle))}${ex.ableitung === "B" ? " · ähnliche Aufgabe" : ""}</span>
        <div class="px-stages" role="group" aria-label="Stufe">${stageButtons()}</div>
      </div>`;
  }

  function renderRun() {
    if (run.stage < 0) return renderGuided();
    const ex = run.ex;
    const done = run.checked && allRight();
    runView.innerHTML = `
      ${topbarHtml()}
      <div class="px-layout">
        <div class="px-sheet">
          <p class="px-task">${esc(ex.aufgabentext)}</p>
          ${ex.bausteine.begruendungen.length ? `<div class="px-answers"><span class="px-label">Begründung:</span>${reasonsHtml(ex)}</div>` : ""}
          ${ex.schema === "rechnung" ? calcHtml(ex) : tableHtml(ex)}
          <div class="px-answers"><span class="px-label">A:</span>${answersHtml(ex)}</div>
        </div>
        <aside class="px-side">
          <div class="px-luna" aria-live="polite">${lunaHtml()}</div>
          <div class="px-palette">${paletteHtml(ex)}</div>
          <div class="px-actions">
            ${done ? nextButtons() : `<button type="button" class="px-check" data-action="check" title="Prüfen" aria-label="Prüfen"${run.guess && allFilled() ? "" : " disabled"}>${icon("Haken")}</button>`}
          </div>
        </aside>
      </div>`;
  }


  function stageButtons() {
    const family = run.ex.zwilling_von || run.ex.id;
    const done = new Set(overview && overview.stand[family] ? overview.stand[family].geschafft : []);
    return STAGES.map(({ n, title }) =>
      `<button type="button" class="px-stage${n === run.stage ? " active" : ""}${done.has(n) ? " done" : ""}" data-stage="${n}" title="${esc(title)}" aria-label="${stageName(n)}: ${esc(title)}">${stageMark(n)}</button>`
    ).join("");
  }

  function nextButtons() {
    const ex = run.ex;
    const twinId = ex.ableitung === "A" ? ex.zwillinge[0] : ex.zwilling_von;
    if (!twinId) return `<button type="button" class="px-check secondary" data-action="back" title="Zur Liste">${icon("Erledigt")}</button>`;
    return `
      <button type="button" class="px-check" data-action="open" data-id="${esc(twinId)}" title="${ex.ableitung === "A" ? "Ähnliche Aufgabe" : "Original"}">${icon("Wiederholen")}</button>
      <button type="button" class="px-check secondary" data-action="back" title="Zur Liste">${icon("Erledigt")}</button>`;
  }

  // ---------- Stufe -1: Gedankengang ----------
  // Ein Satz nach dem anderen; Lücken sind Felder. Zwei Wege hinein: Zahlentasten (Finger wählt das
  // Kästchen) oder das Schreibfeld darunter: derselbe Zeichenkern wie die Tafel (kein Stocken wie bei
  // Scribble), die Ziffern erkennt js/digit_ink.js im Browser. Die gelesene Zahl steht sofort im Kästchen.
  // Bestätigte Ziffern (richtiger Schritt, gelesene Zahl unverändert) werden zu Mustern für Theas Schrift.
  // Ein Fehler markiert nur das Kästchen, ab dem zweiten gibt es den Tipp, ab dem dritten die Zahlen.

  // „2,40“, „2.4“, „1.500“, „10 €“ → Zahl; leer oder unlesbar → NaN
  function parseAnswer(text) {
    let t = String(text).replace(/[^\d,.-]/g, "");
    if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
    else if (/^\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, "");
    return t ? Number(t) : NaN;
  }
  const sameNumber = (a, b) => Math.abs(parseAnswer(a) - parseAnswer(b)) < 1e-9;

  function guidedSentence(sentence, index) {
    const g = run.guided;
    const current = !g.done && index === g.step;
    let k = 0;
    return esc(sentence).replace(/\[\[([^\]]+)\]\]/g, (_, expected) => {
      const id = `${index}-${k++}`;
      if (!current) return `<span class="gg-filled">${expected}</span>`;
      const wrong = g.wrong.has(id) ? " wrong" : "";
      const active = g.active === id ? " active" : "";
      return `<input class="gg-blank${wrong}${active}" data-blank="${id}" data-expect="${expected}" value="${esc(g.values[id] || "")}"${COARSE ? " readonly" : ""}
        inputmode="decimal" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"
        aria-label="Lücke" style="--len:${Math.max(2, expected.length)}">`;
    });
  }

  function guidedLuna() {
    const g = run.guided, steps = run.ex.gedankengang;
    const say = (t) => `<div class="px-say">${icon("Luna", "px-luna-icon")}<p>${esc(t)}</p></div>`;
    if (g.done) return say("Geschafft! Du hast den ganzen Rechenweg aufgeschrieben.");
    const step = steps[g.step];
    let h = "";
    if (g.unreadable) h += say("Eine Ziffer konnte ich nicht lesen. Schreib sie noch mal oder tipp sie ein.");
    else if (g.empty) h += say("Da fehlt noch eine Zahl.");
    else if (g.wrong.size) h += say(g.wrong.size === 1 ? "Fast! Schau noch mal auf das markierte Kästchen." : "Schau noch mal auf die markierten Kästchen.");
    else if (g.step === 0 && !g.fails) h += say("Ergänze die fehlenden Zahlen.");
    if (g.tip && step.tipp) h += say(step.tipp);
    const buttons = [];
    if (step.tipp && !g.tip && g.fails >= 1) buttons.push(`<button type="button" class="px-hint-btn" data-action="gg-tip" title="Tipp" aria-label="Tipp">${icon("Tipp")}</button>`);
    if (g.fails >= 2) buttons.push(`<button type="button" class="px-hint-btn" data-action="gg-show" title="Zahlen zeigen" aria-label="Zahlen zeigen">${icon("Anzeigen")}</button>`);
    return h + (buttons.length ? `<div class="gg-help">${buttons.join("")}</div>` : "");
  }

  function guidedNextButtons() {
    const ex = run.ex;
    const twinId = ex.ableitung === "A" ? ex.zwillinge[0] : ex.zwilling_von;
    let h = `<button type="button" class="px-check" data-stage="0" title="Weiter mit den Bausteinen" aria-label="Weiter mit den Bausteinen">${icon("Pfeil hoch")}<span>0</span></button>`;
    if (twinId) h += `<button type="button" class="px-check secondary" data-action="open" data-id="${esc(twinId)}" data-at="-1" title="Ähnliche Aufgabe">${icon("Wiederholen")}</button>`;
    return h + `<button type="button" class="px-check secondary" data-action="back" title="Zur Liste">${icon("Erledigt")}</button>`;
  }

  function keepGuidedInput() {
    runView.querySelectorAll(".gg-blank").forEach((inp) => { run.guided.values[inp.dataset.blank] = inp.value; });
  }

  const PAD_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ",", "0", "⌫"];
  // Auf dem iPad sind die Felder nur auswählbar: geschrieben wird im Schreibfeld, getippt mit den Tasten
  const COARSE = window.matchMedia("(pointer: coarse)").matches;

  // ---------- Schreibfeld (ein Exemplar, wird bei jedem Zeichnen der Ansicht nur umgehängt) ----------
  let pad = null;
  let handwriting = null;  // Theas bestätigte Ziffern (vom Server)

  function loadHandwriting() {
    if (handwriting) return;
    handwriting = [];
    apiJson("/api/v1/practice/handwriting")
      .then((data) => { handwriting = data.samples || []; })
      .catch((err) => console.warn("Handschrift-Muster nicht geladen:", err));
  }

  function writingPad() {
    if (pad || typeof createInkSurface !== "function" || typeof DigitInk === "undefined") return pad;
    const el = document.createElement("div");
    el.className = "gg-write";
    el.innerHTML = `
      <div class="gg-write-area" title="Hier schreiben"><canvas class="gg-write-ink"></canvas><canvas class="gg-write-overlay"></canvas></div>
      <button type="button" class="gg-key gg-write-clear" data-pad="clear" title="Neu schreiben" aria-label="Neu schreiben">${icon("Radierer")}</button>`;
    const area = el.querySelector(".gg-write-area");
    const ink = el.querySelector(".gg-write-ink"), overlay = el.querySelector(".gg-write-overlay");
    const surface = createInkSurface({
      viewport: area, inkCanvas: ink, overlayCanvas: overlay,
      btnScrollTop: null, scrollTrack: null, scrollThumb: null,
      btnWbZoomIn: null, btnWbZoomOut: null, btnWbZoomReset: null, wbZoomLevelText: null,
      docUnderlay: null, docUnderlayImg: null, tasksLayer: null,
      inkCtx: ink.getContext("2d", { desynchronized: true }), overlayCtx: overlay.getContext("2d"),
      stopTutorSpeech: () => {},
      scheduleAutoSave: () => padStrokeDone(),  // „Strich fertig“ (oder radiert)
      sendCanvasUpdate: () => {},
    });
    pad = { el, surface, timer: null, gap: null, chars: null, text: null };
    loadHandwriting();
    return pad;
  }

  function clearPad() {
    if (!pad) return;
    clearTimeout(pad.timer);
    pad.surface.strokes = [];
    pad.surface.undoStack = [];
    pad.surface.redoStack = [];
    pad.surface.redrawAllStrokes();
    pad.gap = null;
    pad.chars = null;
    pad.text = null;
  }

  function padStrokeDone() {
    clearTimeout(pad.timer);
    pad.timer = setTimeout(readPad, 450);
  }

  // Striche lesen und die Zahl ins aktive Kästchen schreiben
  function readPad() {
    if (!run || run.stage >= 0 || !pad) return;
    const g = run.guided;
    ensureActive();
    const inp = runView.querySelector(`.gg-blank[data-blank="${g.active}"]`);
    const strokes = pad.surface.strokes.filter((st) => st.tool === "pen" && st.points && st.points.length);
    if (!inp || !strokes.length) return;
    const result = DigitInk.recognize(strokes, handwriting);
    pad.gap = g.active;
    pad.chars = result.chars;
    pad.text = result.text;
    inp.value = result.text;
    inp.classList.remove("wrong");
    g.values[g.active] = result.text;
    g.unreadable = result.unsure;
    const luna = runView.querySelector(".gg .px-luna");
    if (luna) luna.innerHTML = guidedLuna();
  }

  // Richtiger Schritt: Ziffern, deren gelesene Zahl unverändert die Lösung war, werden Muster für Theas Schrift
  function learnFromPad(expectedById) {
    if (!pad || !pad.chars || !pad.gap) return;
    const value = run.guided.values[pad.gap];
    if (value !== pad.text || pad.text.includes("?") || !sameNumber(value, expectedById[pad.gap])) return;
    const samples = pad.chars.filter((c) => /^[0-9]$/.test(c.label)).map((c) => DigitInk.toStored(c.label, c.strokes));
    if (!samples.length) return;
    handwriting = (handwriting || []).concat(samples);
    apiJson("/api/v1/practice/handwriting", { method: "POST", json: { samples } })
      .then((data) => { handwriting = data.samples; })
      .catch((err) => console.warn("Handschrift-Muster nicht gespeichert:", err));
  }

  function mountPad() {
    const slot = runView.querySelector(".gg-write-slot");
    const p = writingPad();
    if (!slot || !p) return;
    slot.replaceWith(p.el);
    p.surface.currentColor = getComputedStyle(runView).color || "#f8fafc";
    p.surface.currentTool = "pen";
    p.surface.resizeCanvases();
    p.surface.redrawAllStrokes();
  }

  function padHtml() {
    return `<div class="gg-pad" role="group" aria-label="Zahlen">${PAD_KEYS.map((k) => k === "⌫"
      ? `<button type="button" class="gg-key" data-key="back" title="Löschen" aria-label="Löschen">${icon("Rückgängig")}</button>`
      : `<button type="button" class="gg-key" data-key="${k}">${k}</button>`).join("")}</div>`;
  }

  // Aktives Kästchen: das zuletzt gewählte, sonst das erste leere des aktuellen Satzes
  function ensureActive() {
    const g = run.guided;
    const ids = [...runView.querySelectorAll(".gg-blank")].map((inp) => inp.dataset.blank);
    if (!ids.includes(g.active)) g.active = ids.find((id) => !g.values[id]) || ids[0] || null;
    if (pad && pad.gap && pad.gap !== g.active) clearPad();  // neues Kästchen, neues Schreibfeld
    runView.querySelectorAll(".gg-blank").forEach((inp) => inp.classList.toggle("active", inp.dataset.blank === g.active));
  }

  function guidedKey(key) {
    const g = run.guided;
    ensureActive();
    const inp = runView.querySelector(`.gg-blank[data-blank="${g.active}"]`);
    if (!inp) return;
    inp.value = key === "back" ? inp.value.slice(0, -1) : (inp.value + key).slice(0, 12);
    inp.classList.remove("wrong");
    g.values[g.active] = inp.value;
  }

  function renderGuided() {
    keepGuidedInput();
    const ex = run.ex, g = run.guided, steps = ex.gedankengang;
    const shown = steps.slice(0, g.done ? steps.length : g.step + 1);
    runView.innerHTML = `
      ${topbarHtml()}
      <div class="gg">
        <p class="px-task">${esc(ex.aufgabentext)}</p>
        <ol class="gg-steps">
          ${shown.map((s, i) => `<li class="gg-step${g.done || i < g.step ? " done" : " current"}">${guidedSentence(s.satz, i)}</li>`).join("")}
        </ol>
        ${g.done ? "" : `<div class="gg-write-slot"></div>${padHtml()}`}
        <div class="px-luna" aria-live="polite">${guidedLuna()}</div>
        <div class="px-actions">
          ${g.done ? guidedNextButtons() : `<button type="button" class="px-check" data-action="gg-check" title="Prüfen" aria-label="Prüfen">${icon("Haken")}</button>`}
        </div>
      </div>`;
    ensureActive();
    if (!g.done) mountPad();
    // Mit Tastatur gleich ins erste leere Feld; auf dem iPad nicht (sonst klappt die Bildschirmtastatur auf)
    if (window.matchMedia("(hover: hover)").matches) {
      const first = [...runView.querySelectorAll(".gg-blank")].find((inp) => !inp.value);
      if (first) first.focus();
    }
  }

  function guidedCheck() {
    keepGuidedInput();
    const g = run.guided, steps = run.ex.gedankengang;
    const inputs = [...runView.querySelectorAll(".gg-blank")];
    g.empty = inputs.some((inp) => !inp.value.trim());
    if (g.empty) { g.wrong = new Set(); return renderGuided(); }
    g.wrong = new Set(inputs.filter((inp) => !sameNumber(inp.value, inp.dataset.expect)).map((inp) => inp.dataset.blank));
    if (g.wrong.size) {
      g.fails += 1;
      logPracticeEvent(run.attempt, "check", { status: "noch_nicht", schritt: g.step + 1,
        gelesen: inputs.filter((inp) => g.wrong.has(inp.dataset.blank)).map((inp) => inp.value) });
      return renderGuided();
    }
    learnFromPad(Object.fromEntries(inputs.map((inp) => [inp.dataset.blank, inp.dataset.expect])));
    clearPad();
    g.step += 1;
    g.fails = 0;
    g.tip = false;
    g.unreadable = false;
    if (g.step >= steps.length) {
      g.done = true;
      logPracticeEvent(run.attempt, "check", { status: "richtig", schritte: steps.length });
    }
    renderGuided();
  }

  function guidedReveal() {
    runView.querySelectorAll(".gg-blank").forEach((inp) => { inp.value = inp.dataset.expect; inp.classList.remove("wrong"); });
    run.guided.wrong = new Set();
    logPracticeEvent(run.attempt, "solution", { schritt: run.guided.step + 1 });
    renderGuided();
  }

  runView.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.classList && e.target.classList.contains("gg-blank")) {
      e.preventDefault();
      guidedCheck();
    }
  });
  runView.addEventListener("input", (e) => {
    if (e.target.classList && e.target.classList.contains("gg-blank")) e.target.classList.remove("wrong");
  });
  // Finger wählt nur das Kästchen (keine Bildschirmtastatur, die Zahlentasten tippen); Pencil und Maus
  // fokussieren normal – der Pencil schreibt dann über Scribble
  runView.addEventListener("pointerdown", (e) => {
    const inp = e.target.closest && e.target.closest(".gg-blank");
    if (!inp || !run) return;
    if (e.pointerType === "touch") e.preventDefault();
    run.guided.active = inp.dataset.blank;
    ensureActive();
  });
  runView.addEventListener("focusin", (e) => {
    if (!run || !e.target.classList || !e.target.classList.contains("gg-blank")) return;
    run.guided.active = e.target.dataset.blank;
    ensureActive();
  });

  // ---------- Bedienung: Antippen und Ziehen ----------

  function place(slotId, token) {
    run.placed[slotId] = token;
    run.selected = null;
    if (run.checked) { run.checked = false; }
    renderRun();
  }

  runView.addEventListener("click", (e) => {
    if (!run) return;
    const t = e.target.closest("button");
    if (!t || t.disabled) return;
    if (t.dataset.action === "back") return closeExercise();
    if (t.dataset.stage !== undefined) {
      const stage = Number(t.dataset.stage);
      if (stage <= 0) return stage === run.stage ? undefined : openExercise(run.ex.id, stage);
      if (typeof window.openPracticeOnWhiteboard !== "function") return;
      return window.openPracticeOnWhiteboard({ exerciseId: run.ex.id, stage, title: practiceBoardTitle(run.ex.quelle, run.ex.ableitung, stage) });
    }
    if (t.dataset.action === "open") return openExercise(t.dataset.id, Number(t.dataset.at || 0));
    if (t.dataset.action === "gg-check") return guidedCheck();
    if (t.dataset.key !== undefined) return guidedKey(t.dataset.key);
    if (t.dataset.pad === "clear") {
      const gap = pad && (pad.gap || run.guided.active);
      clearPad();
      const inp = gap && runView.querySelector(`.gg-blank[data-blank="${gap}"]`);
      if (inp) { inp.value = ""; run.guided.values[gap] = ""; }
      run.guided.unreadable = false;
      return;
    }
    if (t.dataset.action === "gg-tip") { run.guided.tip = true; logPracticeEvent(run.attempt, "hint", { schritt: run.guided.step + 1 }); return renderGuided(); }
    if (t.dataset.action === "gg-show") return guidedReveal();
    if (t.dataset.action === "check") {
      run.checked = true;
      logPracticeEvent(run.attempt, "check", checkResult());
      return renderRun();
    }
    if (t.dataset.guess) {
      run.guess = t.dataset.guess;
      logPracticeEvent(run.attempt, "guess", { value: run.guess });
      return renderRun();
    }
    if (t.dataset.hint) {
      run.hint += 1;
      logPracticeEvent(run.attempt, "hint", { stufe: run.hint });
      return renderRun();
    }
    if (t.dataset.reason !== undefined) {
      if (run.checked && allRight()) return;
      run.reason = Number(t.dataset.reason);
      run.checked = false;
      return renderRun();
    }
    if (t.dataset.answer !== undefined) {
      if (run.checked && allRight()) return;
      run.answer = Number(t.dataset.answer);
      run.checked = false;
      return renderRun();
    }
    if (t.dataset.token !== undefined) {
      if (dragMoved) return;
      run.selected = run.selected === t.dataset.token ? null : t.dataset.token;
      run.selectedKind = t.dataset.kind;
      return renderRun();
    }
    if (t.dataset.slot) {
      if (!run.guess || (run.checked && allRight())) return;
      if (run.selected && run.selectedKind === t.dataset.kind) return place(t.dataset.slot, run.selected);
      if (run.placed[t.dataset.slot]) {  // gefülltes Feld antippen = leeren
        delete run.placed[t.dataset.slot];
        run.checked = false;
        renderRun();
      }
    }
  });

  // Ziehen mit Finger oder Pencil: Kopie folgt dem Zeiger, Ablegen auf einem passenden Feld
  let drag = null;
  let dragMoved = false;
  runView.addEventListener("pointerdown", (e) => {
    const tok = e.target.closest(".px-token");
    if (!tok || tok.disabled) return;
    dragMoved = false;
    drag = { token: tok.dataset.token, kind: tok.dataset.kind, x: e.clientX, y: e.clientY, ghost: null };
  });
  window.addEventListener("pointermove", (e) => {
    if (!drag) return;
    if (!drag.ghost && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 8) {
      dragMoved = true;
      drag.ghost = document.createElement("div");
      drag.ghost.className = `px-token px-kind-${drag.kind} px-ghost`;
      drag.ghost.textContent = drag.token;
      document.body.appendChild(drag.ghost);
    }
    if (drag.ghost) {
      drag.ghost.style.left = `${e.clientX}px`;
      drag.ghost.style.top = `${e.clientY}px`;
    }
  });
  window.addEventListener("pointerup", (e) => {
    if (!drag) return;
    const d = drag;
    drag = null;
    if (!d.ghost) return;
    d.ghost.remove();
    const target = document.elementFromPoint(e.clientX, e.clientY)?.closest(".px-slot");
    if (target && target.dataset.kind === d.kind && run) place(target.dataset.slot, d.token);
    setTimeout(() => { dragMoved = false; }, 0);
  });
  window.addEventListener("pointercancel", () => {
    if (drag && drag.ghost) drag.ghost.remove();
    drag = null;
  });

  // ---------- Einstieg ----------

  navBtn.addEventListener("click", () => {
    if (!run) loadPracticeList().catch((err) => console.warn("Übungen nicht geladen:", err));
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
