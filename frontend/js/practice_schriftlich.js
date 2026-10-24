// ==========================================================================
// Üben, Übungstyp „Schriftlich rechnen“ (backend: services/exercise_types/schriftlich.py)
// --------------------------------------------------------------------------
// Addition, Subtraktion, Multiplikation, Division im Kästchengitter. Gitter, Schritte
// (Regelsätze aus dem Merkblatt der Eltern) und Fehlerbild rechnet der Server; hier
// nur Anzeige, Eingabe und Prüfung.
// Stufen: -2 Zuschauen (Schritt für Schritt mit Regelsatz, „Weiter“), -1 Antippen
// (Frage mit drei Antworten je Schritt), 1 Ergebnis eintragen, 2 Zwischenzeilen,
// Überträge und Ergebnis eintragen, 3 Aufgabe selbst stellengerecht aufschreiben
// (darf als Ganzes verschoben stehen), 4 Fehler finden (antippen, dann verbessern).
// Eingabe: Kästchen antippen, Zahlentasten; der Cursor läuft in Rechenrichtung weiter
// (rechts nach links, bei der Division in der Aufgabenzeile links nach rechts).
// Daneben die Nebenrechnung (Kästchen, Stift, kein Lesen; js/digit_pad.js).
// Überträge und nicht zwingende Nullen dürfen leer bleiben.
// ==========================================================================

(function () {
  const runView = document.getElementById("practice-run-view");
  if (!runView) return;

  let core = null;
  // { ex, stage, attempt, step, answered, wrongOpts, entries: {pos: z}, active, checked, wrong: Set(pos),
  //   fails, tip, done, logged, found, misses, offset }
  let run = null;
  let pad = null;

  const esc = (s) => escapeHtml(String(s));
  const say = (t) => `<div class="px-say">${icon("Luna", "px-luna-icon")}<p>${esc(t)}</p></div>`;
  const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ",", "0", "⌫"];
  const OFFSETS = [0, -1, 1, -2, 2, -3, 3];  // Stufe 3: so weit darf die ganze Rechnung verschoben stehen

  const key = (r, c) => `${r},${c}`;
  const grid = () => run.ex.gitter;
  const rowInfo = (r) => grid().zeilen_info[String(r)] || {};
  const plainCells = () => grid().zellen;
  const byPos = (cells) => Object.fromEntries(cells.map((c) => [key(c.r, c.c), c]));
  const steps = () => run.ex.schritte;

  // Schritt, der eine Zelle aufdeckt (für Tipps)
  function stepOf(cellId) {
    return steps().find((st) => st.zellen.includes(cellId));
  }

  // ---------- Was ist sichtbar, was wird eingetragen? ----------

  const INPUT_KINDS = { 1: ["ergebnis"], 2: ["null", "uebertrag", "zwischen", "ergebnis"],
                        3: ["aufgabe", "null", "uebertrag", "zwischen", "ergebnis"] };

  // Erwartete Eingaben: Position → Zelle (Stufe 3 um run.offset verschoben)
  function expected(offset = 0) {
    const kinds = INPUT_KINDS[run.stage] || [];
    const out = {};
    plainCells().filter((c) => kinds.includes(c.art)).forEach((c) => { out[key(c.r, c.c + offset)] = c; });
    return out;
  }

  const opPositions = () => new Set(plainCells().filter((c) => c.art === "op").map((c) => key(c.r, c.c)));

  // Fehlerbild (Stufe 4): Positionen, an denen es von der Lösung abweicht
  function errorDiff() {
    const plain = byPos(plainCells()), wrong = byPos(run.ex.fehlerbild.zellen);
    return new Set([...new Set([...Object.keys(plain), ...Object.keys(wrong)])]
      .filter((p) => (plain[p] ? plain[p].z : "") !== (wrong[p] ? wrong[p].z : "")));
  }

  function isInput(p) {
    if (run.done) return false;
    if (run.stage === 1 || run.stage === 2) return p in expected();
    if (run.stage === 3) return !opPositions().has(p);
    if (run.stage === 4) return run.found ? errorDiff().has(p) : true;
    return false;
  }

  function cellText(p, plain) {
    const c = plain[p];
    if (run.stage < 0) {
      if (!c) return "";
      const shown = c.art === "aufgabe" || c.art === "op" || stepsShown().some((st) => st.zellen.includes(c.id));
      return shown ? c.z : "";
    }
    if (run.stage === 4) {
      if (run.found && errorDiff().has(p)) return run.entries[p] || "";
      const w = byPos(run.ex.fehlerbild.zellen)[p];
      return run.done && c ? c.z : (w ? w.z : "");
    }
    if (isInput(p) || (run.stage === 3 && !(c && c.art === "op"))) return run.entries[p] || "";
    return c ? c.z : "";
  }

  // Zuschauen/Antippen: aufgedeckte Schritte
  function stepsShown() {
    const upto = run.stage === -1 && !run.answered ? run.step : run.step + 1;
    return steps().slice(0, upto);
  }

  // ---------- Gitter ----------

  function gridHtml() {
    const g = grid(), plain = byPos(plainCells());
    // Spalten, in denen nur Kommas stehen, sind schmal
    const narrow = new Set();
    for (let c = 0; c < g.spalten; c++) {
      const col = plainCells().filter((x) => x.c === c);
      if (col.length && col.every((x) => x.z === ",")) narrow.add(c);
    }
    const cols = Array.from({ length: g.spalten }, (_, c) => (narrow.has(c) ? "calc(var(--cell) * 0.5)" : "var(--cell)")).join(" ");
    const rows = Array.from({ length: g.zeilen }, (_, r) => (rowInfo(r).klein ? "calc(var(--cell) * 0.62)" : "var(--cell)")).join(" ");
    // Strich unter einer Zeile: kleine Übertragszeile über die ganze Rechnung, sonst unter ihren Zellen
    // Zuschauen/Antippen: erst mit der aufgedeckten Zeile; Stufe 3 ohne Striche (sie verrieten den Aufbau)
    const extent = {};
    for (let r = 0; r < g.zeilen; r++) {
      if (!rowInfo(r).strich || run.stage === 3) continue;
      if (run.stage < 0 && !plainCells().some((x) => x.r >= r && cellText(key(x.r, x.c), plain))) continue;
      const cs = (rowInfo(r).klein ? plainCells() : plainCells().filter((x) => x.r === r)).map((x) => x.c);
      if (cs.length) extent[r] = [Math.min(...cs), Math.max(...cs)];
    }
    const current = new Set(run.stage < 0 ? (steps()[run.step] || { zellen: [] }).zellen : []);
    let h = "";
    for (let r = 0; r < g.zeilen; r++) {
      for (let c = 0; c < g.spalten; c++) {
        const p = key(r, c), cell = plain[p];
        const text = cellText(p, plain);
        const cls = ["sr-cell"];
        if (rowInfo(r).klein) cls.push("klein");
        if (extent[r] && c >= extent[r][0] && c <= extent[r][1]) cls.push("strich");
        if (cell && cell.art === "op") cls.push("op");
        if (cell && current.has(cell.id) && (run.stage === -2 || run.answered)) cls.push("neu");
        const style = `grid-row:${r + 1};grid-column:${c + 1}`;
        if (isInput(p)) {
          cls.push("in");
          if (run.active === p) cls.push("active");
          if (run.wrong.has(p)) cls.push("wrong");
          if (run.done) cls.push("ok");
          h += `<button type="button" class="${cls.join(" ")}" style="${style}" data-cell="${p}" aria-label="Kästchen">${esc(text)}</button>`;
        } else if (text || cls.length > 1) {
          // geschafft: was Thea eingetragen hat, grün
          if (run.done && (run.stage === 4 ? errorDiff().has(p) : run.stage >= 1 && p in expected(run.offset))) cls.push("ok");
          h += `<span class="${cls.join(" ")}" style="${style}">${esc(text)}</span>`;
        }
      }
    }
    return `<div class="sr-grid" style="grid-template-columns:${cols};grid-template-rows:${rows}">${h}</div>`;
  }

  // Kästchengröße so, dass das Gitter in seinen Bereich passt
  function fitGrid() {
    const wrap = runView.querySelector(".sr-wrap");
    if (!wrap || !run) return;
    const g = grid();
    const narrowCols = new Set(plainCells().filter((x) => x.z === ",").map((x) => x.c)).size;
    const unitsW = g.spalten - 0.5 * narrowCols;
    const unitsH = Array.from({ length: g.zeilen }, (_, r) => (rowInfo(r).klein ? 0.62 : 1)).reduce((a, b) => a + b, 0);
    const size = Math.floor(Math.min(56, wrap.clientWidth / unitsW, wrap.clientHeight / unitsH));
    wrap.style.setProperty("--cell", `${Math.max(18, size)}px`);
  }
  window.addEventListener("resize", () => { if (run) fitGrid(); });

  // ---------- Luna, Knöpfe ----------

  function lunaHtml() {
    const st = steps()[run.step];
    if (run.stage === -2) return run.done ? say("So geht die Rechnung. Jetzt bist du dran!") : say(st.satz);
    if (run.stage === -1) {
      if (run.done) return say("Geschafft! Du hast jeden Schritt gewusst.");
      if (run.answered || !st.frage) return say(st.satz);
      let h = say(st.frage);
      h += `<div class="sr-options">${st.optionen.map((o) => `<button type="button" class="px-guess-btn sr-option${run.wrongOpts.has(o) ? " wrong" : ""}"
        data-option="${esc(o)}"${run.wrongOpts.has(o) ? " disabled" : ""}>${esc(o)}</button>`).join("")}</div>`;
      return h;
    }
    if (run.stage === 4) {
      if (run.done) return say("Richtig verbessert!");
      if (!run.found) {
        let h = say(run.misses ? "Da stimmt es. Such weiter." : "In dieser Rechnung steckt ein Fehler. Tipp ihn an.");
        if (run.misses >= 2) h += say(run.ex.fehlerbild.satz);
        return h;
      }
      return say(`${run.ex.fehlerbild.satz} Verbessere die Rechnung.`) + (run.checked && run.wrong.size ? say("Noch nicht ganz.") : "");
    }
    if (run.done) return say(run.fails ? "Geschafft!" : "Richtig gerechnet!");
    if (!run.checked) {
      return say({ 1: "Trag das Ergebnis ein.", 2: "Rechne Schritt für Schritt und trag alles ein.",
                   3: "Schreib die Aufgabe selbst stellengerecht auf und rechne." }[run.stage]);
    }
    let h = say(run.missing && !run.wrongEntered ? "Da fehlen noch Ziffern." : "Schau noch mal auf die markierten Kästchen.");
    if (run.tip && run.tipText) h += say(run.tipText);
    return h;
  }

  function actionsHtml() {
    if (run.done) return nextButtons();
    if (run.stage === -2) {
      return `<button type="button" class="px-check" data-action="sr-next" title="Weiter" aria-label="Weiter">${icon("Pfeil rechts")}</button>`;
    }
    if (run.stage === -1) {
      return run.answered || !steps()[run.step].frage
        ? `<button type="button" class="px-check" data-action="sr-next" title="Weiter" aria-label="Weiter">${icon("Pfeil rechts")}</button>` : "";
    }
    if (run.stage === 4 && !run.found) return "";
    let h = "";
    if (run.stage !== 4 && run.fails >= 1 && !run.tip) h += `<button type="button" class="px-check secondary" data-action="sr-tip" title="Tipp" aria-label="Tipp">${icon("Tipp")}</button>`;
    if (run.fails >= 2) h += `<button type="button" class="px-check secondary" data-action="sr-show" title="Lösung zeigen" aria-label="Lösung zeigen">${icon("Anzeigen")}</button>`;
    return h + `<button type="button" class="px-check" data-action="sr-check" title="Prüfen" aria-label="Prüfen">${icon("Haken")}</button>`;
  }

  function nextButtons() {
    if (core.inRound()) return core.roundNextHtml();
    const ex = run.ex;
    const next = ex.stufen.find((s) => s > run.stage);
    const twinId = ex.zwilling_von || ex.zwillinge[0];
    let h = next !== undefined
      ? `<button type="button" class="px-check" data-stage="${next}" title="Weiter mit Stufe ${next}" aria-label="Weiter mit Stufe ${next}">${icon("Pfeil hoch")}<span>${next}</span></button>` : "";
    if (twinId) h += `<button type="button" class="px-check secondary" data-action="open" data-id="${esc(twinId)}" data-at="${run.stage}" title="Ähnliche Aufgabe">${icon("Wiederholen")}</button>`;
    return h + `<button type="button" class="px-check secondary" data-action="back" title="Zur Liste">${icon("Erledigt")}</button>`;
  }

  const typing = () => !run.done && (run.stage >= 1 && run.stage <= 3 || (run.stage === 4 && run.found));

  function keysHtml() {
    return `<div class="gg-pad sr-keys" role="group" aria-label="Zahlen">${KEYS.map((k) => k === "⌫"
      ? `<button type="button" class="gg-key" data-key="back" title="Löschen" aria-label="Löschen">${icon("Rückgängig")}</button>`
      : `<button type="button" class="gg-key" data-key="${k}">${k}</button>`).join("")}</div>`;
  }

  // Feste Seite in Bildschirmhöhe: links Aufgabe und Gitter, rechts Luna, Tasten, Nebenrechnung, Knöpfe
  function render() {
    core.setZen(true);
    const ex = run.ex;
    const pre = ex.vorspann && run.stage <= 2 ? `<p class="sr-pre">${esc(ex.vorspann)}</p>` : "";
    runView.innerHTML = `
      ${core.topbarHtml(ex, run.stage)}
      <div class="sr${run.stage >= 1 ? " sr-typing" : ""}">
        <div class="sr-left">
          <p class="px-task sr-task">${esc(ex.aufgabentext)}</p>
          ${pre}
          <div class="sr-wrap">${gridHtml()}</div>
        </div>
        <div class="sr-right">
          <div class="px-luna" aria-live="polite">${lunaHtml()}</div>
          ${typing() ? keysHtml() : ""}
          ${run.stage >= 1 && !run.done ? `<div class="gg-write-slot"></div>` : ""}
          <div class="px-actions sr-actions">${actionsHtml()}</div>
        </div>
      </div>`;
    fitGrid();
    if (run.stage >= 1 && !run.done) {
      if (!pad) pad = createDigitPad({ recognize: false });
      if (pad) pad.mount(runView.querySelector(".gg-write-slot"), getComputedStyle(runView).color);
    }
  }

  // ---------- Bedienung ----------

  function firstInput() {
    const exp = Object.keys(expected());
    if (run.stage === 3) return key(0, 1);
    if (run.stage === 4) return [...errorDiff()][0];
    // Ergebnis von rechts, Division links (Aufgabenzeile) zuerst
    const sorted = exp.map((p) => p.split(",").map(Number)).sort((a, b) => a[0] - b[0] || b[1] - a[1]);
    const div = run.ex.verfahren === "division";
    const firstRow = sorted.length ? sorted[0][0] : 0;
    const inRow = sorted.filter((x) => x[0] === firstRow).sort((a, b) => (div && firstRow === 0 ? a[1] - b[1] : b[1] - a[1]));
    return inRow.length ? key(...inRow[0]) : null;
  }

  // Nächstes Kästchen in Rechenrichtung (Zeile weiß ihre Richtung), sonst stehen bleiben
  function advance() {
    if (!run.active) return;
    const [r, c] = run.active.split(",").map(Number);
    const step = rowInfo(r).richtung === "ltr" ? 1 : -1;
    for (let k = c + step; k >= 0 && k < grid().spalten; k += step) {
      const p = key(r, k);
      if (isInput(p)) { run.active = p; return; }
    }
  }

  function typeKey(k) {
    if (!typing()) return;
    if (!run.active) run.active = firstInput();
    if (!run.active) return;
    if (k === "back") {
      run.entries[run.active] = "";
    } else {
      run.entries[run.active] = k;
      advance();
    }
    run.wrong.delete(run.active);
    render();
  }

  function tapCell(p) {
    if (run.stage === 4 && !run.found) {
      if (errorDiff().has(p)) {
        run.found = true;
        const wrong = byPos(run.ex.fehlerbild.zellen);
        errorDiff().forEach((q) => { run.entries[q] = wrong[q] ? wrong[q].z : ""; });
        run.active = p;
        logPracticeEvent(run.attempt, "hint", { fehler_gefunden: run.misses });
      } else {
        run.misses += 1;
      }
      return render();
    }
    run.active = p;
    render();
  }

  // Prüfen: erwartete Kästchen (Stufe 3 die beste Verschiebung), Überträge/optionale Nullen dürfen leer sein
  function evaluate(offset) {
    const exp = run.stage === 4 ? diffExpected() : expected(offset);
    const wrong = new Set();
    let missing = false, wrongEntered = false;
    Object.entries(exp).forEach(([p, c]) => {
      const v = run.entries[p] || "";
      if (!v) {
        if (!c.opt) { wrong.add(p); missing = true; }
      } else if (v !== c.z) {
        wrong.add(p);
        wrongEntered = true;
      }
    });
    Object.entries(run.entries).forEach(([p, v]) => {
      if (v && !(p in exp)) { wrong.add(p); wrongEntered = true; }
    });
    return { wrong, missing, wrongEntered };
  }

  function diffExpected() {
    const plain = byPos(plainCells());
    return Object.fromEntries([...errorDiff()].map((p) => [p, plain[p] || { z: "", opt: true }]));
  }

  function check() {
    let best = null;
    const offsets = run.stage === 3 ? OFFSETS : [0];
    const ops = opPositions();
    offsets.forEach((d) => {
      const exp = Object.keys(expected(d));
      if (exp.some((p) => ops.has(p) || Number(p.split(",")[1]) < 0 || Number(p.split(",")[1]) >= grid().spalten)) return;
      const res = evaluate(d);
      if (!best || res.wrong.size < best.wrong.size) best = { ...res, offset: d };
    });
    run.offset = best.offset;
    run.wrong = best.wrong;
    run.missing = best.missing;
    run.wrongEntered = best.wrongEntered;
    run.checked = true;
    if (run.wrong.size) {
      run.fails += 1;
      const first = [...run.wrong].map((p) => p.split(",").map(Number)).sort((a, b) => a[0] - b[0] || b[1] - a[1])[0];
      const cell = byPos(plainCells())[key(first[0], first[1] - run.offset)];
      const st = cell && stepOf(cell.id);
      run.tipText = st ? st.satz : null;
    } else {
      run.done = true;
      run.active = null;
    }
    logPracticeEvent(run.attempt, "check", { status: run.done ? "richtig" : "noch_nicht", falsch: run.wrong.size });
    render();
  }

  function showSolution() {
    const exp = run.stage === 4 ? diffExpected() : expected(run.offset || 0);
    Object.entries(exp).forEach(([p, c]) => { run.entries[p] = c.z; });
    run.wrong = new Set();
    logPracticeEvent(run.attempt, "solution", {});
    render();
  }

  function nextStep() {
    if (run.stage === -1 && !run.answered && steps()[run.step].frage) return;
    if (run.step + 1 >= steps().length) {
      run.done = true;
      if (!run.logged) {
        run.logged = true;
        logPracticeEvent(run.attempt, "check", { status: "richtig", schritte: steps().length, falsch: run.misses });
      }
    } else {
      run.step += 1;
      run.answered = run.stage === -2 || !steps()[run.step].frage;
      run.wrongOpts = new Set();
    }
    render();
  }

  function choose(option) {
    const st = steps()[run.step];
    if (option === st.antwort) {
      run.answered = true;
    } else {
      run.wrongOpts.add(option);
      run.misses += 1;
      if (run.wrongOpts.size >= 2) run.answered = true;  // nach zwei Fehlversuchen zeigt Luna den Schritt
    }
    render();
  }

  runView.addEventListener("click", (e) => {
    if (!run) return;
    const t = e.target.closest("button");
    if (!t || t.disabled) return;
    if (t.dataset.cell !== undefined) return tapCell(t.dataset.cell);
    if (t.dataset.key !== undefined) return typeKey(t.dataset.key);
    if (t.dataset.option !== undefined) return choose(t.dataset.option);
    if (t.dataset.pad === "clear") return pad && pad.clear();
    if (t.dataset.action === "sr-next") return nextStep();
    if (t.dataset.action === "sr-check") return check();
    if (t.dataset.action === "sr-tip") {
      run.tip = true;
      logPracticeEvent(run.attempt, "hint", {});
      return render();
    }
    if (t.dataset.action === "sr-show") return showSolution();
  });

  // Mit Tastatur (Mac): Ziffern, Komma, Löschen
  document.addEventListener("keydown", (e) => {
    const tab = document.getElementById("tab-practice");
    if (!run || runView.style.display === "none" || (tab && !tab.classList.contains("active")) || e.metaKey || e.ctrlKey) return;
    if (e.target.closest && e.target.closest("input, textarea, [contenteditable]")) return;
    if (/^[0-9]$/.test(e.key) || e.key === ",") typeKey(e.key);
    else if (e.key === "Backspace") typeKey("back");
  });

  // ---------- Anmeldung beim Kern ----------

  registerPracticeType("schriftlich", {
    stages: {
      "-2": { title: "Zuschauen: die Rechnung Schritt für Schritt", name: "Zuschauen", icon: "Anzeigen" },
      "-1": { title: "Antippen: bei jedem Schritt die richtige Antwort", name: "Antippen", icon: "Hand" },
      1: { title: "Ergebnis eintragen" },
      2: { title: "Zwischenschritte und Ergebnis eintragen" },
      3: { title: "Aufgabe selbst aufschreiben und rechnen" },
      4: { title: "Fehler finden und verbessern", name: "Fehler finden", icon: "Suche" },
    },
    open(ex, stage, coreApi) {
      core = coreApi;
      run = { ex, stage, attempt: startPracticeAttempt(ex.id, stage), step: 0, answered: stage === -2,
              wrongOpts: new Set(), entries: {}, active: null, checked: false, wrong: new Set(), fails: 0,
              tip: false, tipText: null, done: false, logged: false, found: false, misses: 0, offset: 0,
              missing: false, wrongEntered: false };
      if (stage === -1 && !ex.schritte[0].frage) run.answered = true;
      if (stage >= 1 && stage <= 3) run.active = firstInput();
      render();
      return stage;
    },
    close() {
      run = null;
      if (pad) pad.clear();
    },
  });
})();
