// ==========================================================================
// Üben, Übungstyp „Kurzrechnung“ (Mathe; backend: services/exercise_types/kurzrechnung.py)
// --------------------------------------------------------------------------
// Ein Päckchen kurzer Rechnungen, eine nach der anderen. Antwort über die
// Zahlentasten (keine Ziffernerkennung), Brüche mit Zähler- und Nennerfeld,
// daneben die Nebenrechnung (Kästchen, Stift, js/digit_pad.js ohne Erkennung).
// Stufe -1: Ergebnis aus vier Angeboten antippen. Stufe 1: erst den Überschlag
// antippen (Größenordnung), dann eintippen. Stufe 2: gleich eintippen; nach
// einem Fehler kommt der Überschlag als Hilfe. Der Browser prüft (Wert als
// Bruch aus BigInt, kein Rundungsfehler): „Komma“ = Ziffern stimmen, Wert um
// eine Zehnerpotenz daneben; „Wert“ = richtiger Wert, aber nicht der verlangte
// Bruch (nicht fertig gekürzt, mit der falschen Zahl gekürzt).
// Einmaleins-Check (ex.check): Zeit still gemessen (keine Uhr); richtig kurz grün,
// falsch: eigene Antwort durchgestrichen, das richtige Ergebnis daneben, weiter
// mit „Weiter“ (Nutzer 25.10.: Fehler müssen sichtbar sein). Gemessen wird nur die
// erste Antwort. Im Eltern-Modus vorher die Auswertung (sicher / langsam / falsch).
// Jede Antwort geht als Ereignis „step“ mit Zeit an den Server.
// ==========================================================================

(function () {
  const runView = document.getElementById("practice-run-view");
  if (!runView) return;

  let core = null;
  let run = null;
  let pad = null;  // Nebenrechnung, ein Exemplar, wird nur umgehängt

  const esc = (s) => escapeHtml(String(s));
  const say = (t) => `<div class="px-say">${icon("Luna", "px-luna-icon")}<p>${esc(t)}</p></div>`;
  const isParent = () => document.body.classList.contains("parent-mode-active");
  const RIGHT_PAUSE_MS = 700;
  const CHECK_PAUSE_MS = 350;  // Einmaleins-Check: kurz grün, das Tempo bleibt

  // „15/24“ → gestapelter Bruch; sonst Text
  function mathHtml(text) {
    return esc(text).replace(/(\d+)\/(\d+)/g, '<span class="kr-frac"><span>$1</span><span>$2</span></span>');
  }

  // ---------- Werte vergleichen (exakt, als Bruch aus BigInt) ----------

  function parseDecimal(text) {
    const t = String(text).trim();
    if (!/^\d+(,\d*)?$|^,\d+$/.test(t)) return null;
    const [whole, frac = ""] = t.split(",");
    return { n: BigInt((whole || "0") + frac), d: 10n ** BigInt(frac.length) };
  }

  const big = (pair) => ({ n: BigInt(pair[0]), d: BigInt(pair[1]) });
  const sameValue = (a, b) => a.n * b.d === b.n * a.d;

  function isPow10(x) {
    if (x < 10n) return false;
    while (x % 10n === 0n) x /= 10n;
    return x === 1n;
  }

  // Wert um eine Zehnerpotenz daneben (Komma verschoben)?
  function commaOff(a, b) {
    const p = a.n * b.d, q = b.n * a.d;
    if (p === 0n || q === 0n) return false;
    return p > q ? p % q === 0n && isPow10(p / q) : q % p === 0n && isPow10(q / p);
  }

  // Ergebnis: richtig | komma | wert | falsch | leer
  function judge(item, input) {
    if (item.antwort === "bruch") {
      if (!input.z || !input.n || /^0+$/.test(input.n)) return "leer";
      const given = { n: BigInt(input.z), d: BigInt(input.n) };
      if (item.exakt) {
        if (given.n === BigInt(item.exakt[0]) && given.d === BigInt(item.exakt[1])) return "richtig";
        return sameValue(given, big(item.wert)) ? "wert" : "falsch";
      }
      return sameValue(given, big(item.wert)) ? "richtig" : "falsch";
    }
    const given = parseDecimal(input.zahl);
    if (!given) return "leer";
    if (sameValue(given, big(item.wert))) return "richtig";
    return commaOff(given, big(item.wert)) ? "komma" : "falsch";
  }

  function answerText(item, input) {
    return item.antwort === "bruch" ? `${input.z}/${input.n}` : input.zahl;
  }

  // ---------- Ablauf ----------

  const item = () => run.ex.liste[run.i];
  const freshInput = () => ({ zahl: "", z: "", n: "", field: "z" });

  function startItem() {
    run.input = freshInput();
    run.fails = 0;
    run.state = "offen";       // offen | richtig | gezeigt
    run.msg = "";
    run.tried = new Set();     // Stufe -1: falsch angetippte Angebote
    run.ueWrong = new Set();
    run.ueDone = !(run.stage === 1 && item().ueberschlag);
    run.ueShown = false;       // Stufe 2: Überschlag als Hilfe nach einem Fehler
    run.firstAnswer = true;
    run.t0 = performance.now();
    if (pad) pad.clear();
    render();
  }

  function finishItem(state) {
    run.state = state;
    run.results[run.i] = state;
    render();
    if (state === "richtig") {
      const i = run.i;
      setTimeout(() => { if (run && run.i === i && run.state === "richtig") nextItem(); }, run.ex.check ? CHECK_PAUSE_MS : RIGHT_PAUSE_MS);
    }
  }

  function nextItem() {
    if (run.i + 1 < run.ex.liste.length) {
      run.i += 1;
      return startItem();
    }
    run.done = true;
    const shown = run.results.filter((r) => r === "gezeigt").length;
    if (!shown) logPracticeEvent(run.attempt, "check", { status: "richtig", aufgaben: run.ex.liste.length, fehler: run.totalFails });
    render();
  }

  function logStep(answer, verdict, extra = {}) {
    logPracticeEvent(run.attempt, "step", {
      aufgabe: item().id, antwort: answer, richtig: verdict === "richtig", art: verdict,
      ms: Math.round(performance.now() - run.t0), ...extra,
    });
  }

  function submit(answer, verdict) {
    if (verdict === "leer") return;
    const ms = Math.round(performance.now() - run.t0);
    logStep(answer, verdict);
    if (run.ex.check) {  // Check: nur die erste Antwort zählt; falsch → richtiges Ergebnis zeigen
      if (verdict === "richtig") return finishItem("richtig");
      run.given = answer;
      const [z, n] = item().antwort === "bruch" ? item().loesung.split("/") : [];
      run.input = item().antwort === "bruch" ? { ...run.input, z, n } : { ...run.input, zahl: item().loesung };
      return finishItem("korrigiert");
    }
    const first = run.firstAnswer;
    run.firstAnswer = false;
    if (verdict === "richtig") {
      // Wacklige Einmaleins-Aufgaben: richtig, aber langsam zählt still als „noch nicht sicher“
      if (first && run.ex.grenze_ms && ms > run.ex.grenze_ms) {
        logPracticeEvent(run.attempt, "check", { status: "noch_nicht", aufgabe: item().id, art: "langsam" });
      }
      run.msg = "";
      return finishItem("richtig");
    }
    run.fails += 1;
    run.totalFails += 1;
    logPracticeEvent(run.attempt, "check", { status: "noch_nicht", aufgabe: item().id, antwort: answer, art: verdict });
    run.msg = verdict;
    // Stufe 2: nach einem Fehler erst einen Überschlag machen (wo es einen gibt)
    if (run.stage === 2 && item().ueberschlag && !run.ueShown && verdict !== "wert") {
      run.ueShown = true;
      run.ueDone = false;
      logPracticeEvent(run.attempt, "hint", { aufgabe: item().id, ueberschlag: true });
    }
    render();
  }

  function showSolution() {
    const it = item();
    if (it.antwort === "bruch") {
      const [z, n] = it.loesung.split("/");
      run.input = { ...run.input, z, n };
    } else {
      run.input = { ...run.input, zahl: it.loesung };
    }
    logPracticeEvent(run.attempt, "solution", { aufgabe: it.id });
    run.msg = "";
    finishItem("gezeigt");
  }

  // ---------- Darstellung ----------

  function dotsHtml() {
    if (run.ex.liste.length < 2) return "";
    return `<div class="kr-dots" aria-label="Aufgabe ${run.i + 1} von ${run.ex.liste.length}">${run.ex.liste.map((_, i) => {
      const cls = ["gezeigt", "korrigiert"].includes(run.results[i]) ? " shown" : run.results[i] ? " done" : i === run.i ? " now" : "";
      return `<span class="kr-dot${cls}"></span>`;
    }).join("")}</div>`;
  }

  function answerBoxHtml() {
    const it = item();
    const st = run.state === "richtig" ? " ok" : ["gezeigt", "korrigiert"].includes(run.state) ? " shown" : run.msg ? " wrong" : "";
    if (run.stage < 0 && run.state === "offen") return `<span class="kr-box kr-box-empty${st}"></span>`;
    if (it.antwort === "bruch") {
      const f = (key) => `<button type="button" class="kr-box kr-field${st}${run.input.field === key && run.state === "offen" ? " active" : ""}" data-field="${key}" aria-label="${key === "z" ? "Zähler" : "Nenner"}">${esc(run.input[key])}</button>`;
      return `<span class="kr-frac kr-frac-input">${f("z")}${f("n")}</span>`;
    }
    return `<span class="kr-box${st}${run.state === "offen" ? " active" : ""}">${esc(run.input.zahl)}</span>`;
  }

  // Aufgabe in einer Zeile: Nummer, Rechnung, = (bei „Kürze …“/„Dividiere …“ ein Pfeil wie auf dem Blatt), Antwort, Einheit
  function lineHtml() {
    const it = item();
    return `<div class="kr-line">
          ${it.nummer ? `<span class="kr-no">${esc(it.nummer)}</span>` : ""}
          <span class="kr-expr">${mathHtml(it.zeige)}</span>
          <span class="kr-eq">${it.vor ? "→" : "="}</span>
          ${run.state === "korrigiert" ? `<s class="kr-given" aria-label="Deine Antwort">${esc(run.given)}</s>` : ""}
          ${answerBoxHtml()}
          ${it.nach ? `<span class="kr-unit">${esc(it.nach)}</span>` : ""}
        </div>`;
  }

  function taskHtml() {
    const it = item();
    return `
      <div class="kr-task">
        ${dotsHtml()}
        ${it.vor ? `<div class="kr-vor">${esc(it.vor)}</div>` : ""}
        ${lineHtml()}
      </div>`;
  }

  function estimateHtml() {
    const it = item();
    if (!it.ueberschlag || run.stage < 0 || (run.stage === 2 && !run.ueShown)) return "";
    const ue = it.ueberschlag;
    const buttons = ue.angebote.map((v, i) => {
      const cls = run.ueDone && i === ue.richtig ? " chosen" : run.ueWrong.has(i) ? " wrong" : "";
      return `<button type="button" class="kr-opt kr-ue${cls}" data-ue="${i}"${run.ueDone || run.ueWrong.has(i) ? " disabled" : ""}>${esc(v)}</button>`;
    }).join("");
    return `<div class="kr-estimate" role="group" aria-label="Überschlag"><span class="kr-approx" title="Überschlag">≈</span><div class="kr-opts">${buttons}</div></div>`;
  }

  function choicesHtml() {
    const a = item().auswahl;
    return `<div class="kr-opts kr-choices" role="group" aria-label="Ergebnis">${a.angebote.map((v, i) => {
      const cls = run.state !== "offen" && i === a.richtig ? " ok" : run.tried.has(i) ? " wrong" : "";
      return `<button type="button" class="kr-opt kr-choice${cls}" data-choice="${i}"${run.state !== "offen" || run.tried.has(i) ? " disabled" : ""}>${mathHtml(v)}</button>`;
    }).join("")}</div>`;
  }

  function lunaHtml() {
    const it = item();
    if (run.done) return "";
    if (run.ex.check) return "";
    if (run.state === "richtig") return say("Richtig!");
    if (run.state === "gezeigt") return say(`So geht es: ${it.loesung}`);
    if (!run.ueDone && run.stage === 1 && !run.ueWrong.size && run.i === 0) return say("Erst ungefähr: Wie groß wird das Ergebnis?");
    if (!run.ueDone && run.ueWrong.size) return say("Das passt nicht. Wie groß wird das Ergebnis ungefähr?");
    if (!run.ueDone && run.stage === 2) return say("Mach erst einen Überschlag.");
    if (run.msg === "komma") {
      const ue = it.ueberschlag && run.ueDone ? it.ueberschlag.angebote[it.ueberschlag.richtig] : null;
      return say(ue ? `Die Ziffern stimmen. Dein Überschlag sagt ≈ ${ue}. Wo steht das Komma?` : "Die Ziffern stimmen. Wo steht das Komma?");
    }
    if (run.msg === "wert") return say(it.hinweis_wert);
    if (run.msg === "falsch") return say(run.fails >= 2 ? "Noch nicht. Rechne in der Nebenrechnung." : "Noch nicht.");
    return "";
  }

  const PAD_KEYS = ["7", "8", "9", "4", "5", "6", "1", "2", "3"];

  function keypadHtml() {
    const it = item();
    const locked = run.state !== "offen" || !run.ueDone;
    const third = it.antwort === "bruch"
      ? `<button type="button" class="gg-key" data-key="field" title="Zähler / Nenner" aria-label="Zähler oder Nenner">${icon(run.input.field === "z" ? "Pfeil runter" : "Pfeil hoch")}</button>`
      : `<button type="button" class="gg-key" data-key=",">,</button>`;
    return `<div class="kr-pad${locked ? " locked" : ""}" role="group" aria-label="Zahlen">
      ${PAD_KEYS.map((k) => `<button type="button" class="gg-key" data-key="${k}"${locked ? " disabled" : ""}>${k}</button>`).join("")}
      ${third.replace("<button", `<button${locked ? " disabled" : ""}`)}
      <button type="button" class="gg-key" data-key="0"${locked ? " disabled" : ""}>0</button>
      <button type="button" class="gg-key" data-key="back" title="Löschen" aria-label="Löschen"${locked ? " disabled" : ""}>${icon("Rückgängig")}</button>
    </div>`;
  }

  function actionsHtml() {
    if (run.done) return nextButtons();
    if (run.state === "gezeigt" || run.state === "korrigiert") return `<button type="button" class="px-check" data-action="kr-next" title="Weiter" aria-label="Weiter">${icon("Pfeil rechts")}</button>`;
    if (run.state !== "offen") return "";
    const show = !run.ex.check && run.fails >= 2
      ? `<button type="button" class="px-check secondary" data-action="kr-show" title="Lösung zeigen" aria-label="Lösung zeigen">${icon("Anzeigen")}</button>` : "";
    const book = !run.ex.check && run.fails >= 1 && run.ex.nachschlagen
      ? `<button type="button" class="px-check secondary" data-action="kr-book" title="Nachschlagen" aria-label="Nachschlagen">${icon("Lesen")}</button>` : "";
    if (run.stage < 0) return book + show;
    const empty = judge(item(), run.input) === "leer";
    const go = run.ex.check
      ? `<button type="button" class="px-check" data-action="kr-submit" title="Weiter" aria-label="Weiter"${empty ? " disabled" : ""}>${icon("Pfeil rechts")}</button>`
      : `<button type="button" class="px-check" data-action="kr-submit" title="Prüfen" aria-label="Prüfen"${empty || !run.ueDone ? " disabled" : ""}>${icon("Haken")}</button>`;
    return book + show + go;
  }

  function nextButtons() {
    if (core.inRound()) return core.roundNextHtml();
    const ex = run.ex;
    const next = ex.stufen.find((s) => s > run.stage);
    const twinId = ex.zwilling_von || ex.zwillinge[0];
    let h = next !== undefined && !ex.check
      ? `<button type="button" class="px-check" data-stage="${next}" title="Weiter mit Stufe ${next}" aria-label="Weiter mit Stufe ${next}">${icon("Pfeil hoch")}<span>${next}</span></button>` : "";
    if (twinId) h += `<button type="button" class="px-check secondary" data-action="open" data-id="${esc(twinId)}" data-at="${run.stage}" title="Ähnliche Aufgabe">${icon("Wiederholen")}</button>`;
    return h + `<button type="button" class="px-check secondary" data-action="back" title="Zur Liste">${icon("Erledigt")}</button>`;
  }

  function doneHtml() {
    const shown = run.results.filter((r) => r === "gezeigt").length;
    const text = run.ex.check ? "Geschafft! Danke." : shown
      ? `Fertig! Bei ${shown === 1 ? "einer Aufgabe" : `${shown} Aufgaben`} hast du die Lösung angesehen.`
      : run.totalFails ? "Geschafft! Alles richtig." : "Richtig! Alles auf Anhieb.";
    return `<div class="kr kr-done">
      <div class="kr-task">${dotsHtml()}<div class="kr-done-mark">${icon(shown ? "Haken" : "Feier")}</div></div>
      <div class="px-luna" aria-live="polite">${say(text)}</div>
      <div class="px-actions kr-actions">${nextButtons()}</div>
    </div>`;
  }

  function bookHtml() {
    const n = run.ex.nachschlagen;
    return say(`Schau nach: ${n.material}${n.seite ? `, S. ${n.seite}` : ""}${n.stelle ? ` – ${n.stelle}` : ""}.`);
  }

  // Feste Seite in Bildschirmhöhe; quer: links Aufgabe + Nebenrechnung, rechts Antwort + Tasten
  function render() {
    core.setZen(true);
    if (run.done) {
      runView.innerHTML = core.topbarHtml(run.ex, run.stage) + doneHtml();
      return;
    }
    const tapStage = run.stage < 0;
    const scratch = !run.ex.check && !tapStage;
    runView.innerHTML = `
      ${core.topbarHtml(run.ex, run.stage)}
      <div class="kr${tapStage ? " kr-tap" : ""}${run.ex.check ? " kr-check" : ""}${scratch ? "" : " kr-noscratch"}" style="--subject-color:${subjectColor(run.ex.fach)}">
        <div class="kr-left">
          ${run.i === 0 && !run.ex.check ? `<p class="px-task kr-text">${esc(run.ex.aufgabentext)}</p>` : ""}
          ${taskHtml()}
          ${estimateHtml()}
          ${tapStage ? choicesHtml() : ""}
          <div class="px-luna" aria-live="polite">${lunaHtml()}${run.book ? bookHtml() : ""}</div>
          ${scratch ? '<div class="gg-write-slot"></div>' : ""}
        </div>
        <div class="kr-right">
          ${tapStage ? "" : keypadHtml()}
          <div class="px-actions kr-actions">${actionsHtml()}</div>
        </div>
      </div>`;
    if (scratch) mountPad();
  }

  function mountPad() {
    if (!pad) pad = typeof createDigitPad === "function" ? createDigitPad({ recognize: false }) : null;
    if (pad) pad.mount(runView.querySelector(".gg-write-slot"), getComputedStyle(runView).color);
  }

  // Nur Antwort und Knöpfe neu zeichnen (die Nebenrechnung bleibt, wie sie ist)
  function refreshAnswer() {
    const line = runView.querySelector(".kr-line");
    if (line) line.outerHTML = lineHtml();
    const actions = runView.querySelector(".kr-right .kr-actions");
    if (actions) actions.innerHTML = actionsHtml();
    const keypad = runView.querySelector(".kr-pad");
    if (keypad) keypad.outerHTML = keypadHtml();
  }

  // ---------- Bedienung ----------

  function key(k) {
    if (run.state !== "offen" || !run.ueDone) return;
    const inp = run.input;
    const it = item();
    if (it.antwort === "bruch") {
      if (k === "field") inp.field = inp.field === "z" ? "n" : "z";
      else if (k === "back") inp[inp.field] = inp[inp.field].slice(0, -1);
      else if (/^\d$/.test(k) && inp[inp.field].length < 6) inp[inp.field] += k;
    } else if (k === "back") {
      inp.zahl = inp.zahl.slice(0, -1);
    } else if (k === ",") {
      if (!inp.zahl.includes(",")) inp.zahl = (inp.zahl || "0") + ",";
    } else if (inp.zahl.replace(",", "").length < 12) {
      inp.zahl += k;
    }
    if (run.msg) run.msg = "";
    refreshAnswer();
    const luna = runView.querySelector(".kr-left .px-luna");
    if (luna) luna.innerHTML = lunaHtml();
  }

  function tapEstimate(i) {
    const ue = item().ueberschlag;
    if (i === ue.richtig) {
      run.ueDone = true;
      logStep(ue.angebote[i], "richtig", { ueberschlag: true });  // die Zeit läuft weiter: der Überschlag gehört zur Aufgabe
    } else {
      run.ueWrong.add(i);
      logStep(ue.angebote[i], "falsch", { ueberschlag: true });
      if (run.ueWrong.size >= 2) run.ueDone = true;  // dann zeigt die Markierung den richtigen
    }
    render();
  }

  function tapChoice(i) {
    const a = item().auswahl;
    const value = a.angebote[i];
    if (i === a.richtig) return submit(value, "richtig");
    run.tried.add(i);
    const verdict = item().antwort === "zahl" && commaOff(parseDecimal(value) || { n: 0n, d: 1n }, big(item().wert)) ? "komma" : "falsch";
    submit(value, verdict);
  }

  runView.addEventListener("click", (e) => {
    if (!run) return;
    const t = e.target.closest("button");
    if (!t || t.disabled) return;
    if (t.dataset.key !== undefined) return key(t.dataset.key);
    if (t.dataset.field) {
      if (run.state === "offen") { run.input.field = t.dataset.field; refreshAnswer(); }
      return;
    }
    if (t.dataset.ue !== undefined) return tapEstimate(Number(t.dataset.ue));
    if (t.dataset.choice !== undefined) return tapChoice(Number(t.dataset.choice));
    if (t.dataset.action === "kr-submit") return submit(answerText(item(), run.input), judge(item(), run.input));
    if (t.dataset.action === "kr-show") return showSolution();
    if (t.dataset.action === "kr-next") return nextItem();
    if (t.dataset.action === "kr-start") return startItem();
    if (t.dataset.action === "kr-book") {
      run.book = !run.book;
      if (run.book) logPracticeEvent(run.attempt, "hint", { nachschlagen: true });
      return render();
    }
  });

  // ---------- Einmaleins-Check: Auswertung für die Eltern ----------

  async function showEvaluation() {
    core.setZen(true);
    let data = null;
    try {
      data = (await apiJson(`/api/v1/practice/${encodeURIComponent(run.ex.id)}/auswertung`)).auswertung;
    } catch (err) {
      console.warn("Auswertung nicht geladen:", err);
    }
    if (!run) return;
    const start = `<button type="button" class="px-check" data-action="kr-start" title="Check starten" aria-label="Check starten">${icon("Pfeil rechts")}</button>`;
    if (!data) {
      runView.innerHTML = `${core.topbarHtml(run.ex, run.stage)}<div class="kr-eval"><div class="px-actions kr-actions">${start}</div></div>`;
      return;
    }
    const cell = (a, b) => {
      const key = `${Math.min(a, b)}·${Math.max(a, b)}`;
      const c = data.zellen[key];
      if (!c) return `<span class="kr-cell"></span>`;
      const title = `${a} · ${b}: ${c.richtig ? "" : `${c.antwort} – `}${(c.ms / 1000).toFixed(1).replace(".", ",")} s`;
      return `<span class="kr-cell ${c.status}${data.wacklig.includes(key) ? " still" : ""}" title="${esc(title)}">${a * b}</span>`;
    };
    let grid = `<span class="kr-cell head">·</span>`;
    for (let b = 2; b <= 9; b++) grid += `<span class="kr-cell head">${b}</span>`;
    for (let a = 2; a <= 9; a++) {
      grid += `<span class="kr-cell head">${a}</span>`;
      for (let b = 2; b <= 9; b++) grid += cell(a, b);
    }
    const day = new Date(data.datum + "Z").toLocaleDateString("de-DE");
    const sec = (ms) => (ms / 1000).toFixed(1).replace(".", ",");
    runView.innerHTML = `
      ${core.topbarHtml(run.ex, run.stage)}
      <div class="kr-eval">
        <div class="kr-eval-head">${esc(day)} · Median ${sec(data.median_ms)} s · langsam ab ${sec(data.grenze_ms)} s · ${data.wacklig.length} wacklig</div>
        <div class="kr-grid">${grid}</div>
        <div class="kr-legend"><span class="kr-cell sicher"></span>sicher <span class="kr-cell langsam"></span>langsam <span class="kr-cell falsch"></span>falsch</div>
        <div class="px-actions kr-actions">${start}</div>
      </div>`;
  }

  // ---------- Anmeldung beim Kern ----------

  registerPracticeType("kurzrechnung", {
    stages: {
      "-1": { title: "Ergebnis antippen", name: "Antippen", icon: "Hand" },
      1: { title: "Erst Überschlag, dann rechnen" },
      2: { title: "Rechnen" },
    },
    open(ex, stage, coreApi) {
      core = coreApi;
      run = { ex, stage, attempt: startPracticeAttempt(ex.id, stage), i: 0, results: [], totalFails: 0,
              done: false, book: false };
      if (!ex.liste.length) {
        run.done = true;
        render();
        return stage;
      }
      if (ex.check && isParent() && !core.inRound()) {
        showEvaluation();
        return stage;
      }
      startItem();
      return stage;
    },
    close() {
      run = null;
    },
  });
})();
