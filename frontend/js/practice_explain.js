// ==========================================================================
// Üben: Erklär-Stufe (alle Fächer; backend: services/explanations.py)
// --------------------------------------------------------------------------
// Luna erklärt eine echte Aufgabe Schritt für Schritt (abgestimmt 31.10. am
// Klick-Modell): immer nur ein kurzer Satz, geschrieben und vorgelesen; genau
// das, wovon er spricht, leuchtet (Textstelle, Tabellenfeld, Kärtchen); Dinge
// erscheinen erst, wenn Luna davon spricht. Nach dem Satz kurze Pause, dann
// von selbst der nächste Satz des Schritts; „Weiter“ springt vor bzw. öffnet
// den nächsten Schritt. Zum Schluss Fragen zum Antippen, auch vorgelesen.
// Audio: vorab eingesprochen (hilfe/saetze/), ein Audio-Element für alles –
// Safari erlaubt es nach dem ersten Antippen. Ohne Ton läuft es im Lesetempo.
// window.openPracticeExplain(host, data, { onDone(falsch), doneHtml() }) → { close() }
// ==========================================================================

(function () {
  const esc = (s) => escapeHtml(String(s));
  const PAUSE_MS = 700;   // wie die Satzpause der Stimme (OPENAI_TTS_PAUSE_MS)
  const SILENT = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=";

  // Ein Audio-Element, beim ersten Antippen irgendwo freigeschaltet (iPad spielt sonst nach dem Laden nicht)
  const audio = new Audio();
  let unlocked = false;
  document.addEventListener("pointerdown", () => {
    if (unlocked) return;
    unlocked = true;
    if (!audio.src || audio.src === SILENT) {
      audio.src = SILENT;
      const p = audio.play();
      if (p && p.catch) p.catch(() => {});
    }
  }, { capture: true });

  window.openPracticeExplain = function (host, data, opts) {
    const st = { step: 0, beat: 0, quiz: -1, qbeat: 0, picked: null, done: false, reading: true, wrong: 0 };
    let token = 0, timer = null, closed = false;

    // ---------- was gerade gilt ----------
    const beats = () => data.schritte[st.step];
    const inSteps = () => st.quiz < 0 && !st.done;
    function current() {
      if (st.done) return { satz: "Geschafft!", audio: null };
      if (st.quiz >= 0) {
        const q = data.abfrage[st.quiz];
        if (st.picked !== null) return { satz: q.warum[st.picked], audio: q.audio.warum[st.picked] };
        if (st.qbeat === 0) return { satz: q.frage, audio: q.audio.frage };
        return { satz: q.antworten[st.qbeat - 1], audio: q.audio.antworten[st.qbeat - 1] };
      }
      return beats()[st.beat];
    }
    function lastBeat() {
      if (st.done) return true;
      if (st.quiz >= 0) return st.picked !== null || st.qbeat >= data.abfrage[st.quiz].antworten.length;
      return st.beat >= beats().length - 1;
    }
    // Sichtbar: alles aus früheren Schritten (Kärtchen ohne „bleibt“ nur in ihrem Schritt) und bis zum aktuellen Satz
    function shownSet() {
      const shown = new Set();
      const upto = inSteps() ? st.step : data.schritte.length;
      data.schritte.forEach((step, si) => step.forEach((b, bi) => {
        if (si < upto || (inSteps() && si === st.step && bi <= st.beat)) b.neu.forEach((id) => {
          const card = data.karten[id];
          if (!card || card.bleibt || (inSteps() && si === st.step)) shown.add(id);
        });
      }));
      return shown;
    }

    // ---------- Darstellung ----------
    // Nebeneinanderliegende leuchtende Stücke als eine Markierung (sonst zerfällt ein Satz in Einzelteile)
    function taskHtml(lit) {
      const runs = [];
      data.segmente.forEach((s) => {
        const on = s.marken.some((m) => lit.has(m));
        const last = runs[runs.length - 1];
        if (last && last.on === on) last.t += s.t; else runs.push({ on, t: s.t });
      });
      return runs.map((r) => (r.on ? `<mark class="pe-hl">${esc(r.t)}</mark>` : esc(r.t))).join("");
    }
    function cardsHtml(shown, lit) {
      let h = Object.entries(data.karten).filter(([id]) => shown.has(id)).map(([id, c]) =>
        `<div class="pe-card${c.art === "ok" ? " ok" : ""}${lit.has(id) ? " lit" : ""}">${c.art === "ok" ? icon("Haken") : ""}<span>${esc(c.text)}</span></div>`).join("");
      if (shown.has("antwort")) {
        h += `<div class="pe-card answer${lit.has("antwort") ? " lit" : ""}"><b>A:</b><span>${esc(data.antwort)}</span></div>`;
      }
      return h;
    }
    function cell(id, text, shown, lit, extra = "") {
      const on = shown.has(id);
      return `<td class="pe-cell${on ? " on" : ""}${lit.has(id) ? " lit" : ""}${extra}">${on ? esc(text) : ""}</td>`;
    }
    function dreisatzHtml(d, shown, lit) {
      const any = [...shown].some((id) => /^(z|p)\d/.test(id));
      if (!any) return "";
      const head = (id, t) => `<th class="pe-head${lit.has(id) ? " lit" : ""}">${esc(t)}</th>`;
      const row = (n) => {
        const [l, r] = d.zeilen[n - 1];
        // Gefragtes Feld: ein Fragezeichen, solange es noch nicht ausgerechnet ist
        const ask = n === 3 && shown.has("z3l") && !shown.has("z3r");
        const right = ask ? `<td class="pe-cell on ask${lit.has("z3r") ? " lit" : ""}">?</td>` : cell(`z${n}r`, r, shown, lit);
        return `<tr><td></td>${cell(`z${n}l`, l, shown, lit)}${right}<td></td></tr>`;
      };
      const ops = (n) => {
        const [l, r] = d.pfeile[n - 1];
        const op = (id, t, side) => `<td class="pe-op ${side}${lit.has(id) ? " lit" : ""}">${shown.has(id) ? esc(t.replace(/^([:·])/, "$1 ")) : ""}</td>`;
        return `<tr class="pe-oprow">${op(`p${n}l`, l, "l")}<td></td><td></td>${op(`p${n}r`, r, "r")}</tr>`;
      };
      return `<table class="pe-table"><thead><tr><th></th>${head("kopf_l", d.kopf[0])}${head("kopf_r", d.kopf[1])}<th></th></tr></thead>
        <tbody>${row(1)}${ops(1)}${row(2)}${ops(2)}${row(3)}</tbody></table>`;
    }
    function rechnungHtml(d, shown, lit) {
      const parts = d.teile.filter((t) => shown.has(t.id));
      if (!parts.length) return "";
      const line = (label) => {
        const ps = parts.filter((t) => t.zeile === label);
        return ps.length ? `<div class="pe-calc"><b>${label}:</b>${ps.map((t) => `<span class="${lit.has(t.id) ? "lit" : ""}">${esc(t.text)}</span>`).join("")}</div>` : "";
      };
      return `<div class="pe-calcs">${line("Ü")}${line("R")}</div>`;
    }
    function displayHtml(shown, lit) {
      const d = data.anzeige;
      const inner = d.art === "dreisatz" ? dreisatzHtml(d, shown, lit) : rechnungHtml(d, shown, lit);
      return inner ? `<div class="pe-display">${inner}</div>` : "";
    }
    function quizHtml() {
      const q = data.abfrage[st.quiz];
      const answered = st.picked !== null, right = answered && st.picked === q.richtig;
      return `<div class="pe-quiz">
        <div class="pe-quiz-head">${st.quiz + 1} / ${data.abfrage.length}</div>
        ${q.antworten.map((a, i) => {
          let cls = !answered && st.qbeat === i + 1 ? " lit" : "";
          if (answered && i === st.picked) cls = right ? " ok" : " wrong";
          return `<button type="button" class="pe-answer${cls}" data-pe-pick="${i}"${right ? " disabled" : ""}>${esc(a)}</button>`;
        }).join("")}
      </div>`;
    }
    function dotsHtml() {
      const total = data.schritte.length + data.abfrage.length;
      const pos = st.done ? total : (st.quiz >= 0 ? data.schritte.length + st.quiz : st.step);
      return Array.from({ length: total }, (_, i) => `<span class="pe-dot${i < pos ? " done" : i === pos ? " now" : ""}"></span>`).join("");
    }
    // Sprechblase: in der Abfrage bleibt die Frage stehen, während Luna die Antworten vorliest (die leuchten)
    function bubbleText() {
      if (st.quiz >= 0 && st.picked === null) return data.abfrage[st.quiz].frage;
      return current().satz;
    }
    function render() {
      if (closed) return;
      const lit = new Set(inSteps() ? current().zeige : []);
      const shown = shownSet();
      const q = st.quiz >= 0 ? data.abfrage[st.quiz] : null;
      const canNext = !st.reading && !st.done && (inSteps() || (q && st.picked === q.richtig));
      host.innerHTML = `
        <div class="pe">
          <div class="pe-left">
            <div class="pe-task"><p>${taskHtml(lit)}</p></div>
            ${cardsHtml(shown, lit)}
          </div>
          <div class="pe-right">
            <div class="pe-say">${icon("Luna", "px-luna-icon")}<p aria-live="polite">${esc(bubbleText())}</p>
              <button type="button" class="practice-icon-btn" data-pe="replay" title="Noch mal hören" aria-label="Noch mal hören">${icon("Lautsprecher")}</button></div>
            ${st.done ? `<div class="pe-done">${icon("Haken")}<div class="px-actions">${opts.doneHtml ? opts.doneHtml() : ""}</div></div>`
              : q ? quizHtml() : displayHtml(shown, lit)}
          </div>
        </div>
        <div class="pe-nav">
          <button type="button" class="px-check secondary pe-back" data-pe="back" title="Zurück" aria-label="Zurück"${st.step === 0 && st.quiz < 0 && !st.done ? " disabled" : ""}>${icon("Pfeil links")}</button>
          <div class="pe-dots" aria-hidden="true">${dotsHtml()}</div>
          <button type="button" class="px-check pe-next${canNext ? " ready" : ""}" data-pe="next" title="Weiter" aria-label="Weiter"${st.done ? " disabled" : ""}>${icon("Pfeil rechts")}</button>
        </div>`;
    }

    // ---------- Vorlesen und Weiterlaufen ----------
    function advance() {
      if (lastBeat()) { st.reading = false; return render(); }
      if (st.quiz >= 0) st.qbeat += 1; else st.beat += 1;
      play();
    }
    function play() {
      const my = ++token;
      clearTimeout(timer);
      st.reading = true;
      render();
      const { satz, audio: url } = current();
      const after = () => {
        if (my !== token || closed) return;
        timer = setTimeout(() => { if (my === token && !closed) advance(); }, PAUSE_MS);
      };
      const byReadingTime = () => { timer = setTimeout(after, 400 + satz.length * 55); };
      if (st.done) { st.reading = false; return render(); }
      if (!url) return byReadingTime();
      audio.onended = after;
      audio.onerror = () => { if (my === token) byReadingTime(); };
      audio.src = url;
      const p = audio.play();
      if (p && p.catch) p.catch(() => { if (my === token) byReadingTime(); });
    }
    function stop() {
      token++;
      clearTimeout(timer);
      audio.onended = null;
      audio.onerror = null;
      audio.pause();
    }

    function next() {
      if (st.done) return;
      if (!lastBeat()) { stop(); return advance(); }
      if (inSteps()) {
        if (st.step < data.schritte.length - 1) { st.step += 1; st.beat = 0; }
        else { st.quiz = 0; st.qbeat = 0; st.picked = null; }
        return play();
      }
      const q = data.abfrage[st.quiz];
      if (st.picked !== q.richtig) return;
      if (st.quiz < data.abfrage.length - 1) { st.quiz += 1; st.qbeat = 0; st.picked = null; return play(); }
      st.quiz = -1; st.done = true; st.picked = null;
      stop();
      if (opts.onDone) opts.onDone(st.wrong);
      play();
    }
    function back() {
      stop();
      if (st.done) { st.done = false; st.quiz = data.abfrage.length - 1; st.qbeat = 0; st.picked = null; }
      else if (st.quiz > 0) { st.quiz -= 1; st.qbeat = 0; st.picked = null; }
      else if (st.quiz === 0) { st.quiz = -1; st.step = data.schritte.length - 1; st.beat = 0; st.picked = null; }
      else if (st.step > 0) { st.step -= 1; st.beat = 0; }
      play();
    }
    function pick(i) {
      const q = data.abfrage[st.quiz];
      if (st.picked === q.richtig) return;
      stop();
      st.picked = i;
      if (i !== q.richtig) st.wrong += 1;
      play();
    }

    host.addEventListener("click", (e) => {
      const t = e.target.closest("button");
      if (!t || t.disabled || closed) return;
      if (t.dataset.pe === "next") return next();
      if (t.dataset.pe === "back") return back();
      if (t.dataset.pe === "replay") {
        stop();
        if (st.quiz >= 0) { st.qbeat = 0; st.picked = st.picked === data.abfrage[st.quiz].richtig ? st.picked : null; }
        else if (!st.done) st.beat = 0;
        return play();
      }
      if (t.dataset.pePick !== undefined) return pick(Number(t.dataset.pePick));
    });

    play();
    return { close() { closed = true; stop(); } };
  };
})();
