// ==========================================================================
// Üben, Übungstyp „Schriftlich rechnen“ (backend: services/exercise_types/schriftlich.py)
// --------------------------------------------------------------------------
// Addition, Subtraktion, Multiplikation, Division im Kästchengitter. Gitter, Schritte
// (Regelsätze aus dem Merkblatt der Eltern) und Fehlerbild rechnet der Server; hier
// nur Anzeige, Eingabe und Prüfung.
// Schreibregeln der Eltern (25.10.): jede Ziffer in einem Kästchen; das Komma sitzt auf
// der senkrechten Linie rechts neben seinem Kästchen, unten – es verschiebt keine Ziffer;
// der Strich liegt auf der Linie direkt unter der Zahlenzeile; ein Übertrag steht klein
// unten rechts im Kästchen seiner Zahl. Feste Kästchengröße, das Blatt scrollt, zoomt nicht.
// Stufen: -2 Zuschauen (Schritt für Schritt mit Regelsatz, „Weiter“), -1 Antippen
// (Frage mit drei Antworten je Schritt), 1 Ergebnis eintragen, 2 Zwischenzeilen,
// Überträge und Ergebnis eintragen, 3 Aufgabe selbst stellengerecht aufschreiben
// (darf als Ganzes verschoben stehen), 4 Fehler finden (antippen, dann verbessern).
// Eingabe: Kästchen antippen, Zahlentasten; der Cursor läuft in Rechenrichtung weiter.
// Dasselbe Kästchen gleich noch einmal antippen = Übertrag (klein unten rechts); die Komma-Taste
// setzt oder entfernt das Komma rechts neben dem gewählten Kästchen. Überträge und nicht
// zwingende Nullen dürfen leer bleiben. Keine Nebenrechnung: die schriftliche Rechnung ist
// hier selbst das, was geübt wird (Nutzer, 25.10.).
// ==========================================================================

(function () {
  const runView = document.getElementById("practice-run-view");
  if (!runView) return;

  let core = null;
  // { ex, stage, attempt, step, answered, wrongOpts, entries: {platz: z}, active: {r, c, platz}, checked,
  //   wrong: Set(platz), fails, tip, tipText, done, logged, found, misses, offset, missing, wrongEntered, diff }
  let run = null;

  const esc = (s) => escapeHtml(String(s));
  const say = (t) => `<div class="px-say">${icon("Luna", "px-luna-icon")}<p>${esc(t)}</p></div>`;
  const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ",", "0", "⌫"];
  const OFFSETS = [0, -1, 1, -2, 2, -3, 3];  // Stufe 3: so weit darf die ganze Rechnung verschoben stehen
  const SUFFIX = { ziffer: "", komma: ",k", uebertrag: ",u" };

  // Platz eines Zeichens: "r,c" (Ziffer), "r,c,k" (Komma rechts daneben), "r,c,u" (Übertrag im Kästchen)
  const slot = (r, c, platz = "ziffer") => `${r},${c}${SUFFIX[platz]}`;
  const slotOf = (cell, offset = 0) => slot(cell.r, cell.c + offset, cell.platz);
  const box = (s) => s.split(",").slice(0, 2).join(",");
  const grid = () => run.ex.gitter;
  const rowInfo = (r) => grid().zeilen_info[String(r)] || {};
  const plainCells = () => grid().zellen;
  const bySlot = (cells) => Object.fromEntries(cells.map((c) => [slotOf(c), c]));
  const steps = () => run.ex.schritte;
  const stepOf = (cellId) => steps().find((st) => st.zellen.includes(cellId));

  // ---------- Was ist sichtbar, was wird eingetragen? ----------

  const INPUT_KINDS = { 1: ["ergebnis"], 2: ["null", "uebertrag", "zwischen", "ergebnis"],
                        3: ["aufgabe", "null", "uebertrag", "zwischen", "ergebnis"] };

  // Erwartete Eingaben: Platz → Zelle (Stufe 3 um offset Spalten verschoben)
  function expected(offset = 0) {
    const kinds = INPUT_KINDS[run.stage] || [];
    return Object.fromEntries(plainCells().filter((c) => kinds.includes(c.art)).map((c) => [slotOf(c, offset), c]));
  }

  const opBoxes = () => new Set(plainCells().filter((c) => c.art === "op").map((c) => slot(c.r, c.c)));

  // Fehlerbild (Stufe 4): Plätze, an denen es von der Lösung abweicht
  function errorDiff() {
    if (!run.diff) {
      const plain = bySlot(plainCells()), wrong = bySlot(run.ex.fehlerbild.zellen);
      run.diff = new Set([...new Set([...Object.keys(plain), ...Object.keys(wrong)])]
        .filter((s) => (plain[s] ? plain[s].z : "") !== (wrong[s] ? wrong[s].z : "")));
    }
    return run.diff;
  }
  const diffBoxes = () => new Set([...errorDiff()].map(box));

  // Darf Thea in dieses Kästchen schreiben?
  function boxIsInput(b) {
    if (run.done) return false;
    if (run.stage === 1 || run.stage === 2) return Object.keys(expected()).some((s) => box(s) === b);
    if (run.stage === 3) return !opBoxes().has(b);
    if (run.stage === 4) return run.found ? diffBoxes().has(b) : true;
    return false;
  }

  // Zuschauen/Antippen: aufgedeckte Schritte
  function stepsShown() {
    const upto = run.stage === -1 && !run.answered ? run.step : run.step + 1;
    return steps().slice(0, upto);
  }

  // Inhalt eines Platzes, wie er gerade zu sehen ist
  function slotText(s, plain) {
    const c = plain[s];
    if (run.stage < 0) {
      if (!c) return "";
      return c.art === "aufgabe" || c.art === "op" || stepsShown().some((st) => st.zellen.includes(c.id)) ? c.z : "";
    }
    if (run.stage === 4) {
      if (run.done) return c ? c.z : "";
      if (run.found && diffBoxes().has(box(s))) return run.entries[s] || "";
      const w = bySlot(run.ex.fehlerbild.zellen)[s];
      return w ? w.z : "";
    }
    if (c && c.art === "op") return c.z;
    if (run.stage === 3) return run.entries[s] || "";
    if (boxIsInput(box(s))) return run.entries[s] || (c && !(s in expected()) ? c.z : "");
    if (run.done && run.entries[s]) return run.entries[s];
    return c && !(s in expected()) ? c.z : (run.entries[s] || "");
  }

  // ---------- Blatt ----------

  function gridHtml() {
    const g = grid(), plain = bySlot(plainCells());
    // Strich auf der Linie unter der Zeile, so breit wie die Zahlen darüber und darunter; Zuschauen: erst, wenn
    // die Zeile oder eine darunter zu sehen ist; Stufe 3 ohne Striche (sie verrieten den Aufbau)
    const extent = {};
    for (let r = 0; r < g.zeilen; r++) {
      if (!rowInfo(r).strich || run.stage === 3) continue;
      if (run.stage < 0 && !plainCells().some((x) => x.r > r && slotText(slotOf(x), plain))) continue;
      const cs = plainCells().filter((x) => (x.r === r || x.r === r + 1) && x.platz === "ziffer").map((x) => x.c);
      if (cs.length) extent[r] = [Math.min(...cs), Math.max(...cs)];
    }
    const current = new Set(run.stage < 0 && (run.stage === -2 || run.answered) ? (steps()[run.step] || { zellen: [] }).zellen : []);
    const isNew = (s) => plain[s] && current.has(plain[s].id);
    const hintCarries = run.stage === 2 && !run.done;
    let h = "";
    for (let r = 0; r < g.zeilen; r++) {
      for (let c = 0; c < g.spalten; c++) {
        const b = slot(r, c), uSlot = slot(r, c, "uebertrag"), kSlot = slot(r, c, "komma");
        const digit = slotText(b, plain), comma = slotText(kSlot, plain), carry = slotText(uSlot, plain);
        const input = boxIsInput(b);
        const active = input && run.active && run.active.r === r && run.active.c === c ? run.active.platz : null;
        const carryHint = hintCarries && input && uSlot in expected();
        const cls = ["sr-cell"];
        if (extent[r] && c >= extent[r][0] && c <= extent[r][1]) cls.push("strich");
        if (plain[b] && plain[b].art === "op") cls.push("op");
        if (isNew(b)) cls.push("neu");
        let inner = esc(digit);
        if (carry || active === "uebertrag" || carryHint) {
          const k = ["sr-carry"];
          if (active === "uebertrag") k.push("active");
          if (carryHint && !carry) k.push("hint");
          if (run.wrong.has(uSlot)) k.push("wrong");
          if (isNew(uSlot)) k.push("neu");
          inner += `<span class="${k.join(" ")}">${esc(carry)}</span>`;
        }
        if (comma) {
          inner += `<span class="sr-comma${run.wrong.has(kSlot) ? " wrong" : ""}${isNew(kSlot) ? " neu" : ""}">,</span>`;
        }
        const style = `grid-row:${r + 1};grid-column:${c + 1}`;
        if (input) {
          cls.push("in");
          if (active === "ziffer") cls.push("active");
          if (run.wrong.has(b)) cls.push("wrong");
          h += `<button type="button" class="${cls.join(" ")}" style="${style}" data-box="${b}" aria-label="Kästchen">${inner}</button>`;
        } else if (inner || cls.length > 1) {
          if (run.done && wasTyped(b)) cls.push("ok");
          h += `<span class="${cls.join(" ")}" style="${style}">${inner}</span>`;
        }
      }
    }
    return `<div class="sr-grid" style="grid-template-columns:repeat(${g.spalten}, var(--cell));grid-template-rows:repeat(${g.zeilen}, var(--cell))">${h}</div>`;
  }

  // Geschafft: was Thea eingetragen hat, grün
  function wasTyped(b) {
    if (run.stage === 4) return diffBoxes().has(b);
    return run.stage >= 1 && Object.keys(expected(run.offset)).some((s) => box(s) === b);
  }

  // ---------- Luna, Knöpfe ----------

  function lunaHtml() {
    const st = steps()[run.step];
    if (run.stage === -2) return run.done ? say("So geht die Rechnung. Jetzt bist du dran!") : say(st.satz);
    if (run.stage === -1) {
      if (run.done) return say("Geschafft! Du hast jeden Schritt gewusst.");
      if (run.answered || !st.frage) return say(st.satz);
      return say(st.frage) + `<div class="sr-options">${st.optionen.map((o) => `<button type="button" class="px-guess-btn sr-option${run.wrongOpts.has(o) ? " wrong" : ""}"
        data-option="${esc(o)}"${run.wrongOpts.has(o) ? " disabled" : ""}>${esc(o)}</button>`).join("")}</div>`;
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
    const next = `<button type="button" class="px-check" data-action="sr-next" title="Weiter" aria-label="Weiter">${icon("Pfeil rechts")}</button>`;
    if (run.stage === -2) return next;
    if (run.stage === -1) return run.answered || !steps()[run.step].frage ? next : "";
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

  const typing = () => !run.done && ((run.stage >= 1 && run.stage <= 3) || (run.stage === 4 && run.found));

  function keysHtml() {
    return `<div class="gg-pad sr-keys" role="group" aria-label="Zahlen">${KEYS.map((k) => k === "⌫"
      ? `<button type="button" class="gg-key" data-key="back" title="Löschen" aria-label="Löschen">${icon("Rückgängig")}</button>`
      : `<button type="button" class="gg-key" data-key="${k}">${k}</button>`).join("")}</div>`;
  }

  // Feste Seite: links Aufgabe und Blatt (scrollt in sich, zoomt nicht), rechts Luna, Tasten, Knöpfe
  function render() {
    core.setZen(true);
    const ex = run.ex;
    const pre = ex.vorspann && run.stage <= 2 ? `<p class="sr-pre">${esc(ex.vorspann)}</p>` : "";
    const old = runView.querySelector(".sr-wrap");
    const scroll = old ? [old.scrollLeft, old.scrollTop] : [0, 0];
    runView.innerHTML = `
      ${core.topbarHtml(ex, run.stage)}
      <div class="sr">
        <div class="sr-left">
          <p class="px-task sr-task">${esc(ex.aufgabentext)}</p>
          ${pre}
          <div class="sr-wrap">${gridHtml()}</div>
        </div>
        <div class="sr-right">
          <div class="px-luna" aria-live="polite">${lunaHtml()}</div>
          ${typing() ? keysHtml() : ""}
          <div class="px-actions sr-actions">${actionsHtml()}</div>
        </div>
      </div>`;
    const wrap = runView.querySelector(".sr-wrap");
    [wrap.scrollLeft, wrap.scrollTop] = scroll;  // beim Tippen nicht nach oben springen
  }

  // ---------- Bedienung ----------

  function firstInput() {
    if (run.stage === 3) return { r: 0, c: 1, platz: "ziffer" };
    // das erste Kästchen, das in der Reihenfolge der Rechenschritte zu schreiben ist
    const byId = Object.fromEntries(Object.values(expected()).filter((c) => c.platz === "ziffer").map((c) => [c.id, c]));
    for (const st of steps()) {
      const cell = st.zellen.map((id) => byId[id]).find(Boolean);
      if (cell) return { r: cell.r, c: cell.c, platz: "ziffer" };
    }
    return null;
  }

  // Nächstes Kästchen in Rechenrichtung (Zeile weiß ihre Richtung), sonst stehen bleiben
  function advance() {
    const { r, c } = run.active;
    const dir = rowInfo(r).richtung === "ltr" ? 1 : -1;
    const exp = expected();
    for (let k = c + dir; k >= 0 && k < grid().spalten; k += dir) {
      const b = slot(r, k);
      if (boxIsInput(b) && (run.stage >= 3 || b in exp)) {
        run.active = { r, c: k, platz: "ziffer" };
        return;
      }
    }
  }

  function typeKey(k) {
    if (!typing()) return;
    if (!run.active) run.active = firstInput();
    if (!run.active) return;
    const { r, c, platz } = run.active;
    run.active.tapped = false;  // nach einer Taste heißt erneutes Antippen wieder: Ziffer
    if (k === ",") {
      const s = slot(r, c, "komma");
      run.entries[s] = run.entries[s] ? "" : ",";
      run.wrong.delete(s);
      return render();
    }
    const s = slot(r, c, platz);
    if (k === "back") {
      run.entries[s] = "";
    } else {
      run.entries[s] = k;
      if (platz === "ziffer") advance();
    }
    run.wrong.delete(s);
    render();
  }

  function tapBox(b) {
    const [r, c] = b.split(",").map(Number);
    if (run.stage === 4 && !run.found) {
      if (diffBoxes().has(b)) {
        run.found = true;
        const wrong = bySlot(run.ex.fehlerbild.zellen);
        errorDiff().forEach((s) => { run.entries[s] = wrong[s] ? wrong[s].z : ""; });
        diffBoxes().forEach((d) => ["ziffer", "komma", "uebertrag"].forEach((p) => {
          const s = d + SUFFIX[p];
          if (!(s in run.entries) && wrong[s]) run.entries[s] = wrong[s].z;
        }));
        run.active = { r, c, platz: "ziffer" };
        logPracticeEvent(run.attempt, "hint", { fehler_gefunden: run.misses });
      } else {
        run.misses += 1;
      }
      return render();
    }
    // dasselbe Kästchen noch einmal antippen: Übertrag (klein unten rechts) – und wieder zurück. Nur nach eigenem
    // Antippen; steht der Cursor von selbst dort (nach der letzten Ziffer), heißt Antippen: Ziffer schreiben
    const same = run.active && run.active.r === r && run.active.c === c && run.active.tapped;
    run.active = { r, c, platz: same && run.active.platz === "ziffer" ? "uebertrag" : "ziffer", tapped: true };
    render();
  }

  // Prüfen: erwartete Plätze (Stufe 3 die beste Verschiebung), Überträge/optionale Nullen dürfen leer sein
  function evaluate(exp) {
    const wrong = new Set();
    let missing = false, wrongEntered = false;
    Object.entries(exp).forEach(([s, c]) => {
      const v = run.entries[s] || "";
      if (!v) {
        if (!c.opt && c.z) { wrong.add(s); missing = true; }
      } else if (v !== c.z) {
        wrong.add(s);
        wrongEntered = true;
      }
    });
    Object.entries(run.entries).forEach(([s, v]) => {
      if (v && !(s in exp)) { wrong.add(s); wrongEntered = true; }
    });
    return { wrong, missing, wrongEntered };
  }

  // Stufe 4: in den Kästchen mit dem Fehler muss am Ende die Lösung stehen (wo die Lösung nichts hat: leer)
  function diffExpected() {
    const plain = bySlot(plainCells()), out = {};
    diffBoxes().forEach((b) => ["ziffer", "komma", "uebertrag"].forEach((p) => {
      const s = b + SUFFIX[p];
      out[s] = plain[s] || { z: "", opt: true };
    }));
    return out;
  }

  function check() {
    let best = null;
    const ops = opBoxes();
    (run.stage === 3 ? OFFSETS : [0]).forEach((d) => {
      const exp = run.stage === 4 ? diffExpected() : expected(d);
      const boxes = Object.keys(exp).map(box);
      if (boxes.some((b) => ops.has(b) || Number(b.split(",")[1]) < 0 || Number(b.split(",")[1]) >= grid().spalten)) return;
      const res = evaluate(exp);
      if (!best || res.wrong.size < best.wrong.size) best = { ...res, offset: d };
    });
    Object.assign(run, { offset: best.offset, wrong: best.wrong, missing: best.missing, wrongEntered: best.wrongEntered, checked: true });
    if (run.wrong.size) {
      run.fails += 1;
      const first = [...run.wrong].map((s) => s.split(",")).sort((a, b) => a[0] - b[0] || b[1] - a[1])[0];
      const cell = bySlot(plainCells())[[first[0], Number(first[1]) - run.offset, ...first.slice(2)].join(",")];
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
    Object.keys(run.entries).forEach((s) => { if (!(s in exp)) run.entries[s] = ""; });
    Object.entries(exp).forEach(([s, c]) => { run.entries[s] = c.z; });
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
    if (t.dataset.box !== undefined) return tapBox(t.dataset.box);
    if (t.dataset.key !== undefined) return typeKey(t.dataset.key);
    if (t.dataset.option !== undefined) return choose(t.dataset.option);
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
              missing: false, wrongEntered: false, diff: null };
      if (stage === -1 && !ex.schritte[0].frage) run.answered = true;
      if (stage >= 1 && stage <= 3) run.active = firstInput();
      render();
      return stage;
    },
    close() {
      run = null;
    },
  });
})();
