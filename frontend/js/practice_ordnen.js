// ==========================================================================
// Üben, Übungstyp „Ordnen“ (alle Fächer; backend: services/exercise_types/ordnen.py)
// --------------------------------------------------------------------------
// Links die nummerierten Plätze, rechts die Kärtchen mit den Schritten (Wortlaut
// des Buchs). Stufe -1 „Anschauen“: die Plätze antippen, der Schritt erscheint.
// Stufe 1: erster (ab 5 Schritten auch letzter) Schritt steht schon; Stufe 2:
// alle; Stufe 3: dazu Ablenker, die liegen bleiben müssen. Kärtchen antippen →
// nächster freier bzw. gewählter Platz; besetzten Platz antippen → zurück;
// ziehen geht auch (Kärtchen auf Platz, Platz auf Platz = tauschen).
// Stufe 4: die Schritte stehen gemischt untereinander, Thea schreibt die Nummern
// mit dem Stift ins Schreibfeld (js/digit_pad.js) oder tippt sie; danach geht es
// zum nächsten leeren Kästchen.
// Kreislauf (kreis): der Anfang ist egal, nur die Folge zählt.
// Jederzeit „Im Buch“: der Buchausschnitt (zählt als Nachschlagen).
// ==========================================================================

(function () {
  const runView = document.getElementById("practice-run-view");
  if (!runView) return;

  let core = null;
  let run = null;  // { ex, stage, attempt, slots: [Schritt|null], fixed: Set, pool, active, checked, fails, book, seen, logged }

  const esc = (s) => escapeHtml(String(s));
  const say = (t) => `<div class="px-say">${icon("Luna", "px-luna-icon")}<p>${esc(t)}</p></div>`;

  const steps = () => run.ex.schritte;

  // Richtig an Platz i? Beim Kreislauf zählt die Folge ab dem Schritt auf Platz 1
  function expectedAt(i) {
    const n = steps().length;
    if (!run.ex.kreis) return steps()[i];
    const start = Math.max(0, steps().indexOf(run.slots[0]));
    return steps()[(start + i) % n];
  }
  const isRight = (i) => run.slots[i] === expectedAt(i);
  const allPlaced = () => run.slots.every(Boolean);
  const allRight = () => run.slots.every((_, i) => isRight(i));
  const done = () => (run.stage < 0 ? run.seen.size === steps().length : run.checked && allRight());

  // ---------- Darstellung ----------

  function slotsHtml() {
    return run.slots.map((value, i) => {
      if (run.stage < 0) {
        const seen = run.seen.has(i);
        return `<li class="or-row"><span class="zo-nr">${i + 1}</span>
          <button type="button" class="or-slot${seen ? " filled" : ""}" data-slot="${i}">${seen ? esc(steps()[i]) : ""}</button></li>`;
      }
      const fixed = run.fixed.has(i);
      const state = fixed ? " fixed" : run.checked && value ? (isRight(i) ? " ok" : " wrong") : "";
      const active = run.active === i ? " active" : "";
      return `<li class="or-row${active}"><span class="zo-nr">${i + 1}</span>
        <button type="button" class="or-slot${value ? " filled" : ""}${state}" data-slot="${i}"${fixed ? " disabled" : ""}
          aria-label="Platz ${i + 1}${value ? ": " + esc(value) : " leer"}">${value ? esc(value) : ""}</button></li>`;
    }).join("");
  }

  function poolHtml() {
    if (run.book) {
      return `<div class="zo-book or-book"><img src="${esc(run.ex.buch_url)}" alt="Im Buch" draggable="false"></div>`;
    }
    if (run.stage < 0) return "";
    const placed = new Set(run.slots.filter(Boolean));
    const free = run.pool.filter((c) => !placed.has(c));
    const locked = done();
    return `<div class="or-pool">${free.map((c) => `<button type="button" class="px-token or-card" data-card="${esc(c)}"${locked ? " disabled" : ""}>${esc(c)}</button>`).join("")}</div>`;
  }

  function lunaHtml() {
    const ex = run.ex;
    if (run.stage < 0) return done() ? say("Jetzt kennst du die Reihenfolge. Probier es selbst!") : "";
    if (!run.checked) return "";
    if (allRight()) return say(run.fails ? "Geschafft! Die Reihenfolge stimmt." : "Richtig! Die Reihenfolge stimmt.");
    const wrong = run.slots.filter((_, i) => !isRight(i)).length;
    let h = say(wrong === 1 ? "Fast! Ein Schritt steht noch falsch." : `${wrong} Schritte stehen noch falsch.`);
    if (run.fails >= 1 && ex.hilfen && ex.hilfen.denkanstoss) h += say(ex.hilfen.denkanstoss);
    if (run.fails >= 2 && ex.nachschlagen) h += say(`Schau im Buch nach: S. ${ex.nachschlagen.seite}, ${ex.nachschlagen.stelle}.`);
    return h;
  }

  function actionsHtml() {
    const book = run.ex.buch_url
      ? `<button type="button" class="px-check secondary${run.book ? " active" : ""}" data-action="or-book"
          title="${run.book ? "Zurück" : "Im Buch"}" aria-label="${run.book ? "Zurück" : "Im Buch"}">${icon(run.book ? "Pfeil links" : "Lesen")}</button>` : "";
    if (done()) return book + nextButtons();
    if (run.stage < 0) return book;
    const show = run.fails >= 2
      ? `<button type="button" class="px-check secondary" data-action="or-show" title="Lösung zeigen" aria-label="Lösung zeigen">${icon("Anzeigen")}</button>` : "";
    return `${book}${show}<button type="button" class="px-check" data-action="or-check" title="Prüfen" aria-label="Prüfen"${allPlaced() ? "" : " disabled"}>${icon("Haken")}</button>`;
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

  // Feste Seite in Bildschirmhöhe, quer und hoch ohne Scrollen (Plätze und Kärtchen scrollen notfalls in sich)
  function render() {
    if (run.stage === 4) return renderNumbers();
    core.setZen(true);
    runView.innerHTML = `
      ${core.topbarHtml(run.ex, run.stage)}
      <div class="or${run.stage < 0 ? " or-look" : ""}">
        <p class="px-task or-task">${esc(run.ex.aufgabentext)}</p>
        <ol class="or-slots">${slotsHtml()}</ol>
        ${poolHtml()}
        <div class="zo-foot or-foot">
          <div class="px-luna" aria-live="polite">${lunaHtml()}</div>
          <div class="px-actions zo-actions">${actionsHtml()}</div>
        </div>
      </div>`;
  }

  // ---------- Stufe 4: Nummern schreiben ----------
  // run.numbers: Schritt → geschriebene Nummer; run.reads: Schritt → gelesene Striche (für Theas Schrift-Muster)

  const NUMBER_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "⌫"];
  let pad = null;

  function numbersPad() {
    if (!pad) {
      pad = createDigitPad({
        beforeRead: () => (run && run.stage === 4 && run.active !== null && !done() ? { run, card: run.active } : null),
        onRead: (result, target) => {
          if (run !== target.run || run.active !== target.card) return;  // inzwischen weiter
          setNumber(target.card, result.text);
          run.reads[target.card] = { text: result.text, chars: result.chars };
          run.unreadable = result.unsure;
          pad.clear();
          if (!result.unsure) moveToNextEmpty();
          render();
        },
      });
    }
    return pad;
  }

  function setNumber(card, value) {
    run.numbers[card] = value;
    run.checked = false;
  }

  function moveToNextEmpty() {
    const cards = run.ex.karten;
    const from = cards.indexOf(run.active);
    const next = [...cards.slice(from + 1), ...cards.slice(0, from + 1)].find((c) => !run.numbers[c]);
    run.active = next === undefined ? null : next;
  }

  // Aus den Nummern die Plätze: Nummer k → Platz k-1; doppelte oder unpassende Nummern bleiben ohne Platz
  function slotsFromNumbers() {
    const n = steps().length;
    const slots = Array(n).fill(null);
    run.ex.karten.forEach((c) => {
      const k = Number(run.numbers[c]);
      if (Number.isInteger(k) && k >= 1 && k <= n && !slots[k - 1]) slots[k - 1] = c;
    });
    return slots;
  }

  function cardRight(card) {
    const i = run.slots.indexOf(card);
    return i >= 0 && isRight(i);
  }

  function numbersLuna() {
    if (run.unreadable) return say("Die Zahl konnte ich nicht lesen. Schreib sie noch mal oder tipp sie ein.");
    if (!run.checked) return run.fails || Object.keys(run.numbers).length ? "" : say("Schreib vor jeden Schritt seine Nummer.");
    if (allRight()) return say(run.fails ? "Geschafft! Die Reihenfolge stimmt." : "Richtig! Die Reihenfolge stimmt.");
    const wrong = run.ex.karten.filter((c) => !cardRight(c)).length;
    let h = say(wrong === 1 ? "Fast! Eine Nummer stimmt noch nicht." : `${wrong} Nummern stimmen noch nicht.`);
    if (run.fails >= 1 && run.ex.hilfen && run.ex.hilfen.denkanstoss) h += say(run.ex.hilfen.denkanstoss);
    return h;
  }

  function renderNumbers() {
    core.setZen(true);
    const filled = run.ex.karten.every((c) => run.numbers[c]);
    const show = run.fails >= 2 && !done()
      ? `<button type="button" class="px-check secondary" data-action="or-show" title="Lösung zeigen" aria-label="Lösung zeigen">${icon("Anzeigen")}</button>` : "";
    const book = run.ex.buch_url && run.book
      ? `<div class="zo-book or-book"><img src="${esc(run.ex.buch_url)}" alt="Im Buch" draggable="false"></div>` : "";
    runView.innerHTML = `
      ${core.topbarHtml(run.ex, run.stage)}
      <div class="or or-numbers">
        <p class="px-task or-task">${esc(run.ex.aufgabentext)}</p>
        ${book || `<ul class="or-slots or-number-list">${run.ex.karten.map((c) => {
          const state = run.checked ? (cardRight(c) ? " ok" : " wrong") : "";
          const active = run.active === c && !done() ? " active" : "";
          return `<li class="or-row"><button type="button" class="or-num${active}${state}" data-num="${esc(c)}"
            aria-label="Nummer für: ${esc(c)}">${esc(run.numbers[c] || "")}</button><span class="or-step-text">${esc(c)}</span></li>`;
        }).join("")}</ul>`}
        <div class="or-write">
          ${done() ? "" : `<div class="gg-write-slot"></div><div class="gg-pad or-keys" role="group" aria-label="Zahlen">${NUMBER_KEYS.map((k) => k === "⌫"
            ? `<button type="button" class="gg-key" data-key="back" title="Löschen" aria-label="Löschen">${icon("Rückgängig")}</button>`
            : `<button type="button" class="gg-key" data-key="${k}">${k}</button>`).join("")}</div>`}
          <div class="px-luna" aria-live="polite">${numbersLuna()}</div>
          <div class="px-actions zo-actions">
            ${run.ex.buch_url ? `<button type="button" class="px-check secondary${run.book ? " active" : ""}" data-action="or-book" title="${run.book ? "Zurück" : "Im Buch"}" aria-label="${run.book ? "Zurück" : "Im Buch"}">${icon(run.book ? "Pfeil links" : "Lesen")}</button>` : ""}
            ${done() ? nextButtons() : `${show}<button type="button" class="px-check" data-action="or-check" title="Prüfen" aria-label="Prüfen"${filled ? "" : " disabled"}>${icon("Haken")}</button>`}
          </div>
        </div>
      </div>`;
    if (!done()) {
      const p = numbersPad();
      if (p) p.mount(runView.querySelector(".gg-write-slot"), getComputedStyle(runView).color);
    }
  }

  function numberKey(key) {
    if (run.active === null || done()) return;
    const old = run.numbers[run.active] || "";
    setNumber(run.active, key === "back" ? old.slice(0, -1) : (old + key).slice(0, 2));
    run.unreadable = false;
    if (key !== "back" && Number(run.numbers[run.active]) * 10 > steps().length) moveToNextEmpty();  // keine zweite Ziffer möglich
    render();
  }

  function checkNumbers() {
    run.slots = slotsFromNumbers();
    run.checked = true;
    const wrong = run.ex.karten.filter((c) => !cardRight(c));
    if (wrong.length) run.fails += 1;
    logPracticeEvent(run.attempt, "check", { status: wrong.length ? "noch_nicht" : "richtig",
      gelesen: run.ex.karten.map((c) => run.numbers[c]) });
    if (!wrong.length && pad) {
      // Gelesene Ziffern, die unverändert richtig waren, werden Muster für Theas Schrift
      Object.entries(run.reads).forEach(([card, r]) => { if (run.numbers[card] === r.text) pad.learn(r.chars); });
    }
    render();
  }

  // ---------- Bedienung ----------

  function place(i, card) {
    if (run.fixed.has(i)) return;
    const from = run.slots.indexOf(card);
    if (from >= 0) run.slots[from] = run.slots[i];  // von Platz zu Platz: tauschen
    run.slots[i] = card;
    run.active = null;
    run.checked = false;
    render();
  }

  function tapCard(card) {
    const target = run.active !== null && !run.slots[run.active]
      ? run.active
      : run.slots.findIndex((v, i) => !v && !run.fixed.has(i));
    if (target >= 0) place(target, card);
  }

  function tapSlot(i) {
    if (run.stage < 0) {
      run.seen.add(i);
      if (done() && !run.logged) {
        run.logged = true;
        logPracticeEvent(run.attempt, "check", { status: "richtig", angesehen: run.seen.size });
      }
      return render();
    }
    if (done() || run.fixed.has(i)) return;
    if (run.slots[i]) {  // besetzter Platz: Kärtchen zurück, der Platz ist dann gewählt
      run.slots[i] = null;
      run.checked = false;
      run.active = i;
    } else {
      run.active = run.active === i ? null : i;
    }
    render();
  }

  function check() {
    run.checked = true;
    const wrong = run.slots.map((_, i) => i).filter((i) => !isRight(i));
    if (wrong.length) run.fails += 1;
    logPracticeEvent(run.attempt, "check", { status: wrong.length ? "noch_nicht" : "richtig", falsch: wrong.map((i) => i + 1) });
    render();
  }

  function showSolution() {
    if (run.stage === 4) run.ex.karten.forEach((c) => { run.numbers[c] = String(steps().indexOf(c) + 1); });
    run.slots = steps().slice();
    run.checked = true;
    logPracticeEvent(run.attempt, "solution", {});
    render();
  }

  runView.addEventListener("click", (e) => {
    if (!run) return;
    const t = e.target.closest("button");
    if (!t || t.disabled) return;
    if (dragMoved) return;
    if (t.dataset.num !== undefined) {
      if (done()) return;
      run.active = t.dataset.num;
      if (pad) pad.clear();
      return render();
    }
    if (t.dataset.key !== undefined) return numberKey(t.dataset.key);
    if (t.dataset.pad === "clear") {
      if (pad) pad.clear();
      if (run.active !== null) setNumber(run.active, "");
      run.unreadable = false;
      return render();
    }
    if (t.dataset.action === "or-check" && run.stage === 4) return checkNumbers();
    if (t.dataset.slot !== undefined) return tapSlot(Number(t.dataset.slot));
    if (t.dataset.card !== undefined) return tapCard(t.dataset.card);
    if (t.dataset.action === "or-check") return check();
    if (t.dataset.action === "or-show") return showSolution();
    if (t.dataset.action === "or-book") {
      run.book = !run.book;
      if (run.book) logPracticeEvent(run.attempt, "hint", { nachschlagen: true });
      return render();
    }
  });

  // Ziehen mit Finger oder Pencil: Kärtchen auf einen Platz, oder ein gesetztes Kärtchen auf einen anderen Platz
  let drag = null;
  let dragMoved = false;
  runView.addEventListener("pointerdown", (e) => {
    if (!run || run.stage < 0 || done()) return;
    const card = e.target.closest(".or-card");
    const slot = e.target.closest(".or-slot.filled:not(.fixed)");
    const text = card ? card.dataset.card : slot ? run.slots[Number(slot.dataset.slot)] : null;
    if (!text) return;
    dragMoved = false;
    drag = { text, x: e.clientX, y: e.clientY, ghost: null };
  });
  window.addEventListener("pointermove", (e) => {
    if (!drag) return;
    if (!drag.ghost && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 8) {
      dragMoved = true;
      drag.ghost = document.createElement("div");
      drag.ghost.className = "px-token or-card px-ghost";
      drag.ghost.textContent = drag.text;
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
    const target = document.elementFromPoint(e.clientX, e.clientY)?.closest("[data-slot]");
    if (target && run && !done()) place(Number(target.dataset.slot), d.text);
    setTimeout(() => { dragMoved = false; }, 0);
  });
  window.addEventListener("pointercancel", () => {
    if (drag && drag.ghost) drag.ghost.remove();
    drag = null;
  });

  // ---------- Anmeldung beim Kern ----------

  registerPracticeType("ordnen", {
    stages: {
      "-1": { title: "Anschauen: Plätze antippen", name: "Anschauen", icon: "Anzeigen" },
      1: { title: "Ordnen, der Anfang steht schon" },
      2: { title: "Alle Schritte ordnen" },
      3: { title: "Ordnen, mit falschen Schritten dazwischen" },
      4: { title: "Nummern mit dem Stift schreiben" },
    },
    open(ex, stage, coreApi) {
      core = coreApi;
      const fixed = new Set(stage === 1 ? ex.fest : []);
      const slots = ex.schritte.map((s, i) => (fixed.has(i) ? s : null));
      const pool = stage >= 3 ? ex.karten_ablenker : stage === 1 ? ex.karten_hilfe : ex.karten;
      run = { ex, stage, attempt: startPracticeAttempt(ex.id, stage), slots, fixed, pool, active: null,
              checked: false, fails: 0, book: false, seen: new Set(), logged: false,
              numbers: {}, reads: {}, unreadable: false };
      if (stage === 4) run.active = ex.karten[0];
      render();
      return stage;
    },
    close() {
      run = null;
      if (pad) pad.clear();
    },
  });
})();
