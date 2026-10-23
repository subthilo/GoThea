// ==========================================================================
// Üben, Übungstyp „Zuordnen“ (alle Fächer; backend: services/exercise_types/zuordnen.py)
// --------------------------------------------------------------------------
// Links das Schaubild (Buchabbildung, nachgezeichnet mit Ziffernkreisen statt
// Beschriftungen), rechts die Antwortliste „1 ___, 2 ___ …“ wie im Arbeitsheft.
// Stufe -1 „Anschauen“: Ziffer oder Zeile antippen, der Begriff erscheint.
// Stufe 1: Begriffe aus der Wortbank in die Zeilen; Stufe 2: dazu Ablenker.
// Drei Wege: Begriff ziehen; Begriff, dann Zeile antippen; Ziffer, dann Begriff.
// Jederzeit „Im Buch“: der Buchausschnitt selbst (zählt als Nachschlagen).
// Geprüft wird hier gegen die Begriffe aus den Übungsdaten.
// ==========================================================================

(function () {
  const runView = document.getElementById("practice-run-view");
  if (!runView) return;

  let core = null;
  let run = null;  // { ex, stage, attempt, placed: {nr: Begriff}, seen: Set, active, selected, checked, fails, book, shown }

  const esc = (s) => escapeHtml(String(s));
  const norm = (s) => String(s || "").trim().replace(/\s+/g, " ").toLowerCase();
  const say = (t) => `<div class="px-say">${icon("Luna", "px-luna-icon")}<p>${esc(t)}</p></div>`;

  const fields = () => run.ex.felder;
  const isRight = (f) => [f.begriff, ...(f.auch || [])].some((t) => norm(t) === norm(run.placed[f.nr]));
  const allPlaced = () => fields().every((f) => run.placed[f.nr]);
  const allRight = () => fields().every(isRight);
  const done = () => (run.stage < 0 ? run.seen.size === fields().length : run.checked && allRight());

  // ---------- Darstellung ----------

  function figureHtml() {
    const ex = run.ex;
    if (run.book) {
      return `<div class="zo-figure zo-book"><img src="${esc(ex.original_url)}" alt="Abbildung im Buch" draggable="false"></div>`;
    }
    const spots = fields().map((f) => {
      let state = "";
      if (run.stage >= 0 && run.checked && run.placed[f.nr]) state = isRight(f) ? " ok" : " wrong";
      const active = run.active === f.nr ? " active" : "";
      return `<button type="button" class="zo-spot${active}${state}" data-spot="${f.nr}" style="left:${f.x * 100}%;top:${f.y * 100}%"
        aria-label="Ziffer ${f.nr}"></button>`;
    }).join("");
    return `<div class="zo-figure" style="--zo-ratio:${ex.bild.breite / ex.bild.hoehe}"><img src="${esc(ex.bild_url)}" alt="Schaubild mit Ziffern" draggable="false">${spots}</div>`;
  }

  function rowsHtml() {
    return fields().map((f) => {
      const active = run.active === f.nr ? " active" : "";
      if (run.stage < 0) {
        const seen = run.seen.has(f.nr);
        return `<li class="zo-row${active}"><span class="zo-nr">${f.nr}</span>
          <button type="button" class="zo-slot${seen ? " filled" : ""}" data-row="${f.nr}">${seen ? esc(f.begriff) : ""}</button></li>`;
      }
      const value = run.placed[f.nr];
      const state = run.checked && value ? (isRight(f) ? " ok" : " wrong") : "";
      return `<li class="zo-row${active}"><span class="zo-nr">${f.nr}</span>
        <button type="button" class="zo-slot${value ? " filled" : ""}${state}" data-row="${f.nr}"
          aria-label="${value ? "Feld " + f.nr + ": " + esc(value) : "Feld " + f.nr + " leer"}">${value ? esc(value) : ""}</button></li>`;
    }).join("");
  }

  function bankHtml() {
    if (run.stage < 0) return "";
    const bank = run.stage >= 2 ? run.ex.wortbank_ablenker : run.ex.wortbank;
    // Gesetzte Begriffe bleiben wählbar (blasser): erneut gesetzt, wandern sie aus ihrer alten Zeile mit
    const used = new Set(Object.values(run.placed).map(norm));
    const locked = done();
    return `<div class="px-palette zo-bank">${bank.map((t) => {
      const isUsed = used.has(norm(t));
      return `<button type="button" class="px-token zo-token${run.selected === t ? " selected" : ""}${isUsed ? " used" : ""}"
        data-token="${esc(t)}"${locked ? " disabled" : ""}>${esc(t)}</button>`;
    }).join("")}</div>`;
  }

  function lunaHtml() {
    const ex = run.ex;
    if (run.stage < 0) {
      return done() ? say("Jetzt kennst du alle Begriffe. Probier es selbst!") : "";
    }
    if (!run.checked) return "";
    if (allRight()) return say(run.fails ? "Geschafft! Alle Begriffe stimmen." : "Richtig! Alle Begriffe stimmen.");
    const wrong = fields().filter((f) => !isRight(f)).length;
    let h = say(wrong === 1 ? "Fast! Ein Begriff stimmt noch nicht." : `${wrong} Begriffe stimmen noch nicht.`);
    if (run.fails >= 1 && ex.hilfen && ex.hilfen.denkanstoss) h += say(ex.hilfen.denkanstoss);
    if (run.fails >= 2 && ex.nachschlagen) h += say(`Schau im Buch nach: S. ${ex.nachschlagen.seite}, ${ex.nachschlagen.stelle}.`);
    return h;
  }

  function actionsHtml() {
    const book = `<button type="button" class="px-check secondary${run.book ? " active" : ""}" data-action="zo-book"
      title="${run.book ? "Zurück zum Schaubild" : "Im Buch"}" aria-label="${run.book ? "Zurück zum Schaubild" : "Im Buch"}">${icon(run.book ? "Bild" : "Lesen")}</button>`;
    if (done()) return book + nextButtons();
    if (run.stage < 0) return book;
    const show = run.fails >= 2
      ? `<button type="button" class="px-check secondary" data-action="zo-show" title="Lösung zeigen" aria-label="Lösung zeigen">${icon("Anzeigen")}</button>` : "";
    return `${book}${show}<button type="button" class="px-check" data-action="zo-check" title="Prüfen" aria-label="Prüfen"${allPlaced() ? "" : " disabled"}>${icon("Haken")}</button>`;
  }

  function nextButtons() {
    const ex = run.ex;
    const next = ex.stufen.find((s) => s > run.stage && !ex.tafel_stufen.includes(s));
    const twinId = ex.ableitung === "A" ? ex.zwillinge[0] : ex.zwilling_von;
    let h = next !== undefined
      ? `<button type="button" class="px-check" data-stage="${next}" title="Weiter mit Stufe ${next}" aria-label="Weiter mit Stufe ${next}">${icon("Pfeil hoch")}<span>${next}</span></button>` : "";
    if (twinId) h += `<button type="button" class="px-check secondary" data-action="open" data-id="${esc(twinId)}" data-at="${run.stage}" title="Ähnliche Aufgabe">${icon("Wiederholen")}</button>`;
    return h + `<button type="button" class="px-check secondary" data-action="back" title="Zur Liste">${icon("Erledigt")}</button>`;
  }

  function render() {
    core.setZen(false);
    runView.innerHTML = `
      ${core.topbarHtml(run.ex, run.stage)}
      <p class="px-task zo-task">${esc(run.ex.aufgabentext)}</p>
      <div class="zo">
        ${figureHtml()}
        <aside class="zo-side">
          <ol class="zo-rows">${rowsHtml()}</ol>
        </aside>
      </div>
      ${bankHtml()}
      <div class="px-luna" aria-live="polite">${lunaHtml()}</div>
      <div class="px-actions zo-actions">${actionsHtml()}</div>`;
  }

  // ---------- Bedienung ----------

  function place(nr, term) {
    // Ein Begriff steht nur einmal: von seiner alten Zeile wegnehmen
    Object.keys(run.placed).forEach((k) => { if (run.placed[k] === term) delete run.placed[k]; });
    run.placed[nr] = term;
    run.selected = null;
    run.active = null;
    run.checked = false;
    render();
  }

  function choose(nr) {
    if (run.stage < 0) {
      run.seen.add(nr);
      run.active = nr;
      if (done() && !run.logged) {
        run.logged = true;
        logPracticeEvent(run.attempt, "check", { status: "richtig", angesehen: run.seen.size });
      }
      return render();
    }
    if (done()) return;
    if (run.selected) return place(nr, run.selected);
    if (run.placed[nr] && run.active === nr) {  // gefüllte, schon markierte Zeile noch mal antippen = leeren
      delete run.placed[nr];
      run.checked = false;
    }
    run.active = run.active === nr ? null : nr;
    render();
  }

  function check() {
    run.checked = true;
    const wrong = fields().filter((f) => !isRight(f)).map((f) => f.nr);
    if (wrong.length) run.fails += 1;
    logPracticeEvent(run.attempt, "check", { status: wrong.length ? "noch_nicht" : "richtig", falsch: wrong });
    render();
  }

  function showSolution() {
    fields().forEach((f) => { run.placed[f.nr] = f.begriff; });
    run.checked = true;
    logPracticeEvent(run.attempt, "solution", {});
    render();
  }

  runView.addEventListener("click", (e) => {
    if (!run) return;
    const t = e.target.closest("button");
    if (!t || t.disabled) return;
    if (t.dataset.spot) return choose(Number(t.dataset.spot));
    if (t.dataset.row) return choose(Number(t.dataset.row));
    if (t.dataset.action === "zo-check") return check();
    if (t.dataset.action === "zo-show") return showSolution();
    if (t.dataset.action === "zo-book") {
      run.book = !run.book;
      if (run.book) logPracticeEvent(run.attempt, "hint", { nachschlagen: true });
      return render();
    }
    if (t.dataset.token !== undefined) {
      if (dragMoved) return;
      if (run.active) return place(run.active, t.dataset.token);
      run.selected = run.selected === t.dataset.token ? null : t.dataset.token;
      return render();
    }
  });

  // Ziehen mit Finger oder Pencil: Kopie folgt dem Zeiger, Ablegen auf einer Zeile oder einer Ziffer
  let drag = null;
  let dragMoved = false;
  runView.addEventListener("pointerdown", (e) => {
    const tok = e.target.closest(".zo-token");
    if (!run || !tok || tok.disabled) return;
    dragMoved = false;
    drag = { token: tok.dataset.token, x: e.clientX, y: e.clientY, ghost: null };
  });
  window.addEventListener("pointermove", (e) => {
    if (!drag) return;
    if (!drag.ghost && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 8) {
      dragMoved = true;
      drag.ghost = document.createElement("div");
      drag.ghost.className = "px-token zo-token px-ghost";
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
    const target = document.elementFromPoint(e.clientX, e.clientY)?.closest("[data-row], [data-spot]");
    if (target && run && !done()) place(Number(target.dataset.row || target.dataset.spot), d.token);
    setTimeout(() => { dragMoved = false; }, 0);
  });
  window.addEventListener("pointercancel", () => {
    if (drag && drag.ghost) drag.ghost.remove();
    drag = null;
  });

  // ---------- Anmeldung beim Kern ----------

  registerPracticeType("zuordnen", {
    stages: {
      "-1": { title: "Anschauen: Ziffern antippen", name: "Anschauen", icon: "Anzeigen" },
      1: { title: "Begriffe zuordnen" },
      2: { title: "Begriffe zuordnen, mit falschen dazwischen" },
    },
    open(ex, stage, coreApi) {
      core = coreApi;
      run = { ex, stage, attempt: startPracticeAttempt(ex.id, stage), placed: {}, seen: new Set(), active: null,
              selected: null, checked: false, fails: 0, book: false, logged: false };
      render();
      return stage;
    },
    close() {
      run = null;
    },
  });
})();
