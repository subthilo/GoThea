// ==========================================================================
// Üben: Anleitung hinter dem ?-Knopf (Übungs-Kopfleiste und Übungstafel)
// --------------------------------------------------------------------------
// Was in dieser Stufe zu tun ist und wie man bedient und korrigiert – als
// kurzer Text und vorab eingesprochen mit Lunas Stimme (Nutzer 31.10.).
// Texte: frontend/hilfe/uebungen.json (je Typ und Stufe, "check" = Einmaleins-
// Check), Audio: scripts/build_practice_help_audio.py → hilfe/audio/.
// Knopf = beliebiges Element mit data-practice-help, data-typ, data-stufe und
// optional data-titel; ein Antippen öffnet und spielt, noch eins schließt.
// ==========================================================================

(function () {
  const esc = (s) => escapeHtml(String(s));
  let data = null;  // Promise: { texte, audio }
  let panel = null, audio = null, openBtn = null;
  // Wechselt die Ansicht (andere Stufe, Übung zu), verschwindet der Knopf – dann auch die Anleitung.
  // Beobachtet wird nur, solange eine Anleitung offen ist.
  const watch = new MutationObserver(() => { if (openBtn && !openBtn.isConnected) close(); });

  function load() {
    if (!data) {
      data = Promise.all([
        fetch("/static/hilfe/uebungen.json").then((r) => r.json()),
        fetch("/static/hilfe/audio/manifest.json").then((r) => r.json()).catch(() => ({})),
      ]).then(([texte, manifest]) => ({ texte, manifest }))
        .catch((err) => { data = null; throw err; });
    }
    return data;
  }

  function close() {
    if (audio) audio.pause();
    if (panel) panel.remove();
    if (openBtn) openBtn.classList.remove("active");
    watch.disconnect();
    panel = null;
    openBtn = null;
  }

  function place(btn) {
    const r = btn.getBoundingClientRect();
    const width = Math.min(420, window.innerWidth - 24);
    panel.style.width = `${width}px`;
    panel.style.top = `${Math.round(r.bottom + 8)}px`;
    panel.style.left = `${Math.round(Math.max(12, Math.min(r.right - width, window.innerWidth - width - 12)))}px`;
  }

  function setPlaying(on) {
    const play = panel && panel.querySelector('[data-help="play"]');
    if (!play) return;
    play.classList.toggle("active", on);
    play.title = on ? "Anhalten" : "Vorlesen";
    play.setAttribute("aria-label", play.title);
  }

  function playFrom(start) {
    if (!audio) return;
    if (start) audio.currentTime = 0;
    const p = audio.play();
    if (p && p.catch) p.catch(() => setPlaying(false));  // Safari ohne vorheriges Antippen: einfach stumm
  }

  async function open(btn) {
    const typ = btn.dataset.typ, stufe = btn.dataset.stufe;
    let help;
    try {
      help = await load();
    } catch (err) {
      console.warn("Anleitung nicht geladen:", err);
      return;
    }
    const text = (help.texte[typ] || {})[stufe];
    if (!text) return;
    close();
    openBtn = btn;
    btn.classList.add("active");
    panel = document.createElement("div");
    panel.className = "px-help";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Anleitung");
    const file = (help.manifest[`${typ}_${stufe}`] || {}).datei;
    panel.innerHTML = `
      <div class="px-help-head">
        ${icon("Hilfe", "px-help-icon")}
        <strong>${esc(btn.dataset.titel || "")}</strong>
        ${file ? `<button type="button" class="practice-icon-btn" data-help="play" title="Vorlesen" aria-label="Vorlesen">${icon("Lautsprecher")}</button>` : ""}
        <button type="button" class="practice-icon-btn" data-help="close" title="Schließen" aria-label="Schließen">${icon("Schließen")}</button>
      </div>
      <p>${esc(text)}</p>`;
    document.body.appendChild(panel);
    place(btn);
    watch.observe(document.body, { childList: true, subtree: true });
    if (file) {
      if (!audio) {
        audio = new Audio();
        audio.addEventListener("playing", () => setPlaying(true));
        audio.addEventListener("pause", () => setPlaying(false));
        audio.addEventListener("ended", () => setPlaying(false));
      }
      audio.src = `/static/hilfe/audio/${file}`;
      playFrom(true);
    }
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-practice-help]");
    if (btn) {
      e.preventDefault();
      if (btn === openBtn) return close();
      open(btn);
      return;
    }
    if (!panel) return;
    const inside = e.target.closest(".px-help");
    if (!inside) return close();
    const action = e.target.closest("[data-help]")?.dataset.help;
    if (action === "close") close();
    if (action === "play") {
      if (audio && !audio.paused) audio.pause();
      else playFrom(audio && (audio.ended || audio.currentTime === 0));
    }
  });
  window.addEventListener("resize", () => { if (panel && openBtn) place(openBtn); });
  // Anderer Tab: Anleitung zu
  document.querySelectorAll(".nav-tab").forEach((tab) => tab.addEventListener("click", close));

  window.closePracticeHelp = close;
})();
