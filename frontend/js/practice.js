// ==========================================================================
// Üben: Übungen aus echten Aufgaben (Probebetrieb, Schalter GOTHEA_EXERCISE_TRIAL)
// --------------------------------------------------------------------------
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

  // Stufe 0 = Bausteine hier; 1–4 = Blatt auf einer neuen Tafel, mit dem Pencil (weniger Gerüst je Stufe)
  const STAGE_TITLES = [
    "Bausteine einsetzen",
    "Tafel: Tabelle vorgegeben, Antwort angefangen",
    "Tafel: nur Tabellenkopf",
    "Tafel: nur R: und A:",
    "Tafel: leeres Blatt wie im Test",
  ];

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
    if (!stage || typeof window.openPracticeOnWhiteboard !== "function") return openExercise(exerciseId);
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
      <span class="practice-suggest-go">${icon(SUGGESTION_ICONS[sug.art] || "Pfeil rechts")}<span class="practice-stage-no">${sug.stufe}</span></span>`;
    card.addEventListener("click", () => startPractice(sug, family));
    return card;
  }

  function stageDots(stand) {
    const done = new Set(stand ? stand.geschafft : []);
    const next = stand ? stand.naechste_stufe : 0;
    return STAGE_TITLES.map((title, n) => {
      const cls = done.has(n) ? " done" : n === next ? " next" : "";
      const label = `Stufe ${n}: ${title}${done.has(n) ? " (geschafft)" : ""}`;
      return `<button type="button" class="practice-dot${cls}" data-stage="${n}" title="${esc(label)}" aria-label="${esc(label)}"><span>${n}</span></button>`;
    }).join("");
  }

  function buildRow(ex, stand) {
    const row = document.createElement("div");
    row.className = "practice-row";
    row.dataset.id = ex.id;
    row.style.setProperty("--subject-color", subjectColor("sub_math"));
    const anti = ex.schema === "dreisatz_antiproportional";
    const next = stand && stand.naechste_stufe !== null ? stand.naechste_stufe : 0;
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
        <span class="practice-dot next" aria-label="Stufe ${r.stufe}"><span>${r.stufe}</span></span>
      </button>`;
    row.querySelector(".practice-row-main").addEventListener("click", () => startPractice(r, family));
    return row;
  }

  // ---------- Übung ----------

  async function openExercise(id) {
    const ex = await apiJson(`/api/v1/practice/${encodeURIComponent(id)}`);
    run = { ex, guess: null, placed: {}, answer: null, reason: null, checked: false, hint: 0, selected: null,
            attempt: startPracticeAttempt(ex.id, 0) };
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

  function renderRun() {
    const ex = run.ex;
    const done = run.checked && allRight();
    runView.innerHTML = `
      <div class="px-topbar">
        <button type="button" class="practice-icon-btn" data-action="back" title="Zur Liste" aria-label="Zur Liste">${icon("Pfeil links")}</button>
        <span class="px-src">${esc(sourceLine(ex.quelle))}${ex.ableitung === "B" ? " · ähnliche Aufgabe" : ""}</span>
        <div class="px-stages" role="group" aria-label="Stufe">${stageButtons()}</div>
      </div>
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
    return STAGE_TITLES.map((title, n) =>
      `<button type="button" class="px-stage${n === 0 ? " active" : ""}${done.has(n) ? " done" : ""}" data-stage="${n}" title="${esc(title)}" aria-label="Stufe ${n}: ${esc(title)}">${n}</button>`
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
      if (stage === 0 || typeof window.openPracticeOnWhiteboard !== "function") return;
      return window.openPracticeOnWhiteboard({ exerciseId: run.ex.id, stage, title: practiceBoardTitle(run.ex.quelle, run.ex.ableitung, stage) });
    }
    if (t.dataset.action === "open") return openExercise(t.dataset.id);
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
