// ==========================================================================
// Üben, Übungstyp „Schubladen“ (alle Fächer; backend: services/exercise_types/schubladen.py)
// --------------------------------------------------------------------------
// Links die Kärtchen, rechts die beschrifteten Schubladen (Gruppen wie im Buch).
// Stufe -1 „Anschauen“: Schublade antippen, ihr Inhalt erscheint. Stufe 1: in
// jeder Schublade liegt schon ein Beispiel; Stufe 2: alles sortieren; Stufe 3
// „Fehler finden“: alles liegt schon, zwei Kärtchen falsch.
// Kärtchen antippen (gewählt), dann Schublade; Kärtchen in einer Schublade
// antippen holt es heraus (gewählt); ziehen geht auch.
// Jederzeit „Im Buch“: der Buchausschnitt (zählt als Nachschlagen).
// ==========================================================================

(function () {
  const runView = document.getElementById("practice-run-view");
  if (!runView) return;

  let core = null;
  let run = null;  // { ex, stage, attempt, place: {Begriff: Gruppe|null}, fixed: Set, selected, checked, fails, book, seen, logged }

  const esc = (s) => escapeHtml(String(s));
  const say = (t) => `<div class="px-say">${icon("Luna", "px-luna-icon")}<p>${esc(t)}</p></div>`;

  const groups = () => run.ex.gruppen;
  const groupOf = (term) => groups().findIndex((g) => g.begriffe.includes(term));
  const isRight = (term) => run.place[term] === groupOf(term);
  const terms = () => run.ex.karten;
  const allPlaced = () => terms().every((t) => run.place[t] !== null);
  const allRight = () => terms().every(isRight);
  const done = () => (run.stage < 0 ? run.seen.size === groups().length : run.checked && allRight());

  // ---------- Darstellung ----------

  function chipHtml(term) {
    const fixed = run.fixed.has(term);
    const state = fixed ? " fixed" : run.checked ? (isRight(term) ? " ok" : " wrong") : "";
    const selected = run.selected === term ? " selected" : "";
    return `<button type="button" class="px-token sb-chip${state}${selected}" data-term="${esc(term)}"${fixed || done() ? " disabled" : ""}>${esc(term)}</button>`;
  }

  function drawersHtml() {
    return `<div class="sb-drawers">${groups().map((g, gi) => {
      const content = run.stage < 0
        ? (run.seen.has(gi) ? g.begriffe.map((t) => `<span class="px-token sb-chip fixed">${esc(t)}</span>`).join("") : "")
        : terms().filter((t) => run.place[t] === gi).map(chipHtml).join("");
      const target = run.selected !== null && run.stage >= 0 ? " target" : "";
      return `<div class="sb-drawer${target}" data-drawer="${gi}" role="button" tabindex="0" aria-label="Schublade ${esc(g.name)}">
        <div class="sb-drawer-name">${esc(g.name)}</div>
        <div class="sb-drawer-content">${content}</div>
      </div>`;
    }).join("")}</div>`;
  }

  function poolHtml() {
    if (run.book) return `<div class="zo-book sb-book"><img src="${esc(run.ex.buch_url)}" alt="Im Buch" draggable="false"></div>`;
    if (run.stage < 0) return "";
    const free = terms().filter((t) => run.place[t] === null);
    return `<div class="sb-pool">${free.map(chipHtml).join("")}</div>`;
  }

  function lunaHtml() {
    const ex = run.ex;
    if (run.stage < 0) return done() ? say("Jetzt kennst du alle Schubladen. Probier es selbst!") : "";
    if (!run.checked) return run.stage === 3 && !run.moved ? say("Zwei Kärtchen liegen in der falschen Schublade. Findest du sie?") : "";
    if (allRight()) return say(run.fails ? "Geschafft! Alles liegt richtig." : "Richtig! Alles liegt richtig.");
    const wrong = terms().filter((t) => !isRight(t)).length;
    let h = say(wrong === 1 ? "Fast! Ein Kärtchen liegt noch falsch." : `${wrong} Kärtchen liegen noch falsch.`);
    if (run.fails >= 1 && ex.hilfen && ex.hilfen.denkanstoss) h += say(ex.hilfen.denkanstoss);
    if (run.fails >= 2 && ex.nachschlagen) h += say(`Schau im Buch nach: S. ${ex.nachschlagen.seite}, ${ex.nachschlagen.stelle}.`);
    return h;
  }

  function actionsHtml() {
    const book = run.ex.buch_url
      ? `<button type="button" class="px-check secondary${run.book ? " active" : ""}" data-action="sb-book"
          title="${run.book ? "Zurück" : "Im Buch"}" aria-label="${run.book ? "Zurück" : "Im Buch"}">${icon(run.book ? "Pfeil links" : "Lesen")}</button>` : "";
    if (done()) return book + nextButtons();
    if (run.stage < 0) return book;
    const show = run.fails >= 2
      ? `<button type="button" class="px-check secondary" data-action="sb-show" title="Lösung zeigen" aria-label="Lösung zeigen">${icon("Anzeigen")}</button>` : "";
    return `${book}${show}<button type="button" class="px-check" data-action="sb-check" title="Prüfen" aria-label="Prüfen"${allPlaced() ? "" : " disabled"}>${icon("Haken")}</button>`;
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

  // Feste Seite in Bildschirmhöhe, quer und hoch ohne Scrollen (Kärtchen und Schubladen scrollen notfalls in sich)
  function render() {
    core.setZen(true);
    runView.innerHTML = `
      ${core.topbarHtml(run.ex, run.stage)}
      <div class="sb${run.stage < 0 || run.stage === 3 ? " sb-full" : ""}">
        <p class="px-task sb-task">${esc(run.ex.aufgabentext)}</p>
        ${poolHtml()}
        ${drawersHtml()}
        <div class="zo-foot sb-foot">
          <div class="px-luna" aria-live="polite">${lunaHtml()}</div>
          <div class="px-actions zo-actions">${actionsHtml()}</div>
        </div>
      </div>`;
  }

  // ---------- Bedienung ----------

  function put(term, gi) {
    if (run.fixed.has(term)) return;
    run.place[term] = gi;
    run.selected = null;
    run.checked = false;
    run.moved = true;
    render();
  }

  function tapChip(term) {
    if (run.stage < 0 || done() || run.fixed.has(term)) return;
    if (run.place[term] !== null) {  // aus der Schublade holen und gleich wählen
      run.place[term] = null;
      run.checked = false;
      run.moved = true;
      run.selected = term;
    } else {
      run.selected = run.selected === term ? null : term;
    }
    render();
  }

  function tapDrawer(gi) {
    if (run.stage < 0) {
      run.seen.add(gi);
      if (done() && !run.logged) {
        run.logged = true;
        logPracticeEvent(run.attempt, "check", { status: "richtig", angesehen: run.seen.size });
      }
      return render();
    }
    if (run.selected !== null && !done()) put(run.selected, gi);
  }

  function check() {
    run.checked = true;
    const wrong = terms().filter((t) => !isRight(t));
    if (wrong.length) run.fails += 1;
    logPracticeEvent(run.attempt, "check", { status: wrong.length ? "noch_nicht" : "richtig", falsch: wrong });
    render();
  }

  function showSolution() {
    terms().forEach((t) => { run.place[t] = groupOf(t); });
    run.checked = true;
    logPracticeEvent(run.attempt, "solution", {});
    render();
  }

  runView.addEventListener("click", (e) => {
    if (!run) return;
    if (dragMoved) return;
    const chip = e.target.closest(".sb-chip[data-term]");
    if (chip && !chip.disabled) return tapChip(chip.dataset.term);
    const drawer = e.target.closest(".sb-drawer");
    if (drawer) return tapDrawer(Number(drawer.dataset.drawer));
    const t = e.target.closest("button");
    if (!t || t.disabled) return;
    if (t.dataset.action === "sb-check") return check();
    if (t.dataset.action === "sb-show") return showSolution();
    if (t.dataset.action === "sb-book") {
      run.book = !run.book;
      if (run.book) logPracticeEvent(run.attempt, "hint", { nachschlagen: true });
      return render();
    }
  });

  // Ziehen mit Finger oder Pencil: Kärtchen (auch aus einer Schublade) auf eine Schublade
  let drag = null;
  let dragMoved = false;
  runView.addEventListener("pointerdown", (e) => {
    if (!run || run.stage < 0 || done()) return;
    const chip = e.target.closest(".sb-chip[data-term]:not(.fixed)");
    if (!chip) return;
    dragMoved = false;
    drag = { term: chip.dataset.term, x: e.clientX, y: e.clientY, ghost: null };
  });
  window.addEventListener("pointermove", (e) => {
    if (!drag) return;
    if (!drag.ghost && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 8) {
      dragMoved = true;
      drag.ghost = document.createElement("div");
      drag.ghost.className = "px-token sb-chip px-ghost";
      drag.ghost.textContent = drag.term;
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
    const target = document.elementFromPoint(e.clientX, e.clientY)?.closest("[data-drawer]");
    if (target && run && !done()) put(d.term, Number(target.dataset.drawer));
    setTimeout(() => { dragMoved = false; }, 0);
  });
  window.addEventListener("pointercancel", () => {
    if (drag && drag.ghost) drag.ghost.remove();
    drag = null;
  });

  // ---------- Anmeldung beim Kern ----------

  registerPracticeType("schubladen", {
    stages: {
      "-1": { title: "Anschauen: Schubladen antippen", name: "Anschauen", icon: "Anzeigen" },
      1: { title: "Sortieren, ein Beispiel liegt schon drin" },
      2: { title: "Alles sortieren" },
      3: { title: "Fehler finden: zwei Kärtchen liegen falsch" },
    },
    open(ex, stage, coreApi) {
      core = coreApi;
      const fixed = new Set(stage === 1 ? ex.beispiele : []);
      const place = {};
      ex.karten.forEach((t) => {
        if (stage === 3) place[t] = ex.fehler_belegung[t];
        else place[t] = fixed.has(t) ? ex.gruppen.findIndex((g) => g.begriffe.includes(t)) : null;
      });
      run = { ex, stage, attempt: startPracticeAttempt(ex.id, stage), place, fixed, selected: null,
              checked: false, fails: 0, book: false, seen: new Set(), logged: false, moved: false };
      render();
      return stage;
    },
    close() {
      run = null;
    },
  });
})();
