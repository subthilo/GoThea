// GoThea Frontend Application Logic (Milestone 1)

let currentProfile = null;
let currentSubjects = [];

// DOM Elements
const statusBadge = document.getElementById("status-badge");
const statusText = document.getElementById("status-text");
const badgeGrade = document.getElementById("badge-grade");
const userGreeting = document.getElementById("user-greeting");
const userSubtitle = document.getElementById("user-subtitle");
const statSubjectsCount = document.getElementById("stat-subjects-count");
const statTopicsCount = document.getElementById("stat-topics-count");
const dashboardSubjectsGrid = document.getElementById("dashboard-subjects-grid");
const subjectsDetailedList = document.getElementById("subjects-detailed-list");

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ============================================================================
// Eltern-Modus & Rechte-Verwaltung (Thea-Modus vs. Eltern-Modus)
// ============================================================================
const PARENT_TOKEN_STORAGE_KEY = "gothea_parent_token";
const PARENT_EXPIRES_STORAGE_KEY = "gothea_parent_expires_at";

let isParentActive = false;
let isDefaultParentPin = false;

function getParentToken() {
  const token = sessionStorage.getItem(PARENT_TOKEN_STORAGE_KEY);
  const exp = parseInt(sessionStorage.getItem(PARENT_EXPIRES_STORAGE_KEY) || "0", 10);
  if (!token) return null;
  if (exp && exp < Math.floor(Date.now() / 1000)) {
    clearParentToken();
    return null;
  }
  return token;
}

function setParentToken(token, expiresAt) {
  if (token) {
    sessionStorage.setItem(PARENT_TOKEN_STORAGE_KEY, token);
    if (expiresAt) {
      sessionStorage.setItem(PARENT_EXPIRES_STORAGE_KEY, String(expiresAt));
    }
  } else {
    clearParentToken();
  }
}

function clearParentToken() {
  sessionStorage.removeItem(PARENT_TOKEN_STORAGE_KEY);
  sessionStorage.removeItem(PARENT_EXPIRES_STORAGE_KEY);
}

// Globaler Fetch-Interceptor für automatische Token-Übermittlung & 403-Handling
const nativeFetch = window.fetch.bind(window);
window.fetch = async function (url, options = {}) {
  const token = getParentToken();
  if (token) {
    options = options || {};
    if (options.headers instanceof Headers) {
      if (!options.headers.has("X-Parent-Token")) {
        options.headers.set("X-Parent-Token", token);
      }
    } else if (Array.isArray(options.headers)) {
      options.headers.push(["X-Parent-Token", token]);
    } else {
      options.headers = Object.assign({}, options.headers, { "X-Parent-Token": token });
    }
  }

  const response = await nativeFetch(url, options);

  if (response.status === 403) {
    try {
      const clone = response.clone();
      const data = await clone.json();
      if (data && data.detail && typeof data.detail === "string" && data.detail.includes("Eltern-Modus")) {
        openParentPinModal("Für diese Aktion ist der Eltern-Modus erforderlich.");
      }
    } catch (_) {}
  }

  return response;
};

// UI-Synchronisation
function updateParentModeUI(active, isDefault = isDefaultParentPin) {
  isParentActive = Boolean(active);
  isDefaultParentPin = Boolean(isDefault);

  // Body classes
  document.body.classList.toggle("parent-mode-active", isParentActive);
  document.body.classList.toggle("thea-mode-active", !isParentActive);

  // Header Pill
  const pillBtn = document.getElementById("btn-parent-toggle");
  const pillIcon = document.getElementById("parent-pill-icon");
  const pillText = document.getElementById("parent-pill-text");

  if (pillBtn && pillIcon && pillText) {
    if (isParentActive) {
      pillBtn.classList.add("is-parent-active");
      pillIcon.innerHTML = '<img src="/static/Icons/Erwachsener.svg" class="pill-svg-icon" alt="Eltern-Modus">';
      pillText.textContent = "Eltern-Modus (Aktiv)";
      pillBtn.title = "Klicken, um den Eltern-Modus zu sperren (zurück zu Thea)";
    } else {
      pillBtn.classList.remove("is-parent-active");
      pillIcon.innerHTML = '<img src="/static/Icons/Kind.svg" class="pill-svg-icon" alt="Thea-Modus">';
      pillText.textContent = "Thea-Modus";
      pillBtn.title = "Klicken, um Eltern-PIN einzugeben (Einstellungen & Prüfungen freischalten)";
    }
  }

  // Profile Card
  const profBadge = document.getElementById("prof-parent-badge");
  const secLocked = document.getElementById("parent-security-locked");
  const secUnlocked = document.getElementById("parent-security-unlocked");
  const defPinWarn = document.getElementById("parent-default-pin-warn");
  const defPinHint = document.getElementById("parent-pin-default-hint");

  if (profBadge) {
    profBadge.textContent = isParentActive ? "Eltern-Modus aktiv" : "Thea-Modus aktiv";
  }
  if (secLocked) secLocked.style.display = isParentActive ? "none" : "block";
  if (secUnlocked) secUnlocked.style.display = isParentActive ? "block" : "none";
  if (defPinWarn) defPinWarn.style.display = (isParentActive && isDefaultParentPin) ? "block" : "none";
  if (defPinHint) defPinHint.style.display = isDefaultParentPin ? "block" : "none";

  // Formular-Sperre im Profil für Thea
  const profInputs = document.querySelectorAll("#tab-profile input, #tab-profile select");
  profInputs.forEach((el) => {
    if (el.id.startsWith("input-current-pin") || el.id.startsWith("input-new-pin")) return;
    el.disabled = !isParentActive;
  });

  if (currentDetailSubjectId) {
    loadSubjectScores(currentDetailSubjectId);
  }
}

async function checkParentAuthStatus() {
  try {
    const res = await nativeFetch("/api/v1/auth/parent/status", {
      headers: getParentToken() ? { "X-Parent-Token": getParentToken() } : {}
    });
    if (res.ok) {
      const data = await res.json();
      updateParentModeUI(data.is_parent, data.is_default_pin);
    }
  } catch (err) {
    console.warn("Konnte Eltern-Status nicht abrufen:", err);
  }
}

// PIN Modal Öffnen / Schließen
function openParentPinModal(customHint = "") {
  const modal = document.getElementById("modal-parent-pin");
  const pinInput = document.getElementById("input-parent-pin");
  const errorBox = document.getElementById("parent-pin-error");
  if (!modal) return;

  if (errorBox) {
    if (customHint) {
      errorBox.textContent = customHint;
      errorBox.style.display = "block";
      errorBox.style.background = "rgba(99, 102, 241, 0.12)";
      errorBox.style.color = "var(--accent-light)";
      errorBox.style.borderColor = "rgba(99, 102, 241, 0.35)";
    } else {
      errorBox.style.display = "none";
    }
  }

  if (pinInput) {
    pinInput.value = "";
    pinInput.type = "password";
  }

  const eyeBtn = document.getElementById("btn-toggle-pin-visibility");
  if (eyeBtn) {
    eyeBtn.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
  }

  modal.style.display = "flex";
  setTimeout(() => pinInput && pinInput.focus(), 80);
}

function closeParentPinModal() {
  const modal = document.getElementById("modal-parent-pin");
  if (modal) modal.style.display = "none";
}

// Entsperren via PIN
async function submitParentPin() {
  const pinInput = document.getElementById("input-parent-pin");
  const errorBox = document.getElementById("parent-pin-error");
  const pin = (pinInput ? pinInput.value : "").trim();

  if (!pin) {
    if (errorBox) {
      errorBox.textContent = "Bitte gib eine PIN ein.";
      errorBox.style.display = "block";
      errorBox.style.background = "rgba(239, 68, 68, 0.12)";
      errorBox.style.color = "#f87171";
      errorBox.style.borderColor = "rgba(239, 68, 68, 0.35)";
    }
    return;
  }

  try {
    const res = await nativeFetch("/api/v1/auth/parent/unlock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin })
    });

    if (res.ok) {
      const data = await res.json();
      setParentToken(data.token, data.expires_at);
      updateParentModeUI(true, data.is_default_pin);
      closeParentPinModal();
    } else {
      const errData = await res.json().catch(() => ({}));
      const msg = errData.detail || "Falsche PIN. Bitte erneut versuchen.";
      if (errorBox) {
        errorBox.textContent = msg;
        errorBox.style.display = "block";
        errorBox.style.background = "rgba(239, 68, 68, 0.12)";
        errorBox.style.color = "#f87171";
        errorBox.style.borderColor = "rgba(239, 68, 68, 0.35)";
      }
      if (pinInput) {
        pinInput.value = "";
        pinInput.focus();
      }
    }
  } catch (err) {
    if (errorBox) {
      errorBox.textContent = "Netzwerkfehler beim Entsperren.";
      errorBox.style.display = "block";
    }
  }
}

// Sofort sperren
function lockParentMode() {
  clearParentToken();
  updateParentModeUI(false);
}

// PIN ändern
async function handleParentPinChange() {
  const curInput = document.getElementById("input-current-pin");
  const newInput = document.getElementById("input-new-pin");
  const confInput = document.getElementById("input-new-pin-confirm");
  const msgBox = document.getElementById("parent-pin-change-msg");

  const currentPin = (curInput ? curInput.value : "").trim();
  const newPin = (newInput ? newInput.value : "").trim();
  const confirmPin = (confInput ? confInput.value : "").trim();

  if (!currentPin || !newPin) {
    if (msgBox) {
      msgBox.textContent = "❌ Bitte alle Felder ausfüllen.";
      msgBox.style.color = "var(--warning)";
    }
    return;
  }

  if (newPin !== confirmPin) {
    if (msgBox) {
      msgBox.textContent = "❌ Die neue PIN stimmt nicht mit der Bestätigung überein.";
      msgBox.style.color = "var(--warning)";
    }
    return;
  }

  if (!/^\d{4,8}$/.test(newPin)) {
    if (msgBox) {
      msgBox.textContent = "❌ Die PIN muss aus 4 bis 8 Ziffern bestehen.";
      msgBox.style.color = "var(--warning)";
    }
    return;
  }

  try {
    const res = await fetch("/api/v1/auth/parent/change-pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_pin: currentPin, new_pin: newPin })
    });

    if (res.ok) {
      const data = await res.json();
      setParentToken(data.token, data.expires_at);
      updateParentModeUI(true, false);
      if (curInput) curInput.value = "";
      if (newInput) newInput.value = "";
      if (confInput) confInput.value = "";
      if (msgBox) {
        msgBox.textContent = "✅ PIN erfolgreich geändert! Die neue PIN ist ab sofort aktiv.";
        msgBox.style.color = "var(--success)";
        setTimeout(() => { if (msgBox) msgBox.textContent = ""; }, 4000);
      }
    } else {
      const errData = await res.json().catch(() => ({}));
      if (msgBox) {
        msgBox.textContent = `❌ ${errData.detail || "Fehler beim Ändern der PIN."}`;
        msgBox.style.color = "var(--warning)";
      }
    }
  } catch (err) {
    if (msgBox) {
      msgBox.textContent = "❌ Netzwerkfehler.";
      msgBox.style.color = "var(--warning)";
    }
  }
}

// Event Listeners registrieren
function setupParentModeEvents() {
  const toggleBtn = document.getElementById("btn-parent-toggle");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      if (isParentActive) {
        lockParentMode();
      } else {
        openParentPinModal();
      }
    });
  }

  const profUnlockBtn = document.getElementById("btn-prof-unlock-parent");
  if (profUnlockBtn) {
    profUnlockBtn.addEventListener("click", () => openParentPinModal());
  }

  const profLockBtn = document.getElementById("btn-prof-lock-parent");
  if (profLockBtn) {
    profLockBtn.addEventListener("click", () => lockParentMode());
  }

  const closeBtn = document.getElementById("btn-close-parent-pin-modal");
  if (closeBtn) closeBtn.addEventListener("click", closeParentPinModal);

  const cancelBtn = document.getElementById("btn-cancel-parent-pin");
  if (cancelBtn) cancelBtn.addEventListener("click", closeParentPinModal);

  const submitBtn = document.getElementById("btn-submit-parent-pin");
  if (submitBtn) submitBtn.addEventListener("click", submitParentPin);

  const pinInput = document.getElementById("input-parent-pin");
  if (pinInput) {
    pinInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        submitParentPin();
      }
    });
  }

  const eyeBtn = document.getElementById("btn-toggle-pin-visibility");
  if (eyeBtn && pinInput) {
    eyeBtn.addEventListener("click", () => {
      const isPassword = pinInput.type === "password";
      pinInput.type = isPassword ? "text" : "password";
      eyeBtn.innerHTML = isPassword
        ? `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>`
        : `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
    });
  }

  const changeBtn = document.getElementById("btn-change-parent-pin");
  if (changeBtn) changeBtn.addEventListener("click", handleParentPinChange);
}

// ============================================================================
// Theme Manager (Farbschemata & Personalisierung)
// ============================================================================
const THEMES = {
  space: { name: "Weltall", icon: "🚀" },
  sunset: { name: "Sonnenuntergang", icon: "🌅" },
  nature: { name: "Zauberwald", icon: "🌲" },
  candy: { name: "Zauberwelt", icon: "🦄" }
};

let currentAppTheme = "space";

function applyTheme(themeKey) {
  if (!THEMES[themeKey]) themeKey = "space";
  currentAppTheme = themeKey;
  try {
    localStorage.setItem("gothea_theme", themeKey);
  } catch (e) {}

  document.body.setAttribute("data-theme", themeKey);
  document.documentElement.setAttribute("data-theme", themeKey);

  // Header pill aktualisieren
  const pillIcon = document.getElementById("theme-pill-icon");
  const pillText = document.getElementById("theme-pill-text");
  if (pillIcon) pillIcon.textContent = THEMES[themeKey].icon;
  if (pillText) pillText.textContent = THEMES[themeKey].name;

  // Active state in Dropdown & Profil
  document.querySelectorAll(".theme-opt-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.theme === themeKey);
  });
  document.querySelectorAll(".theme-card-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.theme === themeKey);
  });
}

function initThemeManager() {
  let saved = "space";
  try {
    saved = localStorage.getItem("gothea_theme") || "space";
  } catch (e) {}
  applyTheme(saved);

  const toggleBtn = document.getElementById("btn-theme-toggle");
  const dropdown = document.getElementById("theme-dropdown-menu");

  if (toggleBtn && dropdown) {
    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isVisible = dropdown.style.display === "flex";
      dropdown.style.display = isVisible ? "none" : "flex";
    });

    document.addEventListener("click", (e) => {
      if (!toggleBtn.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.style.display = "none";
      }
    });
  }

  // Clicks in Header Dropdown
  document.querySelectorAll(".theme-opt-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const th = btn.dataset.theme;
      if (th) {
        applyTheme(th);
        if (dropdown) dropdown.style.display = "none";
      }
    });
  });

  // Clicks in Profile Tab Cards
  document.querySelectorAll(".theme-card-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const th = btn.dataset.theme;
      if (th) applyTheme(th);
    });
  });
}

// ============================================================================
// Confetti Celebration (Erfolgs-Animation)
// ============================================================================
let confettiAnimId = null;

function fireCelebrationConfetti(durationMs = 2600) {
  const canvas = document.getElementById("confetti-canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  canvas.style.display = "block";

  if (confettiAnimId) {
    cancelAnimationFrame(confettiAnimId);
    confettiAnimId = null;
  }

  const colors = ["#6366f1", "#f43f5e", "#10b981", "#f59e0b", "#a855f7", "#ec4899", "#38bdf8", "#fbbf24"];
  const particles = [];
  const particleCount = 110;

  for (let i = 0; i < particleCount; i++) {
    particles.push({
      x: canvas.width * 0.5 + (Math.random() - 0.5) * 260,
      y: canvas.height * 0.45 + (Math.random() - 0.5) * 120,
      vx: (Math.random() - 0.5) * 14,
      vy: -(Math.random() * 12 + 6),
      size: Math.random() * 7 + 4,
      color: colors[Math.floor(Math.random() * colors.length)],
      rotation: Math.random() * 360,
      vRot: (Math.random() - 0.5) * 10,
      gravity: 0.38 + Math.random() * 0.15,
      shape: Math.random() > 0.35 ? "rect" : "star",
      opacity: 1
    });
  }

  const startTime = performance.now();

  function render(now) {
    const elapsed = now - startTime;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    let anyAlive = false;
    const progress = elapsed / durationMs;

    for (let p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      p.vy += p.gravity;
      p.vx *= 0.99;
      p.rotation += p.vRot;

      if (progress > 0.7) {
        p.opacity = Math.max(0, 1 - (progress - 0.7) / 0.3);
      }

      if (p.y < canvas.height && p.opacity > 0) {
        anyAlive = true;
        ctx.save();
        ctx.globalAlpha = p.opacity;
        ctx.translate(p.x, p.y);
        ctx.rotate((p.rotation * Math.PI) / 180);
        ctx.fillStyle = p.color;

        if (p.shape === "rect") {
          ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 1.5);
        } else {
          ctx.beginPath();
          ctx.arc(0, 0, p.size * 0.6, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }
    }

    if (elapsed < durationMs && anyAlive) {
      confettiAnimId = requestAnimationFrame(render);
    } else {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      canvas.style.display = "none";
      confettiAnimId = null;
    }
  }

  confettiAnimId = requestAnimationFrame(render);
}

window.fireCelebrationConfetti = fireCelebrationConfetti;

// ============================================================================
// Gamification Manager (Theas Fortschritte & Positives Scoring)
// ============================================================================
async function loadGamificationOverview() {
  try {
    const res = await fetch("/api/v1/exercises/gamification/overview");
    if (!res.ok) return;
    const data = await res.json();

    // Dashboard Chips
    const levelNumEl = document.getElementById("game-level-num");
    const levelTitleEl = document.getElementById("game-level-title");
    const levelIconEl = document.getElementById("game-level-icon");
    const streakDaysEl = document.getElementById("game-streak-days");
    const totalStarsEl = document.getElementById("game-total-stars");
    const totalXpEl = document.getElementById("game-total-xp");
    const todayCountEl = document.getElementById("stat-today-exercises");

    if (levelNumEl) levelNumEl.textContent = data.level?.level || 1;
    if (levelTitleEl) levelTitleEl.textContent = data.level?.title || "Wissens-Entdeckerin";
    if (levelIconEl) levelIconEl.innerHTML = `<img src="/static/Icons/Level.svg" class="capsule-svg-icon" alt="Level">`;

    if (streakDaysEl) streakDaysEl.textContent = data.streak_days || 0;
    if (totalStarsEl) totalStarsEl.textContent = data.total_stars || 0;
    if (totalXpEl) totalXpEl.textContent = data.total_xp || 0;
    if (todayCountEl) todayCountEl.textContent = data.today?.completed_count || 0;

    // Progress Bar
    const barTitleEl = document.getElementById("game-level-bar-title");
    const barXpEl = document.getElementById("game-level-bar-xp-text");
    const barFillEl = document.getElementById("game-level-bar-fill");

    if (data.level) {
      const lvl = data.level;
      if (barTitleEl) {
        barTitleEl.textContent = `Level ${lvl.level}: ${lvl.title}`;
      }
      if (barXpEl) {
        if (lvl.max_xp === null) {
          barXpEl.textContent = `Maximales Level erreicht! ✨ (${data.total_xp} XP)`;
        } else {
          barXpEl.textContent = `${lvl.current_level_xp} / ${lvl.needed_level_xp} XP bis Level ${lvl.level + 1}`;
        }
      }
      if (barFillEl) {
        barFillEl.style.width = `${Math.min(100, Math.max(0, lvl.progress_percent))}%`;
      }
    }

    // Profile Tab Trophies
    const profBadgeEl = document.getElementById("prof-level-badge");
    if (profBadgeEl && data.level) {
      profBadgeEl.innerHTML = `<img src="/static/Icons/Level.svg" class="badge-svg-icon" alt=""> Level ${data.level.level}`;
    }

    const gridEl = document.getElementById("prof-achievements-grid");
    if (gridEl && Array.isArray(data.achievements)) {
      const iconMap = {
        first_step: "/static/Icons/Tests.svg",
        star_collector: "/static/Icons/Stern.svg",
        streak_flame: "/static/Icons/Flamme.svg",
        perfect_run: "/static/Icons/Blitz.svg",
        knowledge_master: "/static/Icons/Level.svg"
      };
      gridEl.innerHTML = data.achievements.map((ach) => {
        const svgSrc = iconMap[ach.id] || "/static/Icons/Stern.svg";
        return `
        <div class="achievement-card ${ach.unlocked ? 'unlocked' : 'locked'}" title="${escapeHtml(ach.description)}">
          <span class="achievement-icon">
            <img src="${svgSrc}" class="achievement-svg-icon" alt="${escapeHtml(ach.title)}">
          </span>
          <div class="achievement-content">
            <strong>${escapeHtml(ach.title)}</strong>
            <p>${escapeHtml(ach.description)}</p>
          </div>
        </div>
      `;
      }).join("");
    }
  } catch (err) {
    console.warn("Fehler beim Laden des Gamification-Status:", err);
  }
}

function switchToTab(tabName) {
  const btn = document.querySelector(`.nav-tab[data-tab="${tabName}"]`);
  if (btn) btn.click();
}

// Tab Navigation
document.querySelectorAll(".nav-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));

    btn.classList.add("active");
    const target = document.getElementById(`tab-${btn.dataset.tab}`);
    if (target) target.classList.add("active");

    const readerView = document.getElementById("book-reader-view");
    if (btn.dataset.tab !== "books" || !readerView || readerView.style.display === "none") {
      document.body.classList.remove("reader-zen-mode");
    }

    if (btn.dataset.tab === "uploads") {
      checkInboxStatus();
      loadUploadsHistory();
    }
    if (btn.dataset.tab === "timetable") {
      document.documentElement.classList.add("timetable-zen-mode");
      document.body.classList.add("timetable-zen-mode");
      loadTimetable();
    } else {
      document.documentElement.classList.remove("timetable-zen-mode");
      document.body.classList.remove("timetable-zen-mode");
    }
    if (btn.dataset.tab === "whiteboard") {
      document.documentElement.classList.add("whiteboard-zen-mode");
      document.body.classList.add("whiteboard-zen-mode");
      window.dispatchEvent(new Event("resize"));
    } else {
      document.documentElement.classList.remove("whiteboard-zen-mode");
      document.body.classList.remove("whiteboard-zen-mode");
    }
    if (btn.dataset.tab === "books") {
      if (currentBooks.length === 0) {
        loadBooks();
      }
      setTimeout(syncBookAnnotationCanvasSize, 100);
    }
  });
});

// 1. Profil laden
async function loadProfile() {
  try {
    const res = await fetch("/api/v1/profile");
    if (res.ok) {
      currentProfile = await res.json();
      if (badgeGrade) badgeGrade.textContent = `${currentProfile.grade_level}. Klasse`;
      if (userGreeting) userGreeting.textContent = `Hallo, ${currentProfile.name}! 👋`;
      if (userSubtitle) userSubtitle.textContent = `${currentProfile.grade_level}. Klasse ${currentProfile.school_type} • Land ${currentProfile.federal_state} (Niveaustufe E)`;

      // Profil-Formular initialisieren
      const profNameInput = document.getElementById("prof-name");
      const profGradeInput = document.getElementById("prof-grade");
      const profSchoolInput = document.getElementById("prof-school");
      if (profNameInput) profNameInput.value = currentProfile.name;
      if (profGradeInput) profGradeInput.value = currentProfile.grade_level;
      if (profSchoolInput) profSchoolInput.value = currentProfile.school_type;
    }
  } catch (err) {
    console.error("Fehler beim Laden des Profils:", err);
  }
}

// 2. Fächer und Themen laden
async function loadTaxonomy() {
  try {
    const [subRes, topRes] = await Promise.all([
      fetch("/api/v1/taxonomy/subjects"),
      fetch("/api/v1/taxonomy/topics")
    ]);

    if (subRes.ok && topRes.ok) {
      currentSubjects = await subRes.json();
      const allTopics = await topRes.json();
      allTopicsCache = allTopics;

      if (statSubjectsCount) statSubjectsCount.textContent = currentSubjects.length;
      if (statTopicsCount) statTopicsCount.textContent = allTopics.length;

      // Group topics by subject
      const topicsBySubject = {};
      allTopics.forEach((t) => {
        if (!topicsBySubject[t.subject_id]) topicsBySubject[t.subject_id] = [];
        topicsBySubject[t.subject_id].push(t);
      });

      renderDashboardSubjects(currentSubjects, topicsBySubject);
      if (currentDetailSubjectId) {
        openSubjectDetail(currentDetailSubjectId);
      }
    }
  } catch (err) {
    console.error("Fehler beim Laden der Fächer:", err);
  }
}

let cachedSubjects = [];
let cachedTopicsMap = {};
let currentDetailSubjectId = null;
let currentSubjectMaterials = [];
let activeSubjectKindFilter = "all";

// ==========================================================================
// Icon Resolver Helpers (Konzept 1: 55 Vektorgrafiken)
// ==========================================================================
function getSubjectIconUrl(subjectNameOrCode) {
  if (!subjectNameOrCode) return "/static/Icons/Dokumente.svg";
  const norm = String(subjectNameOrCode).toLowerCase().trim();
  if (norm.includes("math")) return "/static/Icons/Mathematik.svg";
  if (norm.includes("deutsch")) return "/static/Icons/Deutsch.svg";
  if (norm.includes("eng")) return "/static/Icons/Englisch.svg";
  if (norm.includes("franz") || norm.includes("franç")) return "/static/Icons/Französisch.svg";
  if (norm.includes("bio")) return "/static/Icons/Biologie.svg";
  if (norm.includes("phys")) return "/static/Icons/Physik.svg";
  if (norm.includes("chem")) return "/static/Icons/Chemie.svg";
  if (norm.includes("gesch")) return "/static/Icons/Geschichte.svg";
  if (norm.includes("geo")) return "/static/Icons/Geografie.svg";
  if (norm.includes("politi") || norm === "pb") return "/static/Icons/Politische Bildung.svg";
  if (norm.includes("wat") || norm.includes("wirtsch")) return "/static/Icons/WAT.svg";
  if (norm.includes("ler")) return "/static/Icons/LER.svg";
  if (norm.includes("relig")) return "/static/Icons/Religion.svg";
  if (norm.includes("mus")) return "/static/Icons/Musik.svg";
  if (norm.includes("sport") || norm.includes("*sp")) return "/static/Icons/Sport.svg";
  if (norm.includes("kunst")) return "/static/Icons/Kunst.svg";
  if (norm.includes("info")) return "/static/Icons/Informatik.svg";
  if (norm.includes("mittag") || norm.includes("mensa")) return "/static/Icons/Mittagspause.svg";
  if (norm.includes("pause")) return "/static/Icons/Pause.svg";
  if (norm.includes("frei")) return "/static/Icons/Freistunde.svg";
  return "/static/Icons/Bücher.svg";
}

function getDocumentIconUrl(docKind) {
  if (!docKind) return "/static/Icons/Dokumente.svg";
  const norm = String(docKind).toLowerCase().trim();
  if (norm.includes("blatt") || norm.includes("arbeitsblatt")) return "/static/Icons/Arbeitsblätter.svg";
  if (norm.includes("heft") || norm.includes("arbeitsheft")) return "/static/Icons/Arbeitshefte.svg";
  if (norm.includes("mitschrift") || norm.includes("notiz")) return "/static/Icons/Mitschriften.svg";
  if (norm.includes("übung") || norm.includes("uebung")) return "/static/Icons/Übungen.svg";
  if (norm.includes("test")) return "/static/Icons/Tests.svg";
  if (norm.includes("arbeit") || norm.includes("klausur")) return "/static/Icons/Arbeiten.svg";
  if (norm.includes("berichtigung")) return "/static/Icons/Berichtigungen.svg";
  if (norm.includes("hausaufgabe")) return "/static/Icons/Hausaufgaben.svg";
  if (norm.includes("buch")) return "/static/Icons/Bücher.svg";
  return "/static/Icons/Dokumente.svg";
}

// Render Dashboard Cards (klickbar zur Fach-Detailseite mit Vektor-Icons)
function renderDashboardSubjects(subjects, topicsMap) {
  cachedSubjects = subjects;
  cachedTopicsMap = topicsMap;
  if (!dashboardSubjectsGrid) return;
  dashboardSubjectsGrid.innerHTML = "";

  subjects.forEach((s) => {
    const card = document.createElement("div");
    card.className = "subject-card subject-app-tile";
    const subColor = s.color_code || "#2563eb";
    card.style.setProperty("--tile-color", subColor);
    card.dataset.subjectId = s.id;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("title", `${s.name} öffnen`);

    card.innerHTML = `
      <div class="subject-tile-icon-wrap" style="background: ${subColor}20; border-color: ${subColor}45;">
        <img src="${getSubjectIconUrl(s.name)}" class="subject-tile-svg" alt="${escapeHtml(s.name)}">
      </div>
      <div class="subject-tile-name">${escapeHtml(s.name)}</div>
    `;

    const handleOpen = () => {
      openSubjectDetail(s.id);
    };

    card.addEventListener("click", handleOpen);
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleOpen();
      }
    });

    dashboardSubjectsGrid.appendChild(card);
  });
}

let subjectDetailSourceTab = "dashboard";

function openSubjectDetail(subjectId, sourceTab = "dashboard") {
  subjectDetailSourceTab = sourceTab;
  currentDetailSubjectId = subjectId;
  const s = cachedSubjects.find((sub) => sub.id === subjectId) || {
    id: subjectId,
    name: "Schulfach",
    icon: "📚",
    color_code: "#6366f1",
    min_grade: 7,
    max_grade: 7
  };
  window.currentDetailSubjectId = subjectId;
  window.currentSubject = s;
  window.cachedSubjects = cachedSubjects;
  window.openSubjectDetail = openSubjectDetail;

  const breadcrumb = document.getElementById("subject-detail-breadcrumb");
  const sourceName = sourceTab === "timetable" ? "Stundenplan" : "Übersicht";
  if (breadcrumb) breadcrumb.textContent = `${sourceName} / ${s.name}`;

  const btnBack = document.getElementById("btn-back-to-dashboard");
  if (btnBack) {
    btnBack.innerHTML = `<span>← Zurück ${sourceTab === "timetable" ? "zum Stundenplan" : "zur Übersicht"}</span>`;
  }

  const heroCard = document.getElementById("subject-hero-card");
  if (heroCard) {
    heroCard.style.borderLeft = `6px solid ${s.color_code}`;
    heroCard.style.boxShadow = `0 10px 32px rgba(0, 0, 0, 0.35), 0 0 24px ${s.color_code}15`;
  }

  const iconEl = document.getElementById("subject-detail-icon");
  if (iconEl) {
    iconEl.innerHTML = `<img src="${getSubjectIconUrl(s.name)}" class="subject-hero-svg" alt="${escapeHtml(s.name)}">`;
    iconEl.style.background = `${s.color_code}22`;
    iconEl.style.borderColor = `${s.color_code}44`;
  }

  const nameEl = document.getElementById("subject-detail-name");
  if (nameEl) nameEl.textContent = s.name;

  const gradeEl = document.getElementById("subject-detail-grade");
  if (gradeEl) gradeEl.textContent = `Klasse ${s.min_grade}–${s.max_grade}`;

  const btnWb = document.getElementById("btn-subject-open-wb");
  if (btnWb) {
    btnWb.onclick = () => {
      switchToTab("whiteboard");
      const subSel = document.getElementById("wb-subject-select");
      if (subSel) {
        subSel.value = s.id;
        subSel.dispatchEvent(new Event("change"));
      }
    };
  }

  const btnExercise = document.getElementById("btn-subject-start-exercise");
  if (btnExercise) {
    btnExercise.dataset.subjectId = s.id;
    btnExercise.dataset.subjectName = s.name;
    btnExercise.onclick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (typeof window.openClozeTrainer === "function") {
        window.openClozeTrainer({
          subjectId: s.id,
          subjectName: s.name,
          sourceMaterialTitle: null
        });
      }
    };
  }

  const btnUpload = document.getElementById("btn-subject-upload-doc");
  if (btnUpload) {
    btnUpload.onclick = () => {
      openMaterialUploadModal(s.id);
    };
  }

  const handleKeyTrigger = (el) => {
    if (el) {
      el.onkeydown = (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          el.click();
        }
      };
    }
  };
  handleKeyTrigger(btnWb);
  handleKeyTrigger(btnExercise);
  handleKeyTrigger(btnUpload);

  const topics = cachedTopicsMap[s.id] || [];
  const topicsCount = document.getElementById("subject-topics-count");
  if (topicsCount) topicsCount.textContent = `${topics.length} Thema${topics.length === 1 ? "" : "n"}`;

  const topicsContainer = document.getElementById("subject-detail-topics");
  if (topicsContainer) {
    if (topics.length === 0) {
      topicsContainer.innerHTML = `<span style="color: var(--text-muted); font-size: 0.85rem;">Keine spezifischen Themen für dieses Fach hinterlegt.</span>`;
    } else {
      topicsContainer.innerHTML = topics.map((t) => `
        <div class="subject-topic-chip">
          <span>${escapeHtml(t.name)}</span>
          ${t.rlp_level_code ? `<span class="topic-rlp-tag">RLP ${t.rlp_level_code}</span>` : ""}
        </div>
      `).join("");
    }
  }

  // Filter-Pills zurücksetzen
  activeSubjectKindFilter = "all";
  const pills = document.querySelectorAll("#subject-materials-filter-bar .filter-pill");
  pills.forEach((p) => {
    p.classList.toggle("active", p.dataset.kind === "all");
  });

  loadSubjectMaterials(subjectId);
  initSubjectScoresVisibility();
  loadSubjectScores(subjectId);

  // View aktivieren
  document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".nav-tab").forEach((b) => b.classList.remove("active"));
  const tabEl = document.getElementById("tab-subject-detail");
  if (tabEl) tabEl.classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function initSubjectScoresVisibility() {
  const btnToggle = document.getElementById("btn-toggle-subject-scores-visibility");
  const bodyEl = document.getElementById("subject-scores-body");
  const hiddenEl = document.getElementById("subject-scores-hidden-state");
  const iconEl = document.getElementById("btn-toggle-subject-scores-icon");
  const textEl = document.getElementById("btn-toggle-subject-scores-text");

  let isHidden = localStorage.getItem("gothea_hide_subject_scores") === "true";

  function applyVisibility(hidden) {
    if (bodyEl) bodyEl.style.display = hidden ? "none" : "block";
    if (hiddenEl) hiddenEl.style.display = hidden ? "block" : "none";
    if (iconEl) iconEl.textContent = hidden ? "👁️" : "🙈";
    if (textEl) textEl.textContent = hidden ? "Scores einblenden" : "Scores ausblenden";
  }

  applyVisibility(isHidden);

  if (btnToggle) {
    btnToggle.onclick = () => {
      isHidden = !isHidden;
      localStorage.setItem("gothea_hide_subject_scores", isHidden ? "true" : "false");
      applyVisibility(isHidden);
    };
  }
}

// Bei Abschluss einer Übung im Hintergrund Fach-Scores neu laden & Gamification aktualisieren
window.addEventListener("gothea:exercise-completed", (e) => {
  if (currentDetailSubjectId) {
    loadSubjectScores(currentDetailSubjectId);
  }
  loadGamificationOverview();
  fireCelebrationConfetti();
});

async function loadSubjectScores(subjectId) {
  const container = document.getElementById("subject-scores-methods-grid");
  const badgeEl = document.getElementById("subject-adaptive-level-badge");
  const hintTextEl = document.getElementById("subject-scores-adaptive-hint-text");
  if (!container) return;

  container.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 18px; color: var(--text-muted); font-size: 0.85rem;">Lade Trainingsstand...</div>`;

  try {
    const res = await fetch(`/api/v1/exercises/scores/${encodeURIComponent(subjectId)}`);
    if (!res.ok) {
      container.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); font-size: 0.85rem;">Keine Trainingsdaten verfügbar.</div>`;
      return;
    }
    const data = await res.json();

    if (badgeEl) {
      if (isParentActive) {
        badgeEl.textContent = data.difficulty_label || "Stufe 2 (Mittel) 🎯";
        badgeEl.className = `badge-adaptive-level level-${data.difficulty_level_code || 2}`;
      } else {
        const badgeTitle = data.positive_summary?.badge || "Gymnasial-Profi 🎯";
        badgeEl.textContent = `${badgeTitle} (${data.subject_stars || 0} ⭐)`;
        badgeEl.className = `badge-adaptive-level level-2`;
      }
    }

    if (hintTextEl) {
      if (isParentActive) {
        if (data.difficulty_level_code === 1) {
          hintTextEl.textContent = "Sanfter Aufbau-Modus aktiv: Luna wählt leichtere Aufgaben, damit Thea die Grundlagen festigt und fast alles richtig hat.";
        } else if (data.difficulty_level_code === 3) {
          hintTextEl.textContent = "Spitzen-Modus aktiv: Thea löst Übungen mit Bravour! Luna stellt anspruchsvolle Vertiefungsaufgaben bereit.";
        } else {
          hintTextEl.textContent = "Ausgewogenes Gymnasial-Niveau: Luna passt den Schwierigkeitsgrad nach jeder Übung an Theas Fortschritt an.";
        }
      } else {
        hintTextEl.textContent = data.positive_summary?.encouragement || "Toller Lernfortschritt! Mit jeder Übung sammelst du wertvolle Wissens-Sterne und XP.";
      }
    }

    const methods = data.methods || {};
    const methodKeys = Object.keys(methods);

    if (methodKeys.length === 0) {
      container.innerHTML = `
        <div class="subject-score-empty" style="grid-column: 1 / -1; text-align: center; padding: 24px; color: var(--text-muted);">
          <span>Noch keine Übungen für dieses Fach absolviert. Starte oben eine Lückentext-Übung!</span>
        </div>
      `;
      return;
    }

    container.innerHTML = methodKeys.map((k) => {
      const m = methods[k];
      const hasData = m.completed_count > 0;
      const scorePct = hasData ? Math.round(m.average_score) : 0;
      const levelCode = m.difficulty_level_code || 2;

      if (!isParentActive) {
        // THEA-MODUS: Positives Gamified Scoring, niemals Fehlerprozente oder rote Warnfarben
        const starsCount = hasData ? Math.min(3, Math.max(1, Math.round((scorePct / 100) * 3))) : 0;
        const starsDisplay = hasData ? "⭐".repeat(starsCount) : "Noch keine Sterne";
        return `
          <div class="method-score-card">
            <div class="method-score-header">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="method-score-icon">${m.icon || "📝"}</span>
                <strong class="method-score-name">${escapeHtml(m.name)}</strong>
              </div>
              <span class="method-difficulty-pill" style="background: rgba(250, 204, 21, 0.15); color: #facc15; border-color: rgba(250, 204, 21, 0.35);">
                ${hasData ? starsDisplay : "Bereit zum Üben 🌱"}
              </span>
            </div>

            <div class="method-score-metrics">
              <div class="method-score-main">
                <span class="method-score-percent" style="color: #facc15;">${hasData ? `+${m.completed_count * 10} XP` : "–"}</span>
                <span class="method-score-sublabel">${hasData ? "Punkte gesammelt" : "Neu"}</span>
              </div>
              <div class="method-score-details">
                <div><strong>${m.completed_count}</strong> Übung${m.completed_count === 1 ? "" : "en"} gemeistert</div>
                <div>${hasData ? "Toller Einsatz! Weiter so 👍" : "Starte deine erste Runde!"}</div>
              </div>
            </div>

            <div class="method-score-bar-wrap">
              <div class="method-score-bar bar-high" style="width: ${hasData ? Math.max(40, scorePct) : 0}%; background: linear-gradient(90deg, #10b981, #facc15);"></div>
            </div>
          </div>
        `;
      }

      // ELTERN-MODUS: Analytische Detailübersicht mit Quoten
      return `
        <div class="method-score-card">
          <div class="method-score-header">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="method-score-icon">${m.icon || "📝"}</span>
              <strong class="method-score-name">${escapeHtml(m.name)}</strong>
            </div>
            <span class="method-difficulty-pill level-${levelCode}">
              ${escapeHtml(m.difficulty_label)}
            </span>
          </div>

          <div class="method-score-metrics">
            <div class="method-score-main">
              <span class="method-score-percent">${hasData ? `${scorePct}%` : "–"}</span>
              <span class="method-score-sublabel">${hasData ? "Erfolgsquote" : "Noch nicht geübt"}</span>
            </div>
            <div class="method-score-details">
              <div><strong>${m.completed_count}</strong> Übung${m.completed_count === 1 ? "" : "en"} absolviert</div>
              ${m.recent_score !== null && m.recent_score !== undefined ? `<div>Zuletzt: <strong>${Math.round(m.recent_score)}%</strong></div>` : `<div>Noch keine Daten</div>`}
            </div>
          </div>

          <div class="method-score-bar-wrap">
            <div class="method-score-bar ${scorePct >= 80 ? "bar-high" : (scorePct >= 60 ? "bar-mid" : "bar-low")}" style="width: ${hasData ? scorePct : 0}%;"></div>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.warn("Fehler beim Laden der Fach-Scores:", err);
    container.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); font-size: 0.85rem;">Trainingsstand konnte nicht geladen werden.</div>`;
  }
}

async function loadSubjectMaterials(subjectId) {
  const grid = document.getElementById("subject-materials-grid");
  const countBadge = document.getElementById("subject-materials-count");
  if (!grid) return;

  grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 30px; color: var(--text-secondary);">Lade Materialien...</div>`;

  try {
    const res = await fetch(`/api/v1/materials?subject_id=${encodeURIComponent(subjectId)}`);
    if (res.ok) {
      currentSubjectMaterials = await res.json();
      if (countBadge) {
        countBadge.textContent = `${currentSubjectMaterials.length} Dokument${currentSubjectMaterials.length === 1 ? "" : "e"}`;
      }
      renderSubjectMaterialsList(currentSubjectMaterials);
    } else {
      grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--danger);">Fehler beim Laden der Materialien.</div>`;
    }
  } catch (err) {
    console.error("Fehler beim Laden der Fach-Materialien:", err);
    grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--danger);">Netzwerkfehler.</div>`;
  }
}

function renderSubjectMaterialsList(materials) {
  const grid = document.getElementById("subject-materials-grid");
  if (!grid) return;
  grid.innerHTML = "";

  const filtered = materials.filter((m) => {
    if (activeSubjectKindFilter === "all") return true;
    if (activeSubjectKindFilter === "Arbeitsblatt") return m.kind === "Arbeitsblatt";
    if (activeSubjectKindFilter === "Hefter") return (m.kind || "").includes("Heft");
    if (activeSubjectKindFilter === "Buch") return (m.kind || "").includes("Buch");
    if (activeSubjectKindFilter === "Test") {
      const k = m.kind || "";
      return k.includes("Test") || k.includes("Klassenarbeit") || k.includes("Übung") || k.includes("Klausur");
    }
    return true;
  });

  if (filtered.length === 0) {
    const filterName = activeSubjectKindFilter === "all" ? "" : ` in der Kategorie „${activeSubjectKindFilter}“`;
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 48px 16px; background: rgba(255, 255, 255, 0.02); border: 1px dashed var(--border-color); border-radius: 16px; color: var(--text-secondary);">
        <span style="font-size: 2.4rem; display: block; margin-bottom: 8px;">📭</span>
        <div style="font-weight: 700; color: var(--text-primary); font-size: 1.1rem; margin-bottom: 6px;">Keine Dokumente${filterName}</div>
        <p style="font-size: 0.88rem; max-width: 440px; margin: 0 auto 16px;">
          Lade Arbeitsblätter, Hefterseiten oder Schulbuchauszüge für dieses Fach hoch, um sie hier direkt zu öffnen und auf der Tafel zu bearbeiten.
        </p>
        <button class="btn-primary-sm" onclick="openMaterialUploadModal('${currentDetailSubjectId || ''}')">➕ Jetzt Dokument hochladen</button>
      </div>
    `;
    return;
  }

  filtered.forEach((m) => {
    const card = buildMaterialCard(m, () => {
      loadSubjectMaterials(currentDetailSubjectId);
      loadUploadsHistory();
    });
    grid.appendChild(card);
  });
}

function setupSubjectDetailEvents() {
  const btnBack = document.getElementById("btn-back-to-dashboard");
  if (btnBack) {
    btnBack.addEventListener("click", () => {
      switchToTab(subjectDetailSourceTab || "dashboard");
    });
  }

  const btnToggleTopics = document.getElementById("btn-toggle-subject-topics");
  if (btnToggleTopics) {
    btnToggleTopics.addEventListener("click", () => {
      const chips = document.getElementById("subject-detail-topics");
      const arrow = document.getElementById("subject-topics-arrow");
      if (!chips) return;
      const isHidden = chips.style.display === "none";
      chips.style.display = isHidden ? "flex" : "none";
      if (arrow) arrow.style.transform = isHidden ? "rotate(180deg)" : "rotate(0deg)";
    });
  }

  const subjectFilterPills = document.querySelectorAll("#subject-materials-filter-bar .filter-pill");
  subjectFilterPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      subjectFilterPills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      activeSubjectKindFilter = pill.dataset.kind || "all";
      renderSubjectMaterialsList(currentSubjectMaterials);
    });
  });
}

// 3. Profil Speichern Event
document.getElementById("btn-save-profile").addEventListener("click", async () => {
  const name = document.getElementById("prof-name").value;
  const grade_level = parseInt(document.getElementById("prof-grade").value, 10);
  const school_type = document.getElementById("prof-school").value;
  const feedback = document.getElementById("prof-feedback");

  try {
    const res = await fetch("/api/v1/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, grade_level, school_type })
    });

    if (res.ok) {
      feedback.textContent = "✅ Profil erfolgreich aktualisiert!";
      feedback.style.color = "var(--success)";
      await loadProfile();
      await loadTaxonomy();
      setTimeout(() => (feedback.textContent = ""), 3000);
    } else {
      feedback.textContent = "❌ Fehler beim Speichern";
      feedback.style.color = "var(--warning)";
    }
  } catch (err) {
    feedback.textContent = "❌ Netzwerkfehler";
    feedback.style.color = "var(--warning)";
  }
});

// 4. WebSocket Verbindung
function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    if (statusBadge) {
      statusBadge.classList.add("online");
      statusBadge.title = "Verbunden";
    }
    if (statusText) statusText.textContent = "Verbunden";
  };

  ws.onclose = () => {
    if (statusBadge) {
      statusBadge.classList.remove("online");
      statusBadge.title = "Verbindung getrennt";
    }
    if (statusText) statusText.textContent = "Verbindung getrennt";
    setTimeout(connectWebSocket, 3000);
  };
}

// 5. Environment & Staging Check
let currentEnvInfo = null;

async function checkEnvironment() {
  try {
    const res = await fetch("/api/v1/env");
    if (res.ok) {
      const data = await res.json();
      currentEnvInfo = data;
      const stagingBanner = document.getElementById("staging-banner");
      const btnSeedDummies = document.getElementById("btn-seed-dummies");
      if (data.is_staging) {
        stagingBanner.style.display = "block";
        if (btnSeedDummies) btnSeedDummies.style.display = "inline-block";
      } else {
        stagingBanner.style.display = "none";
        if (btnSeedDummies) btnSeedDummies.style.display = "none";
      }
      if (inboxEnvBadge) {
        inboxEnvBadge.textContent = data.is_staging ? "Finder: GoThea-Staging" : "Finder: GoThea-Prod";
      }
    }
  } catch (err) {
    console.error("Fehler beim Prüfen der Umgebung:", err);
  }
}

// 6. Lernplan & Countdown laden
async function loadPlan() {
  try {
    const res = await fetch("/api/v1/plan");
    if (!res.ok) return;
    const plan = await res.json();

    // 6.1 Heutige Aufgaben
    const todayTasksList = document.getElementById("planner-today-tasks");
    const todayMinutes = document.getElementById("planner-today-minutes");
    const todayTitle = document.getElementById("planner-today-title");

    todayTitle.textContent = `Heutige Lerneinheiten (${plan.today_plan.day_name})`;
    todayMinutes.textContent = `${plan.today_plan.total_minutes} Min. verbleibend`;

    todayTasksList.innerHTML = "";
    if (plan.today_plan.is_blocked) {
      todayTasksList.innerHTML = `
        <div class="empty-placeholder" style="padding: 24px;">
          <h3>🏖️ Heute ist Sperrtag!</h3>
          <p>${plan.today_plan.block_info || "Für heute sind keine Lerneinheiten geplant."}</p>
        </div>
      `;
    } else if (plan.today_plan.tasks.length === 0) {
      todayTasksList.innerHTML = `
        <div class="empty-placeholder" style="padding: 24px;">
          <h3>🎉 Alles im grünen Bereich!</h3>
          <p>Für heute stehen keine anstehenden Klassenarbeiten im Lernfenster an.</p>
        </div>
      `;
    } else {
      plan.today_plan.tasks.forEach((tsk) => {
        const card = document.createElement("div");
        card.className = `plan-task-card ${tsk.is_completed ? "completed" : ""}`;
        card.style.borderLeft = `5px solid ${tsk.subject_color}`;

        const phaseClass = `phase-p${tsk.phase_number}`;

        card.innerHTML = `
          <div class="task-left">
            <div class="task-subject-icon">${tsk.subject_icon}</div>
            <div class="task-meta">
              <div class="task-title">
                <span>${tsk.subject_name} – ${tsk.test_kind}</span>
                <span class="phase-pill ${phaseClass}">${tsk.phase_name}</span>
              </div>
              <div class="task-desc">${tsk.phase_description} ${tsk.test_note ? `• <em>${tsk.test_note}</em>` : ""}</div>
            </div>
          </div>
          <div class="task-right">
            <div class="task-time-pill">⏱️ ${tsk.target_minutes} Min.</div>
            <button class="btn-task-check" data-test-id="${tsk.test_id}" data-date="${plan.today_date}" data-completed="${tsk.is_completed}">
              ${tsk.is_completed ? "✓" : ""}
            </button>
          </div>
        `;

        card.querySelector(".btn-task-check").addEventListener("click", async (e) => {
          const btn = e.currentTarget;
          const isComp = btn.dataset.completed === "true";
          await toggleTask(btn.dataset.testId, btn.dataset.date, !isComp);
        });

        todayTasksList.appendChild(card);
      });
    }

    // 6.2 Wochen-Vorschau (Nächste 7 Tage)
    const weekTimeline = document.getElementById("planner-week-timeline");
    weekTimeline.innerHTML = "";
    plan.next_7_days.forEach((day, idx) => {
      const dayCard = document.createElement("div");
      dayCard.className = `timeline-day-card ${idx === 0 ? "today" : ""} ${day.is_blocked ? "blocked" : ""}`;

      let taskListHtml = "";
      if (day.is_blocked) {
        taskListHtml = `<span>🏖️ Sperrtag</span>`;
      } else if (day.tasks.length === 0) {
        taskListHtml = `<span>Frei</span>`;
      } else {
        taskListHtml = day.tasks.map((t) => `
          <div>${t.subject_icon} ${t.subject_name} (${t.target_minutes}m)</div>
        `).join("");
      }

      dayCard.innerHTML = `
        <div class="day-card-header">${day.day_name.split(",")[0]}</div>
        <div class="day-card-tasks">${taskListHtml}</div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 6px;">${day.total_minutes} Min.</div>
      `;
      weekTimeline.appendChild(dayCard);
    });

    // 6.3 Anstehende Prüfungen Grid
    const testsGrid = document.getElementById("planner-tests-grid");
    testsGrid.innerHTML = "";
    if (plan.upcoming_tests.length === 0) {
      testsGrid.innerHTML = `
        <div class="empty-placeholder" style="padding: 24px; grid-column: 1 / -1;">
          <p>Keine bevorstehenden Prüfungen eingetragen. Tippe oben auf „➕ Neue Prüfung“, um einen Countdown zu starten.</p>
        </div>
      `;
    } else {
      plan.upcoming_tests.forEach((t) => {
        const card = document.createElement("div");
        card.className = "test-card";
        card.style.borderLeft = `4px solid ${t.subject_color}`;

        // Datum und Tage berechnen
        const examDate = new Date(t.date);
        const todayD = new Date(plan.today_date);
        const diffDays = Math.round((examDate - todayD) / (1000 * 60 * 60 * 24));
        const badgeText = diffDays === 0 ? "Heute!" : (diffDays === 1 ? "Morgen" : `in ${diffDays} Tagen`);

        card.innerHTML = `
          <div class="test-card-top">
            <div class="test-card-title">${t.subject_icon} ${t.subject_name} – ${t.kind}</div>
            <span class="countdown-badge">${badgeText}</span>
          </div>
          <div class="test-note">${t.note || "Keine Notiz hinterlegt"}</div>
          <div class="test-card-footer">
            <span>📅 ${t.date}</span>
            <button class="btn-del-test parent-only" data-id="${t.id}">Löschen</button>
          </div>
        `;

        card.querySelector(".btn-del-test").addEventListener("click", async (e) => {
          if (confirm(`Möchtest du diese ${t.kind} wirklich löschen?`)) {
            await deleteTest(e.currentTarget.dataset.id);
          }
        });

        testsGrid.appendChild(card);
      });
    }

  } catch (err) {
    console.error("Fehler beim Laden des Plans:", err);
  }
}

// Task Toggle
async function toggleTask(testId, dateStr, completed) {
  try {
    await fetch("/api/v1/plan/complete-task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ test_id: testId, date: dateStr, completed })
    });
    await loadPlan();
  } catch (e) {
    console.error(e);
  }
}

// Prüfung löschen
async function deleteTest(testId) {
  try {
    const res = await fetch(`/api/v1/tests/${testId}`, { method: "DELETE" });
    if (res.ok) await loadPlan();
  } catch (e) {
    console.error(e);
  }
}

// Modal Handling
const modalTest = document.getElementById("modal-test");
const modalBlock = document.getElementById("modal-block");

document.getElementById("btn-open-test-modal").addEventListener("click", () => {
  // Fächer Dropdown füllen
  const sel = document.getElementById("input-test-subject");
  sel.innerHTML = currentSubjects.map((s) => `<option value="${s.id}">${s.icon} ${s.name}</option>`).join("");
  // Default Datum: in 7 Tagen
  const d = new Date();
  d.setDate(d.getDate() + 7);
  document.getElementById("input-test-date").value = d.toISOString().split("T")[0];
  modalTest.style.display = "flex";
});

document.getElementById("btn-close-test-modal").addEventListener("click", () => {
  modalTest.style.display = "none";
});

document.getElementById("btn-open-block-modal").addEventListener("click", () => {
  document.getElementById("input-block-date").value = new Date().toISOString().split("T")[0];
  modalBlock.style.display = "flex";
});

document.getElementById("btn-close-block-modal").addEventListener("click", () => {
  modalBlock.style.display = "none";
});

// Neue Prüfung speichern
document.getElementById("btn-submit-test").addEventListener("click", async () => {
  const subject_id = document.getElementById("input-test-subject").value;
  const kind = document.getElementById("input-test-kind").value;
  const dateVal = document.getElementById("input-test-date").value;
  const note = document.getElementById("input-test-note").value;

  if (!dateVal) {
    alert("Bitte ein Datum wählen.");
    return;
  }

  const res = await fetch("/api/v1/tests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject_id, kind, date: dateVal, note })
  });

  if (res.ok) {
    modalTest.style.display = "none";
    document.getElementById("input-test-note").value = "";
    await loadPlan();
  } else {
    alert("Fehler beim Speichern der Prüfung.");
  }
});

// Sperrtag speichern
document.getElementById("btn-submit-block").addEventListener("click", async () => {
  const dateVal = document.getElementById("input-block-date").value;
  const typeVal = document.getElementById("input-block-type").value;

  if (!dateVal) {
    alert("Bitte ein Datum wählen.");
    return;
  }

  const res = await fetch("/api/v1/plan/block", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date: dateVal, type: typeVal })
  });

  if (res.ok) {
    modalBlock.style.display = "none";
    await loadPlan();
  } else {
    alert("Für dieses Datum existiert bereits ein Sperrtag.");
  }
});

// Staging Dummies anlegen
const btnSeedDummies = document.getElementById("btn-seed-dummies");
if (btnSeedDummies) {
  btnSeedDummies.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/v1/staging/seed-dummy-tests", { method: "POST" });
      if (res.ok) {
        alert("3 realistische Test-Prüfungen (Mathe, Bio, Deutsch) angelegt!");
        await loadPlan();
      }
    } catch (e) {
      console.error(e);
    }
  });
}

// Staging Reset Event
const btnResetStaging = document.getElementById("btn-reset-staging");
if (btnResetStaging) {
  btnResetStaging.addEventListener("click", async () => {
    if (!confirm("Möchtest du die Staging-Testdaten wirklich zurücksetzen?")) return;
    try {
      const res = await fetch("/api/v1/staging/reset", { method: "POST" });
      if (res.ok) {
        alert("Staging-Datenbank wurde erfolgreich zurückgesetzt.");
        await loadProfile();
        await loadTaxonomy();
        await loadPlan();
        await loadMaterials();
        await checkInboxStatus();
      } else {
        alert("Fehler beim Zurücksetzen.");
      }
    } catch (e) {
      alert("Netzwerkfehler.");
    }
  });
}

// ==========================================================================
// Material Ingestion Subsystem (Milestone 4)
// ==========================================================================

let currentMaterials = [];
let currentUploadToken = null;
let currentPreselectedSubjectId = null;
let allTopicsCache = [];

const btnOpenMaterialModal = document.getElementById("btn-open-material-modal");
const modalMaterial = document.getElementById("modal-material");
const btnCloseMaterialModal = document.getElementById("btn-close-material-modal");

const matStepUpload = document.getElementById("mat-step-upload");
const matStepConfirm = document.getElementById("mat-step-confirm");
const matDropzone = document.getElementById("mat-dropzone");
const matFileInput = document.getElementById("mat-file-input");
const btnTriggerFile = document.getElementById("btn-trigger-file");
const matUploadSpinner = document.getElementById("mat-upload-spinner");

const matPreviewFilename = document.getElementById("mat-preview-filename");
const matPreviewMeta = document.getElementById("mat-preview-meta");
const matPreviewSnippet = document.getElementById("mat-preview-snippet");
const matPreviewIcon = document.getElementById("mat-preview-icon");

// Inbox / Samba Dropzone DOM
const inboxCard = document.getElementById("inbox-card");
const inboxEnvBadge = document.getElementById("inbox-env-badge");
const inboxSubtitle = document.getElementById("inbox-subtitle");
const inboxFileList = document.getElementById("inbox-file-list");
const inboxBadgeDot = document.getElementById("inbox-badge-dot");
const btnRefreshInbox = document.getElementById("btn-refresh-inbox");
const btnProcessInbox = document.getElementById("btn-process-inbox");
const inboxProcessStatus = document.getElementById("inbox-process-status");
const inboxStatusMsg = document.getElementById("inbox-status-msg");
const inboxSpinner = document.getElementById("inbox-spinner");
const navInboxBadge = document.getElementById("nav-inbox-badge");

const matConfirmSubject = document.getElementById("mat-confirm-subject");
const matConfirmTopic = document.getElementById("mat-confirm-topic");
const matConfirmTitle = document.getElementById("mat-confirm-title");
const matConfirmKind = document.getElementById("mat-confirm-kind");
const matConfirmSummary = document.getElementById("mat-confirm-summary");
const btnBackMaterialStep = document.getElementById("btn-back-material-step");
const btnSubmitMaterial = document.getElementById("btn-submit-material");

// Prüft den Inhalt der Samba Dropzone (GET /api/v1/inbox/status)
async function checkInboxStatus() {
  if (!inboxCard) return;
  try {
    if (!currentEnvInfo) {
      try {
        const envRes = await fetch("/api/v1/env");
        if (envRes.ok) currentEnvInfo = await envRes.json();
      } catch (e) {}
    }

    const res = await fetch("/api/v1/inbox/status");
    if (!res.ok) {
      console.error("Inbox Status HTTP Fehler:", res.status);
      if (inboxSubtitle) {
        inboxSubtitle.textContent = `Fehler beim Prüfen des Netzwerkordners (HTTP ${res.status}).`;
      }
      return;
    }
    const data = await res.json();

    const pending = data.pending_count || 0;
    const files = data.files || [];
    const shareName = (currentEnvInfo && currentEnvInfo.is_staging) ? "GoThea-Staging" : "GoThea-Prod";

    if (inboxEnvBadge) {
      inboxEnvBadge.textContent = `Finder: ${shareName}`;
    }

    // Navigation Tab Badge aktualisieren
    if (navInboxBadge) {
      if (pending > 0) {
        navInboxBadge.textContent = pending;
        navInboxBadge.style.display = "inline-block";
      } else {
        navInboxBadge.style.display = "none";
      }
    }

    // Card-Zustand anpassen
    if (pending > 0) {
      inboxCard.classList.add("has-pending");
      if (inboxBadgeDot) inboxBadgeDot.style.display = "block";
      if (inboxSubtitle) {
        inboxSubtitle.textContent = `${pending} neue${pending === 1 ? "s" : ""} Dokument${pending === 1 ? "" : "e"} im Ordner bereit zum Einsortieren.`;
      }
      if (btnProcessInbox) {
        btnProcessInbox.disabled = false;
        btnProcessInbox.innerHTML = `📥 Jetzt einsortieren (${pending})`;
      }
    } else {
      inboxCard.classList.remove("has-pending");
      if (inboxBadgeDot) inboxBadgeDot.style.display = "none";
      if (inboxSubtitle) {
        inboxSubtitle.textContent = `Keine wartenden Dateien im Netzwerkordner.`;
      }
      if (btnProcessInbox) {
        btnProcessInbox.disabled = true;
        btnProcessInbox.innerHTML = `📥 Jetzt einsortieren`;
      }
    }

    // Dateiliste rendern
    if (inboxFileList) {
      inboxFileList.innerHTML = "";
      if (files.length === 0) {
        inboxFileList.innerHTML = `
          <div class="inbox-empty-hint">
            <span>✨</span>
            <span>Ziehe PDFs oder Bilder in deinen Mac-Finder Netzwerkordner <code>${shareName}</code>, um sie automatisch hier einzulesen.</span>
          </div>
        `;
      } else {
        files.forEach((f) => {
          const chip = document.createElement("div");
          chip.className = "inbox-file-chip";
          const isPdf = (f.mime_type || "").includes("pdf") || (f.filename || "").toLowerCase().endsWith(".pdf");
          const icon = isPdf ? "📄" : "🖼️";
          const sizeKb = Math.round((f.file_size || 0) / 1024);
          const sizeStr = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;

          chip.innerHTML = `
            <span>${icon}</span>
            <span style="font-weight: 600;">${f.filename}</span>
            <span class="inbox-file-size">${sizeStr}</span>
          `;
          inboxFileList.appendChild(chip);
        });
      }
    }
  } catch (err) {
    console.error("Fehler beim Prüfen des Inbox-Status:", err);
  }
}

// Startet die Ingestion der Inbox (POST /api/v1/inbox/process)
async function processInbox() {
  if (!btnProcessInbox || btnProcessInbox.disabled) return;
  btnProcessInbox.disabled = true;

  if (inboxProcessStatus) {
    inboxProcessStatus.className = "inbox-process-status";
    inboxProcessStatus.style.display = "flex";
    if (inboxSpinner) inboxSpinner.style.display = "block";
    if (inboxStatusMsg) {
      inboxStatusMsg.textContent = "Dokumente werden analysiert, Text extrahiert & Fächern zugeordnet...";
    }
  }

  try {
    const res = await fetch("/api/v1/inbox/process", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      const pCount = data.processed_count || 0;
      const eCount = data.errors_count || 0;

      if (inboxSpinner) inboxSpinner.style.display = "none";

      if (pCount > 0 && eCount === 0) {
        inboxProcessStatus.className = "inbox-process-status success";
        if (inboxStatusMsg) {
          inboxStatusMsg.textContent = `✅ Erfolgreich: ${pCount} Dokument${pCount === 1 ? "" : "e"} analysiert und einsortiert!`;
        }
      } else if (pCount > 0 && eCount > 0) {
        inboxProcessStatus.className = "inbox-process-status warning";
        if (inboxStatusMsg) {
          inboxStatusMsg.textContent = `⚠️ ${pCount} Dokument${pCount === 1 ? "" : "e"} verarbeitet, ${eCount} fehlerhafte Datei(en) nach _errors/ verschoben.`;
        }
      } else if (pCount === 0 && eCount > 0) {
        inboxProcessStatus.className = "inbox-process-status warning";
        if (inboxStatusMsg) {
          inboxStatusMsg.textContent = `⚠️ Fehler bei ${eCount} Datei(en). Details in _errors/.`;
        }
      } else {
        inboxProcessStatus.className = "inbox-process-status";
        if (inboxStatusMsg) {
          inboxStatusMsg.textContent = "Keine neuen Dateien zur Verarbeitung gefunden.";
        }
      }

      await loadTaxonomy();
      await loadMaterials();
      await loadUploadsHistory();
      if (currentDetailSubjectId) await loadSubjectMaterials(currentDetailSubjectId);
      await checkInboxStatus();

      setTimeout(() => {
        if (inboxProcessStatus) inboxProcessStatus.style.display = "none";
      }, 6000);
    } else {
      const err = await res.json().catch(() => ({}));
      if (inboxSpinner) inboxSpinner.style.display = "none";
      inboxProcessStatus.className = "inbox-process-status warning";
      if (inboxStatusMsg) {
        inboxStatusMsg.textContent = `❌ Fehler bei der Verarbeitung: ${err.detail || "Serverfehler"}`;
      }
    }
  } catch (err) {
    console.error("Netzwerkfehler beim Verarbeiten des Posteingangs:", err);
    if (inboxSpinner) inboxSpinner.style.display = "none";
    inboxProcessStatus.className = "inbox-process-status warning";
    if (inboxStatusMsg) {
      inboxStatusMsg.textContent = "❌ Netzwerkfehler beim Verarbeiten.";
    }
  } finally {
    await checkInboxStatus();
  }
}

if (btnRefreshInbox) {
  btnRefreshInbox.addEventListener("click", async () => {
    const origHtml = btnRefreshInbox.innerHTML;
    btnRefreshInbox.disabled = true;
    btnRefreshInbox.innerHTML = `<span class="inbox-spin-icon">🔄</span> Prüfe...`;
    try {
      await checkInboxStatus();
      btnRefreshInbox.innerHTML = `✓ Geprüft`;
    } catch (e) {
      btnRefreshInbox.innerHTML = `⚠️ Fehler`;
    } finally {
      setTimeout(() => {
        btnRefreshInbox.innerHTML = origHtml;
        btnRefreshInbox.disabled = false;
      }, 1000);
    }
  });
}

if (btnProcessInbox) {
  btnProcessInbox.addEventListener("click", () => {
    processInbox();
  });
}

function buildMaterialCard(m, onDeleted) {
  const card = document.createElement("div");
  card.className = "material-card";

  const isPdf = (m.mime_type || "").includes("pdf");
  let docIcon = "📄";
  if (m.kind && m.kind.includes("Stundenplan")) docIcon = "📅";
  else if (m.kind && m.kind.includes("Buch")) docIcon = "📚";
  else if (m.kind && m.kind.includes("Heft")) docIcon = "📁";
  else if (m.kind && (m.kind.includes("Klassenarbeit") || m.kind.includes("Test") || m.kind.includes("Übung"))) docIcon = "📝";
  else if (!isPdf) docIcon = "🖼️";

  const sizeKb = Math.round((m.file_size || 0) / 1024);
  const sizeStr = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;

  card.innerHTML = `
    <div>
      <div class="mat-card-header">
        <div class="mat-card-title">${escapeHtml(m.title)}</div>
        <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
          ${m.dossier_title ? `<span class="mat-dossier-badge" title="Zugeordneter Hefter">📁 ${escapeHtml(m.dossier_title)}</span>` : ""}
          <span class="mat-card-badge" style="background: rgba(99, 102, 241, 0.15); color: var(--accent-light); border: 1px solid rgba(99, 102, 241, 0.3);">
            ${escapeHtml(m.kind || "Dokument")}
          </span>
        </div>
      </div>
      <div class="mat-card-meta">
        <span style="color: ${m.subject_color || 'var(--text-primary)'}; font-weight: 600;">
          ${m.subject_icon || '📚'} ${escapeHtml(m.subject_name || 'Fach')}
        </span>
        ${m.topic_name ? `<span>• 📑 ${escapeHtml(m.topic_name)}</span>` : ""}
        <span>• ${docIcon} ${m.page_count} S. (${sizeStr})</span>
        ${m.start_page && m.end_page ? `<span>• S. ${m.start_page}–${m.end_page}</span>` : ""}
      </div>
      ${m.summary ? `<div class="mat-card-summary">“${escapeHtml(m.summary)}”</div>` : ""}
    </div>
    <div class="mat-card-actions">
      ${m.kind && m.kind.includes("Stundenplan") ? `
        <button class="btn-mat-action btn-mat-tt" style="background: rgba(99, 102, 241, 0.2); border-color: var(--accent); color: var(--accent-light); font-weight: 700;" title="Als interaktives Stundenplan-Widget öffnen">
          🗓️ Stundenplan
        </button>
      ` : ""}
      <button class="btn-mat-action btn-mat-view" title="${m.kind && m.kind.includes('Stundenplan') ? 'Original-Scan als Dokument ansehen' : 'Dokument im Popup ansehen'}">
        👁️ ${m.kind && m.kind.includes('Stundenplan') ? 'Scan' : 'Öffnen'}
      </button>
      <button class="btn-mat-action btn-mat-reader" title="Im Dokument-Reader öffnen & mit Apple Pencil beschreiben">
        📖 Reader
      </button>
      <button class="btn-mat-action btn-mat-wb" title="Dieses Dokument auf der digitalen Tafel mit KI-Tutorin Luna üben">
        🎨 Tafel
      </button>
      <button class="btn-mat-action btn-mat-cloze" title="Lückentext-Übung direkt aus diesem Dokument erstellen">
        🧩 Üben
      </button>
      <button class="btn-mat-action btn-mat-edit parent-only" title="Dokument anpassen (Fach, Thema, Titel)">
        ✏️ Ändern
      </button>
      ${(m.page_count > 1 || (m.mime_type || "").includes("pdf")) ? `
        <button class="btn-mat-action btn-mat-reorder parent-only" title="Seitenreihenfolge ändern & verwalten">
          📑 Seiten
        </button>
      ` : ""}
      <button class="btn-mat-action btn-mat-del parent-only" data-id="${m.id}" title="Material löschen">
        🗑️
      </button>
    </div>
  `;

  const ttBtn = card.querySelector(".btn-mat-tt");
  if (ttBtn) {
    ttBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      switchToTab("timetable");
    });
  }

  const wbBtn = card.querySelector(".btn-mat-wb");
  if (wbBtn) {
    wbBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (typeof window.openMaterialOnWhiteboard === "function") {
        window.openMaterialOnWhiteboard(m.id, m.subject_id);
      } else {
        switchToTab("whiteboard");
      }
    });
  }

  const clozeBtn = card.querySelector(".btn-mat-cloze");
  if (clozeBtn) {
    clozeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (typeof window.openClozeTrainer === "function") {
        const subName = (cachedSubjects.find(s => s.id === m.subject_id) || {}).name || "Schulfach";
        window.openClozeTrainer({
          subjectId: m.subject_id,
          subjectName: subName,
          materialId: m.id,
          sourceMaterialTitle: m.title
        });
      }
    });
  }

  const viewBtn = card.querySelector(".btn-mat-view");
  if (viewBtn) {
    viewBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openDocumentViewerModal(m);
    });
  }

  const readerBtn = card.querySelector(".btn-mat-reader");
  if (readerBtn) {
    readerBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openMaterialInReader(m);
    });
  }

  const editBtn = card.querySelector(".btn-mat-edit");
  if (editBtn) {
    editBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openEditMaterialModal(m);
    });
  }

  const reorderBtn = card.querySelector(".btn-mat-reorder");
  if (reorderBtn) {
    reorderBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openReorderPagesModal(m);
    });
  }

  const delBtn = card.querySelector(".btn-mat-del");
  if (delBtn) {
    delBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm(`Möchtest du das Material „${m.title}“ wirklich löschen?`)) return;
      try {
        const delRes = await fetch(`/api/v1/materials/${m.id}`, { method: "DELETE" });
        if (delRes.ok) {
          if (typeof onDeleted === "function") {
            onDeleted();
          } else {
            await loadMaterials();
            await loadUploadsHistory();
            if (currentDetailSubjectId) await loadSubjectMaterials(currentDetailSubjectId);
          }
        } else {
          alert("Fehler beim Löschen des Materials.");
        }
      } catch (err) {
        alert("Netzwerkfehler beim Löschen.");
      }
    });
  }

  return card;
}

async function loadMaterials() {
  try {
    const res = await fetch("/api/v1/materials");
    if (res.ok) {
      currentMaterials = await res.json();
      renderUploadsHistory(currentMaterials);
    }
  } catch (err) {
    console.error("Fehler beim Laden der Materialien:", err);
  }
}

async function loadUploadsHistory() {
  const historyList = document.getElementById("uploads-history-list");
  if (!historyList) return;
  try {
    const res = await fetch("/api/v1/materials");
    if (res.ok) {
      currentMaterials = await res.json();
      renderUploadsHistory(currentMaterials);
    }
  } catch (err) {
    console.error("Fehler beim Laden der Upload-Historie:", err);
  }
}

function renderUploadsHistory(materials) {
  const historyList = document.getElementById("uploads-history-list");
  const countBadge = document.getElementById("uploads-history-count");
  if (!historyList) return;

  historyList.innerHTML = "";
  if (countBadge) {
    countBadge.textContent = `${materials.length} Dokument${materials.length === 1 ? "" : "e"}`;
  }

  if (materials.length === 0) {
    historyList.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 40px 16px; background: rgba(255, 255, 255, 0.02); border: 1px dashed var(--border-color); border-radius: 14px; color: var(--text-secondary);">
        <span style="font-size: 2.2rem; display: block; margin-bottom: 8px;">📭</span>
        <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">Noch keine Uploads vorhanden</div>
        <p style="font-size: 0.85rem; max-width: 440px; margin: 0 auto;">Ziehe Dateien in die Upload-Zone oben oder in deinen Finder-Netzwerkordner, um sie automatisch hier einzulesen.</p>
      </div>
    `;
    return;
  }

  materials.forEach((m) => {
    const card = buildMaterialCard(m, async () => {
      await loadMaterials();
      await loadUploadsHistory();
      if (currentDetailSubjectId) await loadSubjectMaterials(currentDetailSubjectId);
    });
    historyList.appendChild(card);
  });
}

function setupUploadsPageEvents() {
  const dropzone = document.getElementById("page-upload-dropzone");
  const fileInput = document.getElementById("page-file-input");
  const btnTrigger = document.getElementById("btn-trigger-page-upload");

  if (btnTrigger && fileInput) {
    btnTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", (e) => {
      if (e.target !== btnTrigger) {
        fileInput.click();
      }
    });

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("drag-over");
    });

    dropzone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      dropzone.classList.remove("drag-over");
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("drag-over");
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        openMaterialUploadModal();
        handleFilesUpload(Array.from(e.dataTransfer.files));
      }
    });
  }

  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        const files = Array.from(e.target.files);
        openMaterialUploadModal();
        handleFilesUpload(files);
      }
    });
  }
}

function updateMaterialTopicOptions(subjectId, selectedTopicId = null) {
  if (!matConfirmTopic) return;
  matConfirmTopic.innerHTML = '<option value="">-- Kein spezifisches Thema --</option>';
  const subjectTopics = allTopicsCache.filter((t) => t.subject_id === subjectId);
  subjectTopics.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = `${t.name} (Stufe ${t.rlp_level_code || 'E'})`;
    if (selectedTopicId && t.id === selectedTopicId) {
      opt.selected = true;
    }
    matConfirmTopic.appendChild(opt);
  });
}

async function handleFilesUpload(files) {
  if (!files || files.length === 0) return;
  if (files.length === 1) {
    await handleSingleFileUpload(files[0]);
  } else {
    await handleBatchFileUpload(files);
  }
}

async function handleSingleFileUpload(file) {
  if (!file) return;

  if (matDropzone) matDropzone.style.display = "none";
  if (matUploadSpinner) matUploadSpinner.style.display = "block";
  const pBar = document.getElementById("mat-batch-progress-bar");
  if (pBar) pBar.style.display = "none";
  const pStat = document.getElementById("mat-batch-status");
  if (pStat) pStat.textContent = "";
  const spinnerText = document.getElementById("mat-spinner-text");
  if (spinnerText) spinnerText.textContent = "Analysiere Dokument & Schlagwörter...";

  const formData = new FormData();
  formData.append("file", file);
  if (currentPreselectedSubjectId) {
    formData.append("subject_id", currentPreselectedSubjectId);
  }

  try {
    const res = await fetch("/api/v1/materials/pre-analyze", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      alert(errData.detail || "Fehler bei der Analyse.");
      resetMaterialModal();
      return;
    }

    const data = await res.json();
    currentUploadToken = data.upload_token;

    matStepUpload.style.display = "none";
    matStepConfirm.style.display = "block";

    matPreviewFilename.textContent = data.filename;
    const sizeKb = Math.round(data.file_size / 1024);
    const sizeStr = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;
    matPreviewMeta.textContent = `${data.page_count} Seite${data.page_count === 1 ? "" : "n"} • ${sizeStr}`;
    matPreviewIcon.textContent = data.mime_type.includes("pdf") ? "📄" : "🖼️";

    if (data.preview_snippet) {
      matPreviewSnippet.style.display = "block";
      matPreviewSnippet.textContent = `„${data.preview_snippet}“`;
    } else {
      matPreviewSnippet.style.display = "none";
    }

    matConfirmSubject.innerHTML = "";
    const activeSubId = currentPreselectedSubjectId || data.predicted_subject_id;
    currentSubjects.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = `${s.icon} ${s.name}`;
      if (activeSubId && s.id === activeSubId) {
        opt.selected = true;
      }
      matConfirmSubject.appendChild(opt);
    });

    const fixedBadge = document.getElementById("mat-fixed-subject-badge");
    if (currentPreselectedSubjectId) {
      matConfirmSubject.disabled = true;
      if (fixedBadge) fixedBadge.style.display = "block";
    } else {
      matConfirmSubject.disabled = false;
      if (fixedBadge) fixedBadge.style.display = "none";
    }

    updateMaterialTopicOptions(activeSubId, data.predicted_topic_id);

    matConfirmTitle.value = data.predicted_title || "Lernmaterial";
    matConfirmKind.value = data.predicted_kind || "Arbeitsblatt";
    matConfirmSummary.value = "";
  } catch (err) {
    alert("Netzwerkfehler beim Upload.");
    resetMaterialModal();
  }
}

async function handleBatchFileUpload(files) {
  if (!files || files.length === 0) return;

  if (matDropzone) matDropzone.style.display = "none";
  if (matUploadSpinner) matUploadSpinner.style.display = "block";

  const pBar = document.getElementById("mat-batch-progress-bar");
  const pFill = document.getElementById("mat-batch-progress-fill");
  const pStat = document.getElementById("mat-batch-status");
  const spinnerText = document.getElementById("mat-spinner-text");

  if (pBar) pBar.style.display = "block";

  const targetSub = currentPreselectedSubjectId
    ? currentSubjects.find((s) => s.id === currentPreselectedSubjectId)
    : null;

  let successCount = 0;
  const total = files.length;

  for (let i = 0; i < total; i++) {
    const file = files[i];
    const pct = Math.round((i / total) * 100);
    if (pFill) pFill.style.width = `${pct}%`;
    if (spinnerText) {
      spinnerText.textContent = targetSub
        ? `Verarbeite Dokumente für ${targetSub.name}...`
        : "Verarbeite Dokumente...";
    }
    if (pStat) {
      pStat.textContent = `Datei ${i + 1} von ${total}: ${file.name}`;
    }

    try {
      const formData = new FormData();
      formData.append("file", file);
      if (currentPreselectedSubjectId) {
        formData.append("subject_id", currentPreselectedSubjectId);
      }

      const preRes = await fetch("/api/v1/materials/pre-analyze", {
        method: "POST",
        body: formData
      });

      if (!preRes.ok) {
        console.error(`Fehler bei der Voranalyse von ${file.name}`);
        continue;
      }

      const preData = await preRes.json();
      const payload = {
        upload_token: preData.upload_token,
        subject_id: currentPreselectedSubjectId || preData.predicted_subject_id,
        topic_id: preData.predicted_topic_id || null,
        title: preData.predicted_title || file.name,
        kind: preData.predicted_kind || "Arbeitsblatt",
        summary: null
      };

      const confRes = await fetch("/api/v1/materials/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (confRes.ok) {
        successCount++;
      } else {
        console.error(`Fehler beim Speichern von ${file.name}`);
      }
    } catch (e) {
      console.error(`Upload-Fehler bei ${file.name}:`, e);
    }
  }

  if (pFill) pFill.style.width = "100%";
  if (spinnerText) {
    spinnerText.textContent = `✅ ${successCount} von ${total} Dokumenten erfolgreich hochgeladen!`;
  }
  if (pStat) {
    pStat.textContent = targetSub
      ? `Alle Dokumente wurden zu ${targetSub.name} hinzugefügt.`
      : "Alle Dokumente wurden erfolgreich verarbeitet.";
  }

  setTimeout(async () => {
    if (modalMaterial) modalMaterial.style.display = "none";
    resetMaterialModal();
    await loadMaterials();
    await loadUploadsHistory();
    if (currentDetailSubjectId) await loadSubjectMaterials(currentDetailSubjectId);
  }, 1200);
}

function resetMaterialModal() {
  currentUploadToken = null;
  currentPreselectedSubjectId = null;
  if (matFileInput) matFileInput.value = "";
  if (matDropzone) matDropzone.style.display = "flex";
  if (matUploadSpinner) matUploadSpinner.style.display = "none";
  if (matStepUpload) matStepUpload.style.display = "block";
  if (matStepConfirm) matStepConfirm.style.display = "none";

  const pBar = document.getElementById("mat-batch-progress-bar");
  if (pBar) pBar.style.display = "none";
  const pFill = document.getElementById("mat-batch-progress-fill");
  if (pFill) pFill.style.width = "0%";
  const pStat = document.getElementById("mat-batch-status");
  if (pStat) pStat.textContent = "";
  const spinnerText = document.getElementById("mat-spinner-text");
  if (spinnerText) spinnerText.textContent = "Analysiere Dokument & Schlagwörter...";

  const fixedBadge = document.getElementById("mat-fixed-subject-badge");
  if (fixedBadge) fixedBadge.style.display = "none";
  if (matConfirmSubject) matConfirmSubject.disabled = false;
}

function openMaterialUploadModal(preselectedSubjectId = null) {
  resetMaterialModal();
  currentPreselectedSubjectId = preselectedSubjectId;

  const titleEl = document.getElementById("modal-material-title");
  const subEl = document.getElementById("mat-modal-subtitle");
  const dzText = document.getElementById("mat-dropzone-text");
  const dzSub = document.getElementById("mat-dropzone-sub");
  const targetSub = currentPreselectedSubjectId
    ? currentSubjects.find((s) => s.id === currentPreselectedSubjectId)
    : null;

  if (targetSub) {
    if (titleEl) titleEl.textContent = `📄 Neues Dokument für ${targetSub.name} hochladen`;
    if (subEl) subEl.textContent = `Dokumente werden automatisch dem Fach ${targetSub.name} zugeordnet (Mehrfachauswahl möglich).`;
    if (dzText) dzText.textContent = `Dateien für ${targetSub.name} hierher ziehen oder auswählen`;
    if (dzSub) dzSub.textContent = "PDF oder Foto (Mehrfachauswahl möglich)";
  } else {
    if (titleEl) titleEl.textContent = "📄 Dokument hinzufügen";
    if (subEl) subEl.textContent = "Lade ein Schulbuch, ein Arbeitsblatt, eine Hefterseite oder eine Klassenarbeit hoch.";
    if (dzText) dzText.textContent = "Datei hierher ziehen oder tippen";
    if (dzSub) dzSub.textContent = "PDF oder Foto (Mehrfachauswahl möglich)";
  }

  if (modalMaterial) modalMaterial.style.display = "flex";
}

if (matConfirmSubject) {
  matConfirmSubject.addEventListener("change", () => {
    updateMaterialTopicOptions(matConfirmSubject.value);
  });
}

if (btnOpenMaterialModal) {
  btnOpenMaterialModal.addEventListener("click", () => {
    openMaterialUploadModal();
  });
}

if (btnCloseMaterialModal) {
  btnCloseMaterialModal.addEventListener("click", () => {
    if (modalMaterial) modalMaterial.style.display = "none";
    resetMaterialModal();
  });
}

if (modalMaterial) {
  modalMaterial.addEventListener("click", (e) => {
    if (e.target === modalMaterial) {
      modalMaterial.style.display = "none";
      resetMaterialModal();
    }
  });
}

if (btnTriggerFile && matFileInput) {
  btnTriggerFile.addEventListener("click", () => matFileInput.click());
}

if (matDropzone && matFileInput) {
  matDropzone.addEventListener("click", (e) => {
    if (e.target !== btnTriggerFile) {
      matFileInput.click();
    }
  });

  matDropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    matDropzone.classList.add("drag-over");
  });

  matDropzone.addEventListener("dragleave", () => {
    matDropzone.classList.remove("drag-over");
  });

  matDropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    matDropzone.classList.remove("drag-over");
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesUpload(Array.from(e.dataTransfer.files));
    }
  });
}

if (matFileInput) {
  matFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFilesUpload(Array.from(e.target.files));
    }
  });
}

if (btnBackMaterialStep) {
  btnBackMaterialStep.addEventListener("click", () => {
    resetMaterialModal();
  });
}

if (btnSubmitMaterial) {
  btnSubmitMaterial.addEventListener("click", async () => {
    if (!currentUploadToken) {
      alert("Keine gültige Sitzung vorhanden.");
      return;
    }
    const titleVal = matConfirmTitle.value.trim();
    if (!titleVal) {
      alert("Bitte gib einen Titel für das Material ein.");
      return;
    }

    const chosenSubId = currentPreselectedSubjectId || matConfirmSubject.value;
    const payload = {
      upload_token: currentUploadToken,
      subject_id: chosenSubId,
      topic_id: matConfirmTopic.value || null,
      title: titleVal,
      kind: matConfirmKind.value,
      summary: matConfirmSummary.value.trim() || null
    };

    btnSubmitMaterial.disabled = true;
    btnSubmitMaterial.textContent = "Speichere...";

    try {
      const res = await fetch("/api/v1/materials/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        if (modalMaterial) modalMaterial.style.display = "none";
        resetMaterialModal();
        await loadMaterials();
        await loadUploadsHistory();
        if (currentDetailSubjectId) await loadSubjectMaterials(currentDetailSubjectId);
      } else {
        const errData = await res.json().catch(() => ({}));
        alert(errData.detail || "Fehler beim Speichern des Materials.");
      }
    } catch (err) {
      alert("Netzwerkfehler.");
    } finally {
      btnSubmitMaterial.disabled = false;
      btnSubmitMaterial.textContent = "Bestätigen & Speichern";
    }
  });
}

// ==========================================
// 8. Dokumenten-Viewer (Popup) & Tafel-Verbindung
// ==========================================
let activeViewerMaterial = null;
let currentViewerPage = 1;

const modalMaterialViewer = document.getElementById("modal-material-viewer");
const btnCloseViewerModal = document.getElementById("btn-close-viewer-modal");
const btnViewerOpenWb = document.getElementById("btn-viewer-open-wb");
const btnViewerPrevPage = document.getElementById("btn-viewer-prev-page");
const btnViewerNextPage = document.getElementById("btn-viewer-next-page");
const btnViewerZoomOut = document.getElementById("btn-viewer-zoom-out");
const btnViewerZoomIn = document.getElementById("btn-viewer-zoom-in");
const btnViewerZoomLabel = document.getElementById("viewer-zoom-label");
const btnViewerFitPage = document.getElementById("btn-viewer-fit-page");
const btnViewerFitWidth = document.getElementById("btn-viewer-fit-width");

let currentViewerZoomPercent = 100;

function setViewerZoomPercent(percent) {
  // Maximal 100% (volle Breite), minimal 30% (weit herausgezoomt)
  currentViewerZoomPercent = Math.min(100, Math.max(30, Math.round(percent)));
  const viewerImg = document.getElementById("viewer-img");
  const label = document.getElementById("viewer-zoom-label");
  const btnIn = document.getElementById("btn-viewer-zoom-in");
  const btnOut = document.getElementById("btn-viewer-zoom-out");

  if (viewerImg) {
    viewerImg.classList.remove("viewer-img-fitpage");
    viewerImg.classList.add("viewer-img-fullwidth");
    viewerImg.style.width = `${currentViewerZoomPercent}%`;
    viewerImg.style.maxWidth = "100%";
    viewerImg.style.height = "auto";
  }
  if (label) {
    label.textContent = `${currentViewerZoomPercent}%`;
  }
  if (btnIn) {
    btnIn.disabled = currentViewerZoomPercent >= 100;
  }
  if (btnOut) {
    btnOut.disabled = currentViewerZoomPercent <= 30;
  }
}

function fitViewerToPage() {
  const viewerImg = document.getElementById("viewer-img");
  const container = document.getElementById("viewer-content-container");
  if (!viewerImg || !container) return;

  const availHeight = container.clientHeight - 32;
  const availWidth = container.clientWidth - 32;
  if (availHeight <= 0 || availWidth <= 0) return;

  const natWidth = viewerImg.naturalWidth || 1000;
  const natHeight = viewerImg.naturalHeight || 1414;

  const targetImgWidth = availHeight * (natWidth / natHeight);
  const targetPercent = Math.round((targetImgWidth / availWidth) * 100);

  setViewerZoomPercent(targetPercent);
  container.scrollTop = 0;
}

function openDocumentViewerModal(material) {
  activeViewerMaterial = material;
  currentViewerPage = 1;
  setViewerZoomPercent(100); // Standardmäßig maximal in voller Breite!

  const titleEl = document.getElementById("viewer-doc-title");
  const badgeEl = document.getElementById("viewer-doc-badge");
  const dlBtn = document.getElementById("btn-viewer-download");
  const pagerBar = document.getElementById("viewer-pager-bar");
  const container = document.getElementById("viewer-content-container");

  if (container) container.scrollTop = 0;
  if (titleEl) titleEl.textContent = material.title;
  if (badgeEl) {
    badgeEl.textContent = `${material.subject_name || "Fach"} • ${material.kind || "Material"}${material.topic_name ? " • " + material.topic_name : ""}`;
  }
  if (dlBtn) {
    dlBtn.href = `/api/v1/materials/${material.id}/file`;
  }

  const pageCount = material.page_count || 1;
  if (pagerBar) {
    pagerBar.style.display = pageCount > 1 ? "flex" : "none";
  }

  const reorderBtn = document.getElementById("btn-viewer-reorder-pages");
  if (reorderBtn) {
    const isPdf = (material.mime_type || "").includes("pdf");
    reorderBtn.style.display = (pageCount > 1 || isPdf) ? "flex" : "none";
    reorderBtn.onclick = () => {
      closeDocumentViewerModal();
      openReorderPagesModal(material);
    };
  }

  renderViewerPage();
  if (modalMaterialViewer) modalMaterialViewer.style.display = "flex";
}

function renderViewerPage() {
  if (!activeViewerMaterial) return;
  const pageLabel = document.getElementById("viewer-page-label");
  const viewerImg = document.getElementById("viewer-img");
  const spinner = document.getElementById("viewer-loading-spinner");
  const container = document.getElementById("viewer-content-container");
  const pageCount = activeViewerMaterial.page_count || 1;

  if (container) container.scrollTop = 0;
  if (pageLabel) {
    pageLabel.textContent = `Seite ${currentViewerPage} / ${pageCount}`;
  }
  if (viewerImg) {
    if (spinner) spinner.style.display = "block";
    viewerImg.style.opacity = "0.2";

    viewerImg.onload = () => {
      if (spinner) spinner.style.display = "none";
      viewerImg.style.opacity = "1";
    };
    viewerImg.onerror = () => {
      if (spinner) spinner.style.display = "none";
      viewerImg.style.opacity = "1";
    };

    viewerImg.src = `/api/v1/materials/${activeViewerMaterial.id}/preview?page=${currentViewerPage}`;

    // Nächste Seite im Hintergrund vorladen
    if (currentViewerPage < pageCount) {
      const nextPreload = new Image();
      nextPreload.src = `/api/v1/materials/${activeViewerMaterial.id}/preview?page=${currentViewerPage + 1}`;
    }
  }
}

function closeDocumentViewerModal() {
  if (modalMaterialViewer) modalMaterialViewer.style.display = "none";
  const viewerImg = document.getElementById("viewer-img");
  if (viewerImg) {
    viewerImg.src = "";
    viewerImg.onload = null;
    viewerImg.onerror = null;
  }
  const spinner = document.getElementById("viewer-loading-spinner");
  if (spinner) spinner.style.display = "none";
  activeViewerMaterial = null;
}

function openMaterialInReader(material) {
  switchToTab("books");
  const ch = {
    id: material.id,
    title: material.title,
    page_count: material.page_count || 1,
    start_page: material.start_page || 1,
    end_page: material.end_page || material.page_count || 1,
    topic_name: material.topic_name || "Material",
    focus: material.summary || "Dokumentansicht mit handschriftlichen Notizen"
  };
  openChapter(ch);
}

if (btnCloseViewerModal) {
  btnCloseViewerModal.addEventListener("click", closeDocumentViewerModal);
}

if (modalMaterialViewer) {
  modalMaterialViewer.addEventListener("click", (e) => {
    if (e.target === modalMaterialViewer) {
      closeDocumentViewerModal();
    }
  });
}

if (btnViewerPrevPage) {
  btnViewerPrevPage.addEventListener("click", () => {
    if (activeViewerMaterial && currentViewerPage > 1) {
      currentViewerPage--;
      renderViewerPage();
    }
  });
}

if (btnViewerNextPage) {
  btnViewerNextPage.addEventListener("click", () => {
    if (activeViewerMaterial && currentViewerPage < (activeViewerMaterial.page_count || 1)) {
      currentViewerPage++;
      renderViewerPage();
    }
  });
}

if (btnViewerOpenWb) {
  btnViewerOpenWb.addEventListener("click", () => {
    if (activeViewerMaterial) {
      const mat = activeViewerMaterial;
      closeDocumentViewerModal();
      openMaterialInReader(mat);
    }
  });
}

if (btnViewerZoomOut) {
  btnViewerZoomOut.addEventListener("click", () => {
    setViewerZoomPercent(currentViewerZoomPercent - 15);
  });
}

if (btnViewerZoomIn) {
  btnViewerZoomIn.addEventListener("click", () => {
    setViewerZoomPercent(currentViewerZoomPercent + 15);
  });
}

if (btnViewerZoomLabel) {
  btnViewerZoomLabel.addEventListener("click", () => {
    setViewerZoomPercent(100);
  });
}

if (btnViewerFitWidth) {
  btnViewerFitWidth.addEventListener("click", () => {
    setViewerZoomPercent(100);
    const container = document.getElementById("viewer-content-container");
    if (container) container.scrollTop = 0;
  });
}

if (btnViewerFitPage) {
  btnViewerFitPage.addEventListener("click", () => {
    fitViewerToPage();
  });
}

// Doppelklick auf Bild wechselt zwischen Ganze Seite und 100% Volle Breite
const viewerImgEl = document.getElementById("viewer-img");
if (viewerImgEl) {
  viewerImgEl.addEventListener("dblclick", () => {
    if (activeViewerMaterial) {
      if (currentViewerZoomPercent >= 90) {
        fitViewerToPage();
      } else {
        setViewerZoomPercent(100);
      }
    }
  });
}

// Mausrad mit Strg/Cmd oder Trackpad-Pinch zum stufenlosen Zoomen
const viewerContainerEl = document.getElementById("viewer-content-container");
if (viewerContainerEl) {
  viewerContainerEl.addEventListener("wheel", (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 5 : -5;
      setViewerZoomPercent(currentViewerZoomPercent + delta);
    }
  }, { passive: false });
}

// ==========================================================================
// Material Reorganization Subsystem (Edit Metadata, Reorder Pages, Merge)
// ==========================================================================

async function refreshAllMaterialViews() {
  await loadMaterials();
  await loadUploadsHistory();
  if (currentDetailSubjectId) {
    await loadSubjectMaterials(currentDetailSubjectId);
  }
}

// --- 1. Edit Material Modal (Fach, Thema, Titel, Art) ---
const modalEditMaterial = document.getElementById("modal-edit-material");
const btnCloseEditMaterial = document.getElementById("btn-close-edit-material-modal");
const btnCancelEditMaterial = document.getElementById("btn-cancel-edit-material");
const btnSaveEditMaterial = document.getElementById("btn-save-edit-material");
const editMatSubject = document.getElementById("edit-mat-subject");
const editMatTopic = document.getElementById("edit-mat-topic");

function updateEditTopicOptions(subjectId, selectedTopicId = null) {
  if (!editMatTopic) return;
  editMatTopic.innerHTML = '<option value="">-- Kein spezifisches Thema --</option>';
  const topics = allTopicsCache.filter((t) => t.subject_id === subjectId);
  topics.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = `${t.name} (Stufe ${t.rlp_level_code || "E"})`;
    if (selectedTopicId && t.id === selectedTopicId) opt.selected = true;
    editMatTopic.appendChild(opt);
  });
}

function openEditMaterialModal(material) {
  if (!modalEditMaterial) return;
  const idInput = document.getElementById("edit-mat-id");
  const titleInput = document.getElementById("edit-mat-title");
  const summaryInput = document.getElementById("edit-mat-summary");

  if (idInput) idInput.value = material.id;
  if (titleInput) titleInput.value = material.title || "";
  if (summaryInput) summaryInput.value = material.summary || "";

  if (editMatSubject) {
    editMatSubject.innerHTML = currentSubjects
      .map((s) => `<option value="${s.id}" ${s.id === material.subject_id ? "selected" : ""}>${s.icon || "📚"} ${escapeHtml(s.name)}</option>`)
      .join("");

    updateEditTopicOptions(material.subject_id, material.topic_id);
    editMatSubject.onchange = () => {
      updateEditTopicOptions(editMatSubject.value, null);
    };
  }

  const kindSelect = document.getElementById("edit-mat-kind");
  if (kindSelect) {
    let matched = false;
    for (let i = 0; i < kindSelect.options.length; i++) {
      if (kindSelect.options[i].value === material.kind) {
        kindSelect.selectedIndex = i;
        matched = true;
        break;
      }
    }
    if (!matched && material.kind) {
      const customOpt = document.createElement("option");
      customOpt.value = material.kind;
      customOpt.textContent = material.kind;
      customOpt.selected = true;
      kindSelect.appendChild(customOpt);
    }
  }

  modalEditMaterial.style.display = "flex";
}

function closeEditMaterialModal() {
  if (modalEditMaterial) modalEditMaterial.style.display = "none";
}

if (btnCloseEditMaterial) btnCloseEditMaterial.addEventListener("click", closeEditMaterialModal);
if (btnCancelEditMaterial) btnCancelEditMaterial.addEventListener("click", closeEditMaterialModal);
if (modalEditMaterial) {
  modalEditMaterial.addEventListener("click", (e) => {
    if (e.target === modalEditMaterial) closeEditMaterialModal();
  });
}

if (btnSaveEditMaterial) {
  btnSaveEditMaterial.addEventListener("click", async () => {
    const matId = document.getElementById("edit-mat-id").value;
    const title = document.getElementById("edit-mat-title").value.trim();
    const subjectId = editMatSubject ? editMatSubject.value : null;
    const topicId = editMatTopic ? (editMatTopic.value || null) : null;
    const kind = document.getElementById("edit-mat-kind").value;
    const summary = document.getElementById("edit-mat-summary").value.trim();

    if (!title) {
      alert("Bitte gib einen Titel für das Dokument an.");
      return;
    }

    btnSaveEditMaterial.disabled = true;
    btnSaveEditMaterial.textContent = "Speichere...";
    try {
      const res = await fetch(`/api/v1/materials/${matId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          subject_id: subjectId,
          topic_id: topicId,
          kind,
          summary
        })
      });

      if (res.ok) {
        closeEditMaterialModal();
        await refreshAllMaterialViews();
        if (kind === "Buch" || kind === "Buchauszug") {
          await loadBooks();
        }
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Fehler beim Aktualisieren: ${err.detail || "Unbekannter Fehler"}`);
      }
    } catch (e) {
      console.error(e);
      alert("Netzwerkfehler beim Aktualisieren.");
    } finally {
      btnSaveEditMaterial.disabled = false;
      btnSaveEditMaterial.textContent = "Änderungen speichern";
    }
  });
}

// --- 2. Reorder Pages Modal (Seitenreihenfolge ändern & löschen) ---
let activeReorderMaterial = null;
let currentReorderPages = [];
const modalReorderPages = document.getElementById("modal-reorder-pages");
const btnCloseReorderModal = document.getElementById("btn-close-reorder-modal");
const btnReorderReset = document.getElementById("btn-reorder-reset");
const btnSaveReorderPages = document.getElementById("btn-save-reorder-pages");

function openReorderPagesModal(material) {
  if (!modalReorderPages) return;
  activeReorderMaterial = material;
  const count = material.page_count || 1;
  currentReorderPages = Array.from({ length: count }, (_, i) => i + 1);

  const titleEl = document.getElementById("reorder-doc-title");
  if (titleEl) {
    titleEl.textContent = `Seiten von „${material.title}“ ordnen`;
  }
  renderReorderPagesGrid();
  modalReorderPages.style.display = "flex";
}

function closeReorderPagesModal() {
  if (modalReorderPages) modalReorderPages.style.display = "none";
  activeReorderMaterial = null;
  currentReorderPages = [];
}

function renderReorderPagesGrid() {
  const grid = document.getElementById("reorder-pages-grid");
  const badge = document.getElementById("reorder-summary-badge");
  if (!grid || !activeReorderMaterial) return;

  const totalOrig = activeReorderMaterial.page_count || 1;
  if (badge) {
    badge.textContent = `${currentReorderPages.length} von ${totalOrig} Seiten aktiv`;
  }

  grid.innerHTML = "";

  if (currentReorderPages.length === 0) {
    grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-secondary);">Keine Seiten mehr vorhanden. Klicke auf Zurücksetzen, um alle Seiten wiederherzustellen.</div>`;
    return;
  }

  currentReorderPages.forEach((origPage, idx) => {
    const card = document.createElement("div");
    card.className = "reorder-page-card";

    const isFirst = idx === 0;
    const isLast = idx === currentReorderPages.length - 1;

    card.innerHTML = `
      <div class="reorder-page-header">
        <span class="reorder-page-badge">Seite ${idx + 1}</span>
        <span class="reorder-orig-badge">(Orig. S. ${origPage})</span>
      </div>
      <div class="reorder-page-thumb-wrap">
        <img class="reorder-page-thumb" src="/api/v1/materials/${activeReorderMaterial.id}/preview?page=${origPage}" alt="Seite ${origPage}" loading="lazy">
      </div>
      <div class="reorder-card-actions">
        <button type="button" class="reorder-btn reorder-btn-left" title="Nach links verschieben" ${isFirst ? "disabled" : ""}>◀</button>
        <button type="button" class="reorder-btn reorder-btn-del" title="Diese Seite entfernen" ${currentReorderPages.length <= 1 ? "disabled" : ""}>🗑️</button>
        <button type="button" class="reorder-btn reorder-btn-right" title="Nach rechts verschieben" ${isLast ? "disabled" : ""}>▶</button>
      </div>
    `;

    const leftBtn = card.querySelector(".reorder-btn-left");
    if (leftBtn) {
      leftBtn.onclick = () => {
        if (idx > 0) {
          const temp = currentReorderPages[idx];
          currentReorderPages[idx] = currentReorderPages[idx - 1];
          currentReorderPages[idx - 1] = temp;
          renderReorderPagesGrid();
        }
      };
    }

    const rightBtn = card.querySelector(".reorder-btn-right");
    if (rightBtn) {
      rightBtn.onclick = () => {
        if (idx < currentReorderPages.length - 1) {
          const temp = currentReorderPages[idx];
          currentReorderPages[idx] = currentReorderPages[idx + 1];
          currentReorderPages[idx + 1] = temp;
          renderReorderPagesGrid();
        }
      };
    }

    const delBtn = card.querySelector(".reorder-btn-del");
    if (delBtn) {
      delBtn.onclick = () => {
        if (currentReorderPages.length > 1) {
          currentReorderPages.splice(idx, 1);
          renderReorderPagesGrid();
        } else {
          alert("Ein Dokument muss mindestens eine Seite behalten.");
        }
      };
    }

    grid.appendChild(card);
  });
}

if (btnReorderReset) {
  btnReorderReset.addEventListener("click", () => {
    if (activeReorderMaterial) {
      const count = activeReorderMaterial.page_count || 1;
      currentReorderPages = Array.from({ length: count }, (_, i) => i + 1);
      renderReorderPagesGrid();
    }
  });
}

if (btnCloseReorderModal) btnCloseReorderModal.addEventListener("click", closeReorderPagesModal);
if (modalReorderPages) {
  modalReorderPages.addEventListener("click", (e) => {
    if (e.target === modalReorderPages) closeReorderPagesModal();
  });
}

if (btnSaveReorderPages) {
  btnSaveReorderPages.addEventListener("click", async () => {
    if (!activeReorderMaterial || currentReorderPages.length === 0) return;

    btnSaveReorderPages.disabled = true;
    btnSaveReorderPages.textContent = "Speichere Seiten...";

    try {
      const res = await fetch(`/api/v1/materials/${activeReorderMaterial.id}/reorder-pages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page_order: currentReorderPages })
      });

      if (res.ok) {
        const updatedMat = await res.json();
        closeReorderPagesModal();
        await refreshAllMaterialViews();
        if (activeViewerMaterial && activeViewerMaterial.id === updatedMat.id) {
          activeViewerMaterial.page_count = updatedMat.page_count;
          if (currentViewerPage > updatedMat.page_count) currentViewerPage = updatedMat.page_count;
          renderViewerPage();
        }
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Fehler beim Speichern der Seitenreihenfolge: ${err.detail || "Unbekannter Fehler"}`);
      }
    } catch (e) {
      console.error(e);
      alert("Netzwerkfehler beim Speichern der Seitenreihenfolge.");
    } finally {
      btnSaveReorderPages.disabled = false;
      btnSaveReorderPages.textContent = "💾 Neue Reihenfolge speichern";
    }
  });
}

// --- 3. Merge Materials Modal (Dokumente zusammenführen) ---
let mergeSelectedDocIds = [];
const modalMergeMaterials = document.getElementById("modal-merge-materials");
const btnCloseMergeModal = document.getElementById("btn-close-merge-modal");
const mergeFilterSubject = document.getElementById("merge-filter-subject");
const mergeTargetSubject = document.getElementById("merge-target-subject");
const mergeTargetTopic = document.getElementById("merge-target-topic");
const btnSubmitMerge = document.getElementById("btn-submit-merge");

function updateMergeTargetTopicOptions(subjectId) {
  if (!mergeTargetTopic) return;
  mergeTargetTopic.innerHTML = '<option value="">-- Kein Thema --</option>';
  const topics = allTopicsCache.filter((t) => t.subject_id === subjectId);
  topics.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = `${t.name} (Stufe ${t.rlp_level_code || "E"})`;
    mergeTargetTopic.appendChild(opt);
  });
}

function openMergeMaterialsModal(preselectedSubjectId = null) {
  if (!modalMergeMaterials) return;
  mergeSelectedDocIds = [];

  // Filter dropdown
  if (mergeFilterSubject) {
    mergeFilterSubject.innerHTML = '<option value="all">Alle Fächer</option>' +
      currentSubjects.map((s) => `<option value="${s.id}">${s.icon || "📚"} ${escapeHtml(s.name)}</option>`).join("");
    if (preselectedSubjectId) {
      mergeFilterSubject.value = preselectedSubjectId;
    } else {
      mergeFilterSubject.value = "all";
    }
    mergeFilterSubject.onchange = renderMergeAvailableDocs;
  }

  // Target subject dropdown
  if (mergeTargetSubject) {
    mergeTargetSubject.innerHTML = currentSubjects
      .map((s) => `<option value="${s.id}" ${s.id === preselectedSubjectId ? "selected" : ""}>${s.icon || "📚"} ${escapeHtml(s.name)}</option>`)
      .join("");
    const chosenSubject = preselectedSubjectId || (currentSubjects[0] ? currentSubjects[0].id : "");
    updateMergeTargetTopicOptions(chosenSubject);
    mergeTargetSubject.onchange = () => {
      updateMergeTargetTopicOptions(mergeTargetSubject.value);
    };
  }

  const titleInput = document.getElementById("merge-target-title");
  if (titleInput) {
    const todayStr = new Date().toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
    titleInput.value = `Zusammenfassung (${todayStr})`;
  }

  renderMergeAvailableDocs();
  renderMergeOrderList();
  modalMergeMaterials.style.display = "flex";
}

function closeMergeMaterialsModal() {
  if (modalMergeMaterials) modalMergeMaterials.style.display = "none";
  mergeSelectedDocIds = [];
}

function renderMergeAvailableDocs() {
  const container = document.getElementById("merge-available-list");
  if (!container) return;
  container.innerHTML = "";

  const filterSubjectId = mergeFilterSubject ? mergeFilterSubject.value : "all";
  const docs = currentMaterials.filter((m) => {
    if (filterSubjectId === "all") return true;
    return m.subject_id === filterSubjectId;
  });

  if (docs.length === 0) {
    container.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 0.85rem;">Keine Dokumente für diese Auswahl gefunden.</div>`;
    return;
  }

  docs.forEach((m) => {
    const isSelected = mergeSelectedDocIds.includes(m.id);
    const item = document.createElement("div");
    item.className = `merge-doc-item ${isSelected ? "selected" : ""}`;

    item.innerHTML = `
      <input type="checkbox" style="pointer-events: none;" ${isSelected ? "checked" : ""}>
      <div class="merge-doc-info">
        <div class="merge-doc-title">${escapeHtml(m.title)}</div>
        <div class="merge-doc-meta">
          <span>${m.subject_icon || "📚"} ${escapeHtml(m.subject_name || "Fach")}</span>
          <span>• ${m.kind || "Dokument"}</span>
          <span>• ${m.page_count} S.</span>
        </div>
      </div>
    `;

    item.onclick = () => {
      const idx = mergeSelectedDocIds.indexOf(m.id);
      if (idx >= 0) {
        mergeSelectedDocIds.splice(idx, 1);
      } else {
        mergeSelectedDocIds.push(m.id);
      }
      renderMergeAvailableDocs();
      renderMergeOrderList();
    };

    container.appendChild(item);
  });
}

function renderMergeOrderList() {
  const container = document.getElementById("merge-order-list");
  const countBadge = document.getElementById("merge-selected-count");
  if (!container) return;

  if (countBadge) countBadge.textContent = mergeSelectedDocIds.length;
  container.innerHTML = "";

  if (mergeSelectedDocIds.length === 0) {
    container.innerHTML = `<div class="merge-empty-state">Wähle links mindestens 2 Dokumente aus</div>`;
    return;
  }

  mergeSelectedDocIds.forEach((id, idx) => {
    const m = currentMaterials.find((doc) => doc.id === id);
    if (!m) return;

    const isFirst = idx === 0;
    const isLast = idx === mergeSelectedDocIds.length - 1;

    const row = document.createElement("div");
    row.className = "merge-order-item";
    row.innerHTML = `
      <div class="merge-order-index">#${idx + 1}</div>
      <div class="merge-doc-info">
        <div class="merge-doc-title">${escapeHtml(m.title)}</div>
        <div class="merge-doc-meta">${m.page_count} S. • ${m.subject_icon || ""} ${escapeHtml(m.subject_name || "")}</div>
      </div>
      <div class="merge-order-actions">
        <button type="button" class="merge-order-btn btn-merge-up" title="Nach oben" ${isFirst ? "disabled" : ""}>▲</button>
        <button type="button" class="merge-order-btn btn-merge-down" title="Nach unten" ${isLast ? "disabled" : ""}>▼</button>
        <button type="button" class="merge-order-btn btn-merge-remove" title="Aus Auswahl entfernen">✕</button>
      </div>
    `;

    const upBtn = row.querySelector(".btn-merge-up");
    if (upBtn) {
      upBtn.onclick = (e) => {
        e.stopPropagation();
        if (idx > 0) {
          const temp = mergeSelectedDocIds[idx];
          mergeSelectedDocIds[idx] = mergeSelectedDocIds[idx - 1];
          mergeSelectedDocIds[idx - 1] = temp;
          renderMergeOrderList();
        }
      };
    }

    const downBtn = row.querySelector(".btn-merge-down");
    if (downBtn) {
      downBtn.onclick = (e) => {
        e.stopPropagation();
        if (idx < mergeSelectedDocIds.length - 1) {
          const temp = mergeSelectedDocIds[idx];
          mergeSelectedDocIds[idx] = mergeSelectedDocIds[idx + 1];
          mergeSelectedDocIds[idx + 1] = temp;
          renderMergeOrderList();
        }
      };
    }

    const remBtn = row.querySelector(".btn-merge-remove");
    if (remBtn) {
      remBtn.onclick = (e) => {
        e.stopPropagation();
        mergeSelectedDocIds.splice(idx, 1);
        renderMergeAvailableDocs();
        renderMergeOrderList();
      };
    }

    container.appendChild(row);
  });
}

if (btnCloseMergeModal) btnCloseMergeModal.addEventListener("click", closeMergeMaterialsModal);
if (modalMergeMaterials) {
  modalMergeMaterials.addEventListener("click", (e) => {
    if (e.target === modalMergeMaterials) closeMergeMaterialsModal();
  });
}

if (btnSubmitMerge) {
  btnSubmitMerge.addEventListener("click", async () => {
    if (mergeSelectedDocIds.length < 2) {
      alert("Bitte wähle mindestens 2 Dokumente zum Zusammenführen aus.");
      return;
    }

    const title = document.getElementById("merge-target-title").value.trim();
    const subjectId = mergeTargetSubject ? mergeTargetSubject.value : null;
    const topicId = mergeTargetTopic ? (mergeTargetTopic.value || null) : null;
    const kind = document.getElementById("merge-target-kind").value;
    const deleteSources = document.getElementById("merge-delete-sources").checked;

    if (!title) {
      alert("Bitte gib einen Titel für das zusammengeführte Dokument an.");
      return;
    }
    if (!subjectId) {
      alert("Bitte wähle ein Schulfach aus.");
      return;
    }

    btnSubmitMerge.disabled = true;
    btnSubmitMerge.textContent = "Verbinde Dokumente...";

    try {
      const res = await fetch("/api/v1/materials/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_material_ids: mergeSelectedDocIds,
          title,
          subject_id: subjectId,
          topic_id: topicId,
          kind,
          delete_sources: deleteSources
        })
      });

      if (res.ok) {
        closeMergeMaterialsModal();
        await refreshAllMaterialViews();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Fehler beim Zusammenführen: ${err.detail || "Unbekannter Fehler"}`);
      }
    } catch (e) {
      console.error(e);
      alert("Netzwerkfehler beim Zusammenführen der Dokumente.");
    } finally {
      btnSubmitMerge.disabled = false;
      btnSubmitMerge.textContent = "🔗 Dokumente zusammenführen";
    }
  });
}

// Toolbar-Buttons für Zusammenführen
const btnUploadsMerge = document.getElementById("btn-open-uploads-merge-modal");
if (btnUploadsMerge) {
  btnUploadsMerge.addEventListener("click", () => {
    openMergeMaterialsModal();
  });
}

const btnSubjectMerge = document.getElementById("btn-open-subject-merge-modal");
if (btnSubjectMerge) {
  btnSubjectMerge.addEventListener("click", () => {
    openMergeMaterialsModal(currentDetailSubjectId);
  });
}

// ==========================================================================
// Timetable Import Subsystem
// ==========================================================================

const btnOpenTimetableModal = document.getElementById("btn-open-timetable-modal");
const timetableFileInput = document.getElementById("timetable-file-input");
const modalTimetableResult = document.getElementById("modal-timetable-result");
const btnCloseTimetableModal = document.getElementById("btn-close-timetable-modal");
const btnTtConfirmClose = document.getElementById("btn-tt-confirm-close");
const btnTtErrorClose = document.getElementById("btn-tt-error-close");

const ttLoadingState = document.getElementById("tt-loading-state");
const ttResultState = document.getElementById("tt-result-state");
const ttErrorState = document.getElementById("tt-error-state");
const ttResultStatusTitle = document.getElementById("tt-result-status-title");
const ttResultDocName = document.getElementById("tt-result-doc-name");
const ttAddedSubjectsList = document.getElementById("tt-added-subjects-list");
const ttAllSubjectsList = document.getElementById("tt-all-subjects-list");
const ttErrorTitle = document.getElementById("tt-error-title");
const ttErrorDetail = document.getElementById("tt-error-detail");

function openTimetableModal() {
  if (timetableFileInput) timetableFileInput.click();
}

function closeTimetableModal() {
  if (modalTimetableResult) modalTimetableResult.style.display = "none";
}

if (btnOpenTimetableModal) {
  btnOpenTimetableModal.addEventListener("click", openTimetableModal);
}
if (btnCloseTimetableModal) {
  btnCloseTimetableModal.addEventListener("click", closeTimetableModal);
}
if (btnTtConfirmClose) {
  btnTtConfirmClose.addEventListener("click", closeTimetableModal);
}
if (btnTtErrorClose) {
  btnTtErrorClose.addEventListener("click", closeTimetableModal);
}
if (modalTimetableResult) {
  modalTimetableResult.addEventListener("click", (e) => {
    if (e.target === modalTimetableResult && (!ttLoadingState || ttLoadingState.style.display !== "block")) {
      closeTimetableModal();
    }
  });
}

if (timetableFileInput) {
  timetableFileInput.addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    if (modalTimetableResult) {
      modalTimetableResult.style.display = "flex";
      if (ttLoadingState) ttLoadingState.style.display = "block";
      if (ttResultState) ttResultState.style.display = "none";
      if (ttErrorState) ttErrorState.style.display = "none";
    }

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/v1/taxonomy/import-timetable", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Serverfehler HTTP ${res.status}`);
      }

      const data = await res.json();

      if (ttLoadingState) ttLoadingState.style.display = "none";
      if (ttErrorState) ttErrorState.style.display = "none";
      if (ttResultState) ttResultState.style.display = "block";

      const newlyAddedCount = (data.created_subjects || []).length;
      if (ttResultStatusTitle) {
        if (!data.slots_imported) {
          ttResultStatusTitle.textContent = "⚠️ Wochenraster nicht erkannt – Stundenplan unverändert";
        } else if (newlyAddedCount > 0) {
          ttResultStatusTitle.textContent = `🎉 ${data.slots_imported} Stunden übernommen, ${newlyAddedCount} neue(s) Fach/Fächer angelegt!`;
        } else {
          ttResultStatusTitle.textContent = `✅ Stundenplan übernommen: ${data.slots_imported} Stunden`;
        }
      }

      const matTitle = (data.material && data.material.title) || data.material_title || data.filename || "";
      if (ttResultDocName && matTitle) {
        let docText = `Dokument „${matTitle}“ als Stundenplan einsortiert.`;
        const grid = data.timetable_grid || {};
        if (grid.wochentyp || grid.hat_wechselwochen) {
          const wochenLabel = grid.wochentyp || "A/B-Wechselwochen";
          docText += ` (${wochenLabel} – Fächer beider Wochen übernommen)`;
        }
        if (grid.wechsel_details) {
          docText += `<div style="margin-top: 6px; font-size: 0.8rem; color: var(--accent-light);">🔄 ${grid.wechsel_details}</div>`;
        }
        ttResultDocName.innerHTML = docText;
      }

      // Render added subjects
      if (ttAddedSubjectsList) {
        ttAddedSubjectsList.innerHTML = "";
        if (data.created_subjects && data.created_subjects.length > 0) {
          data.created_subjects.forEach((s) => {
            const pill = document.createElement("span");
            pill.className = "mat-card-badge";
            pill.style.background = "rgba(16, 185, 129, 0.2)";
            pill.style.color = "#10b981";
            pill.style.border = "1px solid rgba(16, 185, 129, 0.4)";
            pill.style.padding = "4px 10px";
            pill.style.fontSize = "0.85rem";
            pill.textContent = `✨ ${s.icon || "📚"} ${s.name || ""}`.trim();
            ttAddedSubjectsList.appendChild(pill);
          });
        } else {
          ttAddedSubjectsList.innerHTML = `<span style="font-size: 0.85rem; color: var(--text-secondary); font-style: italic;">Alle erkannten Schulfächer existierten bereits in deiner Fächerliste.</span>`;
        }
      }

      // Render all detected subjects
      if (ttAllSubjectsList) {
        ttAllSubjectsList.innerHTML = "";
        // Kombiniere neu angelegte und bereits existierende Fächer (enthalten vollständige Subject-Objekte mit icon & name)
        const allRecognized = [...(data.created_subjects || []), ...(data.existing_subjects || [])];
        const listToDisplay = allRecognized.length > 0 ? allRecognized : (data.detected_subjects || []);

        if (listToDisplay.length > 0) {
          listToDisplay.forEach((s) => {
            const pill = document.createElement("span");
            pill.className = "mat-card-badge";
            pill.style.background = "rgba(99, 102, 241, 0.15)";
            pill.style.color = "var(--accent-light)";
            pill.style.padding = "4px 10px";
            pill.style.fontSize = "0.85rem";
            if (typeof s === "object" && s !== null) {
              pill.textContent = `${s.icon || "📖"} ${s.name || ""}`.trim();
            } else {
              const matched = allRecognized.find((sub) => sub.name.toLowerCase() === String(s).toLowerCase());
              pill.textContent = matched ? `${matched.icon || "📖"} ${matched.name}` : `📖 ${s}`;
            }
            ttAllSubjectsList.appendChild(pill);
          });
        } else {
          ttAllSubjectsList.innerHTML = `<span style="font-size: 0.85rem; color: var(--text-secondary); font-style: italic;">Keine Fächerkürzel erkannt.</span>`;
        }
      }

      // Refresh taxonomy, materials and timetable across the whole app
      await loadTaxonomy();
      await loadMaterials();
      await loadTimetable();
      await loadTodayDashboardWidget();

    } catch (err) {
      console.error("Fehler beim Import des Stundenplans:", err);
      if (ttLoadingState) ttLoadingState.style.display = "none";
      if (ttResultState) ttResultState.style.display = "none";
      if (ttErrorState) ttErrorState.style.display = "block";
      if (ttErrorTitle) ttErrorTitle.textContent = "Import fehlgeschlagen";
      if (ttErrorDetail) ttErrorDetail.textContent = err.message || "Unbekannter Fehler bei der Übertragung.";
    } finally {
      timetableFileInput.value = "";
    }
  });
}

// ==============================================================================
// STUNDENPLAN-WIDGET & VOLLBILD-VERWALTUNG
// ==============================================================================

let currentTimetableWeek = "A";
let currentTimetableData = null;

async function loadTimetable(forcedWeek = null) {
  try {
    const weekParam = forcedWeek || currentTimetableWeek;
    const res = await fetch(`/api/v1/timetable?week_type=${weekParam}`);
    if (!res.ok) throw new Error("Fehler beim Laden des Stundenplans.");
    currentTimetableData = await res.json();
    currentTimetableWeek = currentTimetableData.current_week_type || "A";

    // Header aktualisieren
    const subtitleEl = document.getElementById("tt-view-subtitle");
    if (subtitleEl) {
      subtitleEl.textContent = currentTimetableData.class_name || "Klasse 7D";
      subtitleEl.title = `${currentTimetableData.school_name || ""} • Schuljahr ${currentTimetableData.school_year || ""}`.trim();
    }

    // A/B Buttons Status setzen
    const btnA = document.getElementById("btn-tt-week-a");
    const btnB = document.getElementById("btn-tt-week-b");
    const autoWeekTag = document.getElementById("tt-auto-week-tag");
    if (btnA && btnB) {
      if (currentTimetableWeek === "A") {
        btnA.classList.add("active");
        btnB.classList.remove("active");
      } else {
        btnB.classList.add("active");
        btnA.classList.remove("active");
      }
    }
    if (autoWeekTag) {
      autoWeekTag.textContent = `Aktiv: ${currentTimetableWeek}-Woche`;
    }

    // Differenzen Text
    const diffEl = document.getElementById("tt-differences-text");
    if (diffEl && currentTimetableData.week_differences && currentTimetableData.week_differences.length > 0) {
      diffEl.textContent = currentTimetableData.week_differences.join(" • ");
    }

    renderTimetableGrid();
  } catch (err) {
    console.error("Fehler beim Laden des Stundenplans:", err);
  }
}

function renderTimetableGrid() {
  const gridEl = document.getElementById("timetable-full-grid");
  if (!gridEl || !currentTimetableData) return;

  gridEl.innerHTML = "";

  const weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"];
  const jsDay = new Date().getDay(); // 0 Sonntag, 1 Montag ... 5 Freitag
  const todayName = (jsDay >= 1 && jsDay <= 5) ? weekdays[jsDay - 1] : "Montag";

  // 1. Header-Zeile: Zeit + 5 Wochentage
  const timeHeader = document.createElement("div");
  timeHeader.className = "tt-grid-header tt-corner-header";
  timeHeader.innerHTML = `<span>Zeit</span>`;
  gridEl.appendChild(timeHeader);

  weekdays.forEach((day) => {
    const dayHeader = document.createElement("div");
    const isToday = (day === todayName);
    dayHeader.className = `tt-grid-header ${isToday ? "today" : ""}`;
    dayHeader.innerHTML = `
      <span>${day}</span>
      ${isToday ? `<span class="tt-today-badge">Heute</span>` : ""}
    `;
    gridEl.appendChild(dayHeader);
  });

  // 2. Zeilen für jede Unterrichtsstunde (1 bis 9)
  const periods = currentTimetableData.periods || [];
  const slots = currentTimetableData.slots || [];

  if (periods.length > 0) {
    gridEl.style.gridTemplateRows = `minmax(20px, 2.8vh) repeat(${periods.length}, minmax(0, 1fr))`;
  }

  periods.forEach((period) => {
    // A) Zeit-Zelle links
    const timeCell = document.createElement("div");
    timeCell.className = "tt-time-cell";
    const periodNumStr = (period.label || String(period.period)).replace(/\s*Std\.?/i, "").trim();
    timeCell.innerHTML = `
      <span class="tt-period-num">${escapeHtml(periodNumStr)}</span>
      <span class="tt-period-time">${escapeHtml(period.start_time || "")}</span>
    `;
    gridEl.appendChild(timeCell);

    // B) 5 Tageszellen
    weekdays.forEach((day) => {
      const isToday = (day === todayName);
      const slotCell = document.createElement("div");
      slotCell.className = `tt-slot-cell ${isToday ? "today-col" : ""}`;

      // Passenden Slot für diesen Tag & Stunde finden
      const matchingSlot = slots.find((s) => {
        return (
          s.day_of_week === day &&
          s.period === period.period &&
          (s.week_type === currentTimetableWeek || s.week_type === "both")
        );
      });

      if (matchingSlot) {
        if (matchingSlot.is_break) {
          const isLunch = (matchingSlot.subject_name || "").toLowerCase().includes("mittag") || (matchingSlot.subject_name || "").toLowerCase().includes("mensa");
          const breakIcon = isLunch ? "/static/Icons/Mittagspause.svg" : "/static/Icons/Pause.svg";
          slotCell.innerHTML = `
            <div class="tt-lesson-card tt-lesson-break" title="${escapeHtml(matchingSlot.subject_name || 'Pause')}">
              <img src="${breakIcon}" class="tt-break-svg" alt="">
              <span class="tt-break-label">${escapeHtml(matchingSlot.subject_name || "Pause")}</span>
            </div>
          `;
        } else {
          const card = document.createElement("div");
          card.className = "tt-lesson-card";
          if (matchingSlot.subject_color) {
            card.style.borderLeftColor = matchingSlot.subject_color;
          }

          let roomStr = matchingSlot.room || "";
          if (roomStr && !roomStr.toLowerCase().includes("halle") && !roomStr.startsWith("R")) {
            roomStr = `R ${roomStr}`;
          }

          card.innerHTML = `
            <div class="tt-lesson-top">
              <img src="${getSubjectIconUrl(matchingSlot.subject_name)}" class="tt-slot-svg" alt="">
              <span class="tt-lesson-name">${escapeHtml(matchingSlot.subject_name)}</span>
            </div>
            <div class="tt-lesson-meta">
              <span class="tt-lesson-room">${escapeHtml(roomStr)}</span>
              <span class="tt-lesson-teacher">${escapeHtml(matchingSlot.teacher || "")}</span>
            </div>
          `;

          card.addEventListener("click", () => {
            if (matchingSlot.subject_id) {
              openSubjectDetail(matchingSlot.subject_id, "timetable");
            } else {
              openTimetableSlotDetailModal(matchingSlot, period);
            }
          });
          slotCell.appendChild(card);
        }
      } else {
        slotCell.innerHTML = `<div class="tt-cell-empty">—</div>`;
      }

      gridEl.appendChild(slotCell);
    });
  });
}

// Modal für Fach-Detail aus Stundenplan
let activeDetailSlot = null;

function openTimetableSlotDetailModal(slot, period) {
  activeDetailSlot = slot;
  const modal = document.getElementById("modal-tt-slot-detail");
  if (!modal) return;

  const iconEl = document.getElementById("tt-slot-modal-icon");
  const titleEl = document.getElementById("tt-slot-modal-title");
  const timeEl = document.getElementById("tt-slot-modal-time");
  const roomEl = document.getElementById("tt-slot-modal-room");
  const teacherEl = document.getElementById("tt-slot-modal-teacher");
  const weekEl = document.getElementById("tt-slot-modal-week");
  const noteRow = document.getElementById("tt-slot-modal-note-row");
  const noteEl = document.getElementById("tt-slot-modal-note");

  if (iconEl) {
    iconEl.innerHTML = `<img src="${getSubjectIconUrl(slot.subject_name)}" style="width: 24px; height: 24px; filter: brightness(0) invert(1);" alt="">`;
  }
  if (titleEl) titleEl.textContent = slot.subject_name;
  if (timeEl) {
    const pLabel = slot.period_label || (period ? period.label : `${slot.period}. Std`);
    const sTime = slot.start_time || (period ? period.start_time : "");
    const eTime = slot.end_time || (period ? period.end_time : "");
    timeEl.textContent = `${slot.day_of_week} • ${pLabel} • ${sTime} – ${eTime}`;
  }
  if (roomEl) {
    let r = slot.room || "–";
    if (r !== "–" && !r.toLowerCase().includes("halle") && !r.startsWith("R")) r = `Raum ${r}`;
    roomEl.textContent = r;
  }
  if (teacherEl) teacherEl.textContent = slot.teacher || "–";
  if (weekEl) {
    weekEl.textContent = slot.week_type === "both" ? "Wöchentlich (A- & B-Woche)" : `${slot.week_type}-Woche`;
  }
  if (noteRow && noteEl) {
    if (slot.note) {
      noteRow.style.display = "flex";
      noteEl.textContent = slot.note;
    } else {
      noteRow.style.display = "none";
    }
  }

  modal.style.display = "flex";
}

function closeTimetableSlotDetailModal() {
  const modal = document.getElementById("modal-tt-slot-detail");
  if (modal) modal.style.display = "none";
  activeDetailSlot = null;
}

// Dashboard Heutiger Stundenplan Widget
async function loadTodayDashboardWidget() {
  const container = document.getElementById("dash-tt-slots-row");
  if (!container) return;

  try {
    const res = await fetch("/api/v1/timetable/today");
    if (!res.ok) throw new Error("Fehler beim Laden des Tagesplans.");
    const data = await res.json();

    const titleEl = document.getElementById("dash-tt-day-title");
    const weekPill = document.getElementById("dash-tt-week-pill");

    if (titleEl) {
      titleEl.textContent = data.is_weekend
        ? `Nächster Schultag (Montag)`
        : `Heute • ${data.day}`;
    }
    if (weekPill) {
      weekPill.textContent = `${data.active_week}-Woche`;
    }

    container.innerHTML = "";
    const lessons = (data.lessons || []).filter((l) => !l.is_break);

    if (lessons.length === 0) {
      container.innerHTML = `<div class="dash-tt-empty">Heute kein regulärer Unterricht eingetragen. 🎉</div>`;
      return;
    }

    lessons.forEach((l) => {
      const card = document.createElement("div");
      card.className = "dash-tt-slot-card";
      const subColor = l.subject_color || "var(--accent)";
      card.style.borderLeftColor = subColor;
      card.setAttribute("role", "button");
      card.setAttribute("tabindex", "0");
      card.setAttribute("title", `${l.subject_name} öffnen`);

      let roomStr = l.room || "";
      if (roomStr && !roomStr.toLowerCase().includes("halle") && !roomStr.startsWith("R")) {
        roomStr = `R ${roomStr}`;
      }

      card.innerHTML = `
        <div class="dash-tt-slot-top">
          <div class="dash-tt-slot-icon-wrap" style="background: ${subColor}20; border-color: ${subColor}40;">
            <img src="${getSubjectIconUrl(l.subject_name)}" class="dash-tt-slot-svg" alt="${escapeHtml(l.subject_name)}">
          </div>
          <span class="dash-tt-slot-time">${escapeHtml(l.period_label || l.period + '. Std')} • ${escapeHtml(l.start_time || "")}</span>
        </div>
        <div class="dash-tt-slot-subject">
          <span>${escapeHtml(l.subject_name)}</span>
        </div>
        <div class="dash-tt-slot-meta">
          ${roomStr ? `<span class="dash-tt-badge-room">${escapeHtml(roomStr)}</span>` : ""}
          ${l.teacher ? `<span class="dash-tt-badge-teacher">${escapeHtml(l.teacher)}</span>` : ""}
        </div>
      `;

      const handleSlotOpen = () => {
        if (l.subject_id) {
          openSubjectDetail(l.subject_id, "dashboard");
        } else {
          switchToTab("timetable");
        }
      };

      card.addEventListener("click", handleSlotOpen);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleSlotOpen();
        }
      });

      container.appendChild(card);
    });
  } catch (err) {
    console.error("Fehler beim Laden des Dashboard-Stundenplans:", err);
  }
}

async function viewMaterialById(matId) {
  try {
    const res = await fetch(`/api/v1/materials/${matId}`);
    if (res.ok) {
      const mat = await res.json();
      openDocumentViewerModal(mat);
    }
  } catch (err) {
    console.error("Fehler beim Laden des Dokuments:", err);
  }
}

// Event Listeners für Stundenplan
const btnTtWeekA = document.getElementById("btn-tt-week-a");
const btnTtWeekB = document.getElementById("btn-tt-week-b");
const btnTtViewScan = document.getElementById("btn-tt-view-scan");
const btnTtUploadNew = document.getElementById("btn-tt-upload-new");
const btnDashGotoTt = document.getElementById("btn-dash-goto-timetable");
const btnCloseTtSlotModal = document.getElementById("btn-close-tt-slot-modal");
const btnTtGotoMaterials = document.getElementById("btn-tt-goto-materials");
const btnTtGotoWb = document.getElementById("btn-tt-goto-whiteboard");

if (btnTtWeekA) {
  btnTtWeekA.addEventListener("click", () => {
    currentTimetableWeek = "A";
    btnTtWeekA.classList.add("active");
    if (btnTtWeekB) btnTtWeekB.classList.remove("active");
    renderTimetableGrid();
  });
}

if (btnTtWeekB) {
  btnTtWeekB.addEventListener("click", () => {
    currentTimetableWeek = "B";
    btnTtWeekB.classList.add("active");
    if (btnTtWeekA) btnTtWeekA.classList.remove("active");
    renderTimetableGrid();
  });
}

if (btnTtViewScan) {
  btnTtViewScan.addEventListener("click", () => {
    if (currentTimetableData && currentTimetableData.scan_material_id) {
      viewMaterialById(currentTimetableData.scan_material_id);
    } else {
      alert("Es wurde noch kein Original-Scan hochgeladen. Du kannst oben auf 'Plan aktualisieren' klicken.");
    }
  });
}

if (btnTtUploadNew) {
  btnTtUploadNew.addEventListener("click", () => {
    const fileIn = document.getElementById("timetable-file-input");
    if (fileIn) fileIn.click();
  });
}

if (btnDashGotoTt) {
  btnDashGotoTt.addEventListener("click", () => {
    switchToTab("timetable");
  });
}

if (btnCloseTtSlotModal) {
  btnCloseTtSlotModal.addEventListener("click", closeTimetableSlotDetailModal);
}

const modalTtSlotDetail = document.getElementById("modal-tt-slot-detail");
if (modalTtSlotDetail) {
  modalTtSlotDetail.addEventListener("click", (e) => {
    if (e.target === modalTtSlotDetail) closeTimetableSlotDetailModal();
  });
}

if (btnTtGotoMaterials) {
  btnTtGotoMaterials.addEventListener("click", () => {
    if (!activeDetailSlot) return;
    const sId = activeDetailSlot.subject_id;
    closeTimetableSlotDetailModal();
    if (sId) {
      openSubjectDetail(sId, "timetable");
    } else {
      switchToTab("dashboard");
    }
  });
}

if (btnTtGotoWb) {
  btnTtGotoWb.addEventListener("click", () => {
    if (!activeDetailSlot) return;
    const sId = activeDetailSlot.subject_id;
    closeTimetableSlotDetailModal();
    switchToTab("whiteboard");
    const wbSelect = document.getElementById("wb-subject-select");
    if (wbSelect && sId) {
      wbSelect.value = sId;
      wbSelect.dispatchEvent(new Event("change"));
    }
  });
}

// ==========================================================================
// 📖 BÜCHER-BROWSER LOGIK (#tab-books)
// ==========================================================================

let currentBooks = [];
let activeBookId = null;
let activeBookDetail = null;
let activeChapter = null;
let currentChapterPage = 1;
let bookZoomMode = "width"; // Standard: Volle Dokumentbreite (100% Breite)

async function loadBooks() {
  try {
    const res = await fetch("/api/v1/books");
    if (!res.ok) {
      console.error("HTTP error loading books:", res.status);
      const grid = document.getElementById("book-catalog-grid");
      if (grid && currentBooks.length === 0) {
        grid.innerHTML = `
          <div class="empty-state-card" style="grid-column: 1 / -1; padding: 48px 24px; text-align: center; background: rgba(239, 68, 68, 0.05); border: 1px dashed rgba(239, 68, 68, 0.3); border-radius: 16px; margin: 20px 0;">
            <div style="font-size: 2.5rem; margin-bottom: 12px;">⚠️</div>
            <h3 style="margin-bottom: 6px; color: #ef4444;">Lehrbücher konnten nicht geladen werden</h3>
            <p style="color: var(--text-secondary); max-width: 480px; margin: 0 auto 20px; font-size: 0.9rem;">
              Beim Abrufen der Bücher ist ein Serverfehler aufgetreten (${res.status}).
            </p>
            <button onclick="loadBooks()" class="btn-primary-sm">🔄 Erneut versuchen</button>
          </div>
        `;
      }
      return;
    }
    currentBooks = await res.json();
    renderBooksShelf();

    const toolbar = document.getElementById("book-catalog-toolbar");
    const grid = document.getElementById("book-catalog-grid");

    if (currentBooks.length === 0) {
      if (toolbar) toolbar.style.display = "none";
      if (grid) {
        grid.innerHTML = `
          <div class="empty-state-card" style="grid-column: 1 / -1; padding: 48px 24px; text-align: center; background: rgba(255, 255, 255, 0.02); border: 1px dashed var(--border-color); border-radius: 16px; margin: 20px 0;">
            <div style="font-size: 3rem; margin-bottom: 12px;">📚</div>
            <h3 style="margin-bottom: 6px;">Noch keine Schulbücher hinterlegt</h3>
            <p style="color: var(--text-secondary); max-width: 480px; margin: 0 auto 20px; font-size: 0.9rem;">
              Sobald Lehrwerke hochgeladen oder importiert werden, kannst du hier interaktiv durch alle Kapitel und Seiten navigieren.
            </p>
            <button id="btn-books-goto-upload" class="btn-primary-sm" style="display: inline-flex; align-items: center; gap: 8px;">
              <span>📤</span>
              <span>Schulbuch hochladen</span>
            </button>
          </div>
        `;
        const btnUpload = document.getElementById("btn-books-goto-upload");
        if (btnUpload) {
          btnUpload.addEventListener("click", () => switchToTab("uploads"));
        }
      }
      return;
    }

    if (toolbar) toolbar.style.display = "flex";

    if (currentBooks.length > 0) {
      if (!activeBookId || !currentBooks.some(b => b.id === activeBookId)) {
        await selectBook(currentBooks[0].id);
      } else {
        await selectBook(activeBookId);
      }
    }
  } catch (err) {
    console.error("Fehler beim Laden der Schulbücher:", err);
  }
}

function renderBooksShelf() {
  const container = document.getElementById("books-shelf-selector");
  if (!container) return;
  container.innerHTML = "";

  currentBooks.forEach((book) => {
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = `shelf-book-pill ${book.id === activeBookId ? "active" : ""}`;
    pill.dataset.bookId = book.id;
    pill.innerHTML = `
      <span class="shelf-book-icon">${book.subject_icon || "📚"}</span>
      <span class="shelf-book-title">${escapeHtml(book.title)}</span>
      <span class="shelf-book-badge">${book.chapters_count} Kap. • ${book.total_pages} S.</span>
    `;
    pill.addEventListener("click", () => selectBook(book.id));
    container.appendChild(pill);
  });
}

async function selectBook(bookId) {
  activeBookId = bookId;
  renderBooksShelf();

  try {
    const res = await fetch(`/api/v1/books/${bookId}`);
    if (!res.ok) return;
    activeBookDetail = await res.json();

    // Katalog-Header befüllen
    const iconEl = document.getElementById("catalog-book-icon");
    const titleEl = document.getElementById("catalog-book-title");
    const subEl = document.getElementById("catalog-book-subtitle");
    const drawerSubEl = document.getElementById("drawer-book-subtitle");

    if (iconEl) iconEl.textContent = activeBookDetail.subject_icon || "📚";
    if (titleEl) titleEl.textContent = activeBookDetail.title;
    if (subEl) subEl.textContent = `${activeBookDetail.chapters_count} Lerneinheiten • ${activeBookDetail.total_pages} Seiten`;
    if (drawerSubEl) drawerSubEl.textContent = activeBookDetail.title;

    // Standardmäßig Katalog anzeigen (oder Reader aktualisieren falls bereits geöffnet)
    const readerView = document.getElementById("book-reader-view");
    const isReaderOpen = readerView && readerView.style.display !== "none";

    renderBookCatalog();
    renderDrawerTOC();

    if (isReaderOpen && activeChapter) {
      // Wenn das Buch gewechselt wurde während der Reader offen war, selbes Kapitel oder erstes Kapitel laden
      const chaps = activeBookDetail.chapters || [];
      const sameChap = chaps.find(c => c.id === activeChapter.id);
      if (sameChap) {
        openChapter(sameChap, currentChapterPage);
      } else {
        const newChap = chaps.find(c => c.chapter_number === 1) || chaps[0];
        if (newChap) openChapter(newChap, 1);
      }
    }
  } catch (err) {
    console.error("Fehler beim Abruf der Buch-Details:", err);
  }
}

// Ansicht 1: Übersicht aller Kapitel / Lerneinheiten als Kacheln (Progressive Disclosure)
function renderBookCatalog(filterTerm = "") {
  const container = document.getElementById("book-catalog-grid");
  if (!container || !activeBookDetail) return;
  container.innerHTML = "";

  const term = (filterTerm || "").toLowerCase().trim();
  const chapters = (activeBookDetail.chapters || []).filter((ch) => {
    if (!term) return true;
    const hasSectionMatch = (ch.sections || []).some(
      (s) =>
        s.title.toLowerCase().includes(term) ||
        String(s.book_page).includes(term)
    );
    return (
      ch.title.toLowerCase().includes(term) ||
      (ch.topic_name && ch.topic_name.toLowerCase().includes(term)) ||
      (ch.focus && ch.focus.toLowerCase().includes(term)) ||
      hasSectionMatch
    );
  });

  if (chapters.length === 0) {
    container.innerHTML = `
      <div style="padding: 36px; text-align: center; color: var(--text-muted); font-size: 0.95rem; background: var(--bg-card); border-radius: 14px; border: 1px solid var(--border-color); width: 100%;">
        <p style="margin-bottom: 16px;">${filterTerm ? `Keine Lerneinheiten für "${escapeHtml(filterTerm)}" gefunden.` : "Für dieses Lehrwerk wurden noch keine separaten Lerneinheiten aufgeteilt."}</p>
        <button type="button" class="btn-primary" id="btn-open-full-book-fallback" style="margin: 0 auto; display: inline-flex; align-items: center; gap: 8px;">
          <span>📖</span>
          <span>Gesamtes Buch aufschlagen (${activeBookDetail.total_pages} Seiten)</span>
        </button>
      </div>
    `;
    const openBtn = document.getElementById("btn-open-full-book-fallback");
    if (openBtn) {
      openBtn.addEventListener("click", () => {
        openChapter({
          id: activeBookDetail.id,
          chapter_number: 0,
          title: activeBookDetail.title,
          start_page: 1,
          end_page: activeBookDetail.total_pages,
          page_count: activeBookDetail.total_pages,
          focus: activeBookDetail.summary || "Gesamtes Lehrwerk",
          file_url: `/api/v1/materials/${activeBookDetail.id}/file`,
          filename: `${activeBookDetail.title}.pdf`
        }, 1);
      });
    }
    return;
  }

  chapters.forEach((ch) => {
    const item = document.createElement("div");
    item.className = "book-toc-item";
    item.dataset.chapterId = ch.id;

    const isSingleFullBook = ch.id === activeBookDetail.id;
    const numDisplay = isSingleFullBook
      ? "★"
      : (ch.chapter_number === 0 ? "00" : String(ch.chapter_number).padStart(2, "0"));
    const unitLabel = isSingleFullBook
      ? "Gesamtbuch"
      : (ch.chapter_number === 0 ? "Titelei & Inhaltsverzeichnis" : `Einheit ${ch.chapter_number}`);

    let sectionsHtml = "";
    if (ch.sections && ch.sections.length > 0) {
      const hasSecMatch = Boolean(term && ch.sections.some(s => s.title.toLowerCase().includes(term) || String(s.book_page).includes(term)));
      sectionsHtml = `
        <details class="toc-subsections-accordion" ${hasSecMatch ? "open" : ""} onclick="event.stopPropagation()">
          <summary class="toc-summary">
            <span class="toc-summary-label">📑 ${ch.sections.length} Unterthemen & Abschnitte</span>
            <span class="toc-chevron">▾</span>
          </summary>
          <div class="toc-subsections-grid">
            ${ch.sections.map(sec => `
              <button type="button" class="toc-sub-pill" data-target-page="${sec.relative_page}" title="Direkt aufschlagen: ${escapeHtml(sec.title)} (Buchseite ${sec.book_page})">
                <span class="toc-sub-title">${escapeHtml(sec.title)}</span>
                <span class="toc-sub-page">S. ${sec.book_page}</span>
              </button>
            `).join("")}
          </div>
        </details>
      `;
    }

    item.innerHTML = `
      <div class="toc-num-badge" title="${unitLabel}">
        ${numDisplay}
      </div>
      <div class="toc-item-main">
        <div class="toc-title-row">
          <div class="toc-item-title">${escapeHtml(ch.title)}</div>
        </div>
        <div class="toc-meta-row">
          <span class="toc-badge-pages">📄 S. ${ch.start_page}–${ch.end_page} (${ch.page_count} S.)</span>
          ${ch.topic_name ? `<span class="toc-badge-topic">📐 ${escapeHtml(ch.topic_name)}</span>` : ""}
          ${isSingleFullBook ? `<span class="toc-badge-topic">⭐ Vollständige Ausgabe</span>` : ""}
        </div>
        ${sectionsHtml}
      </div>
      <div class="toc-item-action">
        <button type="button" class="btn-toc-open">
          <span>${isSingleFullBook ? "Gesamtbuch öffnen" : "Aufschlagen"}</span>
          <span>→</span>
        </button>
      </div>
    `;

    // Klicken auf die Zeile öffnet das Kapitel ab Seite 1
    item.addEventListener("click", () => openChapter(ch, 1));

    // Klicken auf einzelne Unterseiten springt direkt zu dieser Seite
    item.querySelectorAll(".toc-sub-pill").forEach(pill => {
      pill.addEventListener("click", (e) => {
        e.stopPropagation();
        const p = parseInt(pill.dataset.targetPage, 10) || 1;
        openChapter(ch, p);
      });
    });

    container.appendChild(item);
  });
}

// Ansicht 2: Vollbreiten-Reader für ein gewähltes Kapitel öffnen
function openChapter(ch, targetPage = 1) {
  if (!ch) return;
  activeChapter = ch;
  currentChapterPage = Math.max(1, Math.min(ch.page_count, targetPage || 1));

  // Umschalten auf Reader-Ansicht & Zen-Mode aktivieren (100% Bildschirm fürs Buch)
  const catalogView = document.getElementById("book-catalog-view");
  const readerView = document.getElementById("book-reader-view");
  if (catalogView) catalogView.style.display = "none";
  if (readerView) readerView.style.display = "flex";
  document.body.classList.add("reader-zen-mode");

  // Ultraschlanke Kopfzeile (Vorschlag 1)
  const titleSlim = document.getElementById("reader-chapter-title-slim");
  const counterSlim = document.getElementById("reader-page-counter-slim");
  const downloadBtn = document.getElementById("btn-book-download-pdf");

  if (titleSlim) {
    const unitLabel = ch.chapter_number === 0 ? "Titelei" : `Einheit ${ch.chapter_number}`;
    titleSlim.textContent = `${unitLabel}: ${ch.title}`;
    titleSlim.title = `${unitLabel}: ${ch.title}`;
  }
  if (counterSlim) {
    const absPage = ch.start_page + currentChapterPage - 1;
    counterSlim.textContent = `Seite ${currentChapterPage} von ${ch.page_count} (S. ${absPage})`;
  }
  if (downloadBtn) {
    downloadBtn.href = ch.file_url;
    downloadBtn.setAttribute("download", ch.filename);
  }

  // Drawer aktiv markieren
  updateDrawerActiveState();

  // Drawer schließen falls offen
  closeTOCDrawer();

  // Seiten-Pills & gewählte Seite anzeigen
  renderBookPageStrip();
  renderChapterPage();

  // Nach oben scrollen für optimales Leseerlebnis
  const canvasWrap = document.getElementById("book-page-canvas-wrapper");
  if (canvasWrap) canvasWrap.scrollTop = 0;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function closeReaderToCatalog() {
  const catalogView = document.getElementById("book-catalog-view");
  const readerView = document.getElementById("book-reader-view");
  if (readerView) readerView.style.display = "none";
  if (catalogView) catalogView.style.display = "flex";
  document.body.classList.remove("reader-zen-mode");
  closeTOCDrawer();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function updateChapterNavButtons() {
  const prevBtn = document.getElementById("btn-reader-prev-chapter");
  const nextBtn = document.getElementById("btn-reader-next-chapter");
  if (!activeBookDetail || !activeChapter) return;

  const chaps = activeBookDetail.chapters || [];
  const idx = chaps.findIndex(c => c.id === activeChapter.id);

  if (prevBtn) prevBtn.disabled = idx <= 0;
  if (nextBtn) nextBtn.disabled = idx < 0 || idx >= chaps.length - 1;
}

function navigateChapter(delta) {
  if (!activeBookDetail || !activeChapter) return;
  const chaps = activeBookDetail.chapters || [];
  const idx = chaps.findIndex(c => c.id === activeChapter.id);
  const targetIdx = idx + delta;
  if (targetIdx >= 0 && targetIdx < chaps.length) {
    openChapter(chaps[targetIdx], 1);
  }
}

// Schnelles Blättern im Kapitel (per 2-Finger-Swipe, Schwebepfeile oder Tastatur)
function flipBookPage(delta) {
  if (!activeChapter) return;
  const targetPage = currentChapterPage + delta;
  if (targetPage >= 1 && targetPage <= activeChapter.page_count) {
    currentChapterPage = targetPage;
    renderChapterPage();
  }
}

// 3. Offcanvas TOC Drawer
function openTOCDrawer() {
  const drawer = document.getElementById("book-toc-drawer");
  const backdrop = document.getElementById("book-toc-drawer-backdrop");
  if (drawer) drawer.classList.add("open");
  if (backdrop) backdrop.classList.add("open");
}

function closeTOCDrawer() {
  const drawer = document.getElementById("book-toc-drawer");
  const backdrop = document.getElementById("book-toc-drawer-backdrop");
  if (drawer) drawer.classList.remove("open");
  if (backdrop) backdrop.classList.remove("open");
}

function renderDrawerTOC(filterTerm = "") {
  const container = document.getElementById("drawer-chapters-list");
  if (!container || !activeBookDetail) return;
  container.innerHTML = "";

  const term = (filterTerm || "").toLowerCase().trim();
  const chapters = (activeBookDetail.chapters || []).filter((ch) => {
    if (!term) return true;
    const hasSectionMatch = (ch.sections || []).some(
      (s) =>
        s.title.toLowerCase().includes(term) ||
        String(s.book_page).includes(term)
    );
    return (
      ch.title.toLowerCase().includes(term) ||
      (ch.topic_name && ch.topic_name.toLowerCase().includes(term)) ||
      hasSectionMatch
    );
  });

  if (chapters.length === 0) {
    container.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 0.88rem;">Keine Lerneinheiten für "${escapeHtml(filterTerm)}" gefunden.</div>`;
    return;
  }

  chapters.forEach((ch) => {
    const item = document.createElement("div");
    const isActive = activeChapter && activeChapter.id === ch.id;
    item.className = `drawer-chapter-item ${isActive ? "active" : ""}`;
    item.dataset.chapterId = ch.id;

    const unitLabel = ch.chapter_number === 0 ? "Titelei" : `Einheit ${ch.chapter_number}`;

    let sectionsHtml = "";
    if (ch.sections && ch.sections.length > 0) {
      const visibleSections = term
        ? ch.sections.filter(
            (s) =>
              s.title.toLowerCase().includes(term) ||
              String(s.book_page).includes(term) ||
              ch.title.toLowerCase().includes(term)
          )
        : ch.sections;

      if (visibleSections.length > 0) {
        sectionsHtml = `
          <div class="drawer-sections-list">
            ${visibleSections
              .map((sec) => {
                const isSecActive = isActive && currentChapterPage >= sec.relative_page;
                return `
                  <div class="drawer-section-item ${isSecActive ? "active" : ""}" data-target-page="${sec.relative_page}" title="Direkt aufschlagen: ${escapeHtml(sec.title)} (Buchseite ${sec.book_page})">
                    <span class="drawer-sec-bullet">↳</span>
                    <span class="drawer-sec-title">${escapeHtml(sec.title)}</span>
                    <span class="drawer-sec-page">S. ${sec.book_page}</span>
                  </div>
                `;
              })
              .join("")}
          </div>
        `;
      }
    }

    item.innerHTML = `
      <div class="drawer-chapter-header" title="Kapitel ab Seite 1 aufschlagen">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="catalog-badge">${unitLabel}</span>
          <span style="font-size: 0.74rem; color: var(--text-muted); font-weight: 600;">S. ${ch.start_page}–${ch.end_page}</span>
        </div>
        <div style="font-size: 0.92rem; font-weight: 700; color: var(--text-primary); margin-top: 4px;">${escapeHtml(ch.title)}</div>
        ${ch.topic_name ? `<div style="font-size: 0.76rem; color: #94a3b8;">📐 ${escapeHtml(ch.topic_name)}</div>` : ""}
      </div>
      ${sectionsHtml}
    `;

    const chapHeader = item.querySelector(".drawer-chapter-header");
    if (chapHeader) {
      chapHeader.addEventListener("click", () => openChapter(ch, 1));
    }

    item.querySelectorAll(".drawer-section-item").forEach((secEl) => {
      secEl.addEventListener("click", (e) => {
        e.stopPropagation();
        const p = parseInt(secEl.dataset.targetPage, 10) || 1;
        openChapter(ch, p);
      });
    });

    container.appendChild(item);
  });
}

function updateDrawerActiveState() {
  document.querySelectorAll(".drawer-chapter-item").forEach((it) => {
    const isChapActive = activeChapter && it.dataset.chapterId === activeChapter.id;
    it.classList.toggle("active", isChapActive);
    if (isChapActive && activeChapter && activeChapter.sections && activeChapter.sections.length > 0) {
      let currentActiveRel = 1;
      activeChapter.sections.forEach((s) => {
        if (s.relative_page <= currentChapterPage && s.relative_page >= currentActiveRel) {
          currentActiveRel = s.relative_page;
        }
      });
      it.querySelectorAll(".drawer-section-item").forEach((sEl) => {
        const p = parseInt(sEl.dataset.targetPage, 10);
        sEl.classList.toggle("active", p === currentActiveRel);
      });
    }
  });
}

// 4. Seiten-Pills & Seiten-Rendering
function renderBookPageStrip() {
  const strip = document.getElementById("book-page-strip");
  if (!strip || !activeChapter) return;
  strip.innerHTML = "";

  for (let p = 1; p <= activeChapter.page_count; p++) {
    const absPage = activeChapter.start_page + p - 1;
    const pill = document.createElement("div");
    pill.className = `book-page-pill ${p === currentChapterPage ? "active" : ""}`;
    pill.dataset.page = p;
    pill.textContent = p;
    pill.title = `Seite ${p} des Kapitels (Buchseite ${absPage})`;
    pill.addEventListener("click", () => {
      currentChapterPage = p;
      renderChapterPage();
    });
    strip.appendChild(pill);
  }
}

async function renderChapterPage() {
  if (!activeChapter) return;

  const counterEl = document.getElementById("book-page-counter");
  const counterSlim = document.getElementById("reader-page-counter-slim");
  const prevBtn = document.getElementById("btn-book-prev-page");
  const nextBtn = document.getElementById("btn-book-next-page");
  const floatPrev = document.getElementById("btn-floating-prev");
  const floatNext = document.getElementById("btn-floating-next");
  const imgEl = document.getElementById("book-page-img");
  const loadingEl = document.getElementById("book-page-loading");

  const absPage = activeChapter.start_page + currentChapterPage - 1;
  if (counterSlim) {
    counterSlim.textContent = `Seite ${currentChapterPage} von ${activeChapter.page_count} (S. ${absPage})`;
  }
  if (counterEl) {
    counterEl.innerHTML = `Seite ${currentChapterPage} von ${activeChapter.page_count} <small id="book-page-absolute">(Buchseite ${absPage})</small>`;
  }

  if (prevBtn) prevBtn.disabled = currentChapterPage <= 1;
  if (nextBtn) nextBtn.disabled = currentChapterPage >= activeChapter.page_count;
  if (floatPrev) floatPrev.disabled = currentChapterPage <= 1;
  if (floatNext) floatNext.disabled = currentChapterPage >= activeChapter.page_count;

  // Schnell-Sprung-Dropdown für Unterthemen / Inhaltsverzeichnis-Einträge synchronisieren
  const sectionWrap = document.getElementById("book-section-picker-wrap");
  const sectionSelect = document.getElementById("book-section-select");
  if (sectionWrap && sectionSelect) {
    const sections = activeChapter.sections || [];
    if (sections.length > 0) {
      sectionWrap.style.display = "inline-flex";
      sectionSelect.innerHTML = sections
        .map(
          (s) =>
            `<option value="${s.relative_page}">${escapeHtml(s.title)} (S. ${s.book_page})</option>`
        )
        .join("");

      // Bestimme den Abschnitt, in dem Thea sich gerade befindet
      let currentActiveRel = sections[0].relative_page;
      sections.forEach((s) => {
        if (s.relative_page <= currentChapterPage) {
          currentActiveRel = s.relative_page;
        }
      });
      sectionSelect.value = String(currentActiveRel);

      if (!sectionSelect.dataset.wired) {
        sectionSelect.dataset.wired = "true";
        sectionSelect.addEventListener("change", (e) => {
          const targetPage = parseInt(e.target.value, 10);
          if (targetPage && targetPage >= 1 && activeChapter && targetPage <= activeChapter.page_count) {
            currentChapterPage = targetPage;
            renderChapterPage();
          }
        });
      }
    } else {
      sectionWrap.style.display = "none";
    }
  }

  // Aktive Pill markieren und horizontal ins Sichtfeld scrollen (ohne vertikales Springen)
  document.querySelectorAll(".book-page-pill").forEach((pill) => {
    const isAct = parseInt(pill.dataset.page, 10) === currentChapterPage;
    pill.classList.toggle("active", isAct);
    if (isAct) {
      const booksTab = document.getElementById("tab-books");
      if (booksTab && booksTab.classList.contains("active")) {
        const strip = document.getElementById("book-page-strip");
        if (strip) {
          const targetScroll = pill.offsetLeft - (strip.clientWidth / 2) + (pill.clientWidth / 2);
          strip.scrollTo({ left: Math.max(0, targetScroll), behavior: "smooth" });
        }
      }
    }
  });

  // Drawer-Aktualisierung (aktive Sektion hervorheben)
  updateDrawerActiveState();

  // Scrollposition auf Seitenanfang zurücksetzen
  const canvasWrap = document.getElementById("book-page-canvas-wrapper");
  if (canvasWrap) canvasWrap.scrollTop = 0;

  // Bild in gewähltem Modus laden
  if (imgEl) {
    if (!imgEl.dataset.calloutProtected) {
      imgEl.dataset.calloutProtected = "true";
      imgEl.addEventListener("contextmenu", (e) => e.preventDefault());
      imgEl.addEventListener("dragstart", (e) => e.preventDefault());
    }
    if (loadingEl) loadingEl.style.display = "flex";
    imgEl.className = `book-page-img mode-${bookZoomMode}`;
    const targetUrl = `/api/v1/materials/${activeChapter.id}/preview?page=${currentChapterPage}`;

    const onImageLoaded = () => {
      if (loadingEl) loadingEl.style.display = "none";
      syncBookAnnotationCanvasSize();
      loadBookAnnotations(activeChapter.id, currentChapterPage);
    };

    imgEl.onload = onImageLoaded;
    imgEl.onerror = (e) => {
      if (loadingEl) loadingEl.style.display = "none";
      console.error("Fehler beim Laden der Buchseite:", targetUrl, e);
    };
    imgEl.src = targetUrl;

    if (imgEl.complete && imgEl.naturalWidth > 0) {
      onImageLoaded();
    }
  }

  // Benachbarte Seiten intelligent im Hintergrund vorladen
  prefetchAdjacentPages();
}

function prefetchAdjacentPages() {
  if (!activeChapter) return;
  const p = currentChapterPage;
  const pagesToPrefetch = [p + 1, p - 1, p + 2];

  pagesToPrefetch.forEach((targetP) => {
    if (targetP >= 1 && targetP <= activeChapter.page_count) {
      // 1. Browser-Bild-Cache vorwärmen
      const preloadImg = new Image();
      preloadImg.src = `/api/v1/materials/${activeChapter.id}/preview?page=${targetP}`;
    }
  });

  // 2. Server-seitige Prioritäts-Queue triggern
  try {
    fetch(`/api/v1/materials/${activeChapter.id}/prefetch?page=${p}`, {
      method: "POST"
    }).catch(() => {});
  } catch (e) {}
}

function setupBookBrowserEvents() {
  // Zurück zur Kapitelübersicht
  const btnBack = document.getElementById("btn-back-to-catalog");
  if (btnBack) {
    btnBack.addEventListener("click", closeReaderToCatalog);
  }

  // Drawer öffnen / schließen
  const btnOpenDrawer = document.getElementById("btn-open-toc-drawer");
  if (btnOpenDrawer) {
    btnOpenDrawer.addEventListener("click", openTOCDrawer);
  }

  const btnCloseDrawer = document.getElementById("btn-close-toc-drawer");
  if (btnCloseDrawer) {
    btnCloseDrawer.addEventListener("click", closeTOCDrawer);
  }

  const backdrop = document.getElementById("book-toc-drawer-backdrop");
  if (backdrop) {
    backdrop.addEventListener("click", closeTOCDrawer);
  }

  // Filter in Katalog-Ansicht
  const catalogFilter = document.getElementById("book-catalog-filter-input");
  if (catalogFilter) {
    catalogFilter.addEventListener("input", (e) => {
      renderBookCatalog(e.target.value);
    });
  }

  // Filter im Offcanvas Drawer
  const drawerFilter = document.getElementById("drawer-filter-input");
  if (drawerFilter) {
    drawerFilter.addEventListener("input", (e) => {
      renderDrawerTOC(e.target.value);
    });
  }

  // Vorheriges / Nächstes Kapitel Buttons im Reader
  const prevChapBtn = document.getElementById("btn-reader-prev-chapter");
  if (prevChapBtn) {
    prevChapBtn.addEventListener("click", () => navigateChapter(-1));
  }

  const nextChapBtn = document.getElementById("btn-reader-next-chapter");
  if (nextChapBtn) {
    nextChapBtn.addEventListener("click", () => navigateChapter(1));
  }

  // Seiten-Navigation: Schwebepfeile links & rechts
  const floatPrev = document.getElementById("btn-floating-prev");
  const floatNext = document.getElementById("btn-floating-next");
  if (floatPrev) {
    floatPrev.addEventListener("click", (e) => {
      e.stopPropagation();
      flipBookPage(-1);
    });
  }
  if (floatNext) {
    floatNext.addEventListener("click", (e) => {
      e.stopPropagation();
      flipBookPage(1);
    });
  }

  // Seiten-Navigation Buttons (Fallback falls vorhanden)
  const prevBtn = document.getElementById("btn-book-prev-page");
  const nextBtn = document.getElementById("btn-book-next-page");

  if (prevBtn) {
    prevBtn.addEventListener("click", () => flipBookPage(-1));
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => flipBookPage(1));
  }

  // Schwebende Stift-Palette Ein-/Ausklappen (Vorschlag 1)
  const btnToggleInk = document.getElementById("btn-toggle-ink-toolbar");
  const inkPalette = document.getElementById("reader-floating-ink-palette");
  const btnClosePalette = document.getElementById("btn-close-ink-palette");

  if (btnToggleInk && inkPalette) {
    btnToggleInk.addEventListener("click", () => {
      const isHidden = inkPalette.style.display === "none";
      inkPalette.style.display = isHidden ? "flex" : "none";
      btnToggleInk.classList.toggle("active", isHidden);
    });
  }

  if (btnClosePalette && inkPalette) {
    btnClosePalette.addEventListener("click", () => {
      inkPalette.style.display = "none";
      if (btnToggleInk) btnToggleInk.classList.remove("active");
    });
  }

  // Tastatur-Navigation (Links / Rechts Pfeiltasten zum Blättern)
  window.addEventListener("keydown", (e) => {
    const readerView = document.getElementById("book-reader-view");
    if (readerView && readerView.style.display !== "none") {
      if (e.key === "ArrowLeft") {
        flipBookPage(-1);
      } else if (e.key === "ArrowRight") {
        flipBookPage(1);
      }
    }
  });

  // 2-Finger-Wischen auf Mac-Trackpads (Horizontaler 2-Finger-Wisch erzeugt deltaX)
  let macWheelCooldown = false;
  let macAccumulatedDeltaX = 0;
  let macWheelTimer = null;

  window.addEventListener("wheel", (e) => {
    if (!document.body.classList.contains("reader-zen-mode")) return;
    const readerView = document.getElementById("book-reader-view");
    if (!readerView || readerView.style.display === "none") return;

    // Nur horizontal dominierende Gesten auswerten (damit normales vertikales Scrollen unberührt bleibt)
    if (Math.abs(e.deltaX) > Math.abs(e.deltaY) * 1.2 && Math.abs(e.deltaX) > 8) {
      if (macWheelCooldown) {
        e.preventDefault();
        return;
      }

      macAccumulatedDeltaX += e.deltaX;

      clearTimeout(macWheelTimer);
      macWheelTimer = setTimeout(() => {
        macAccumulatedDeltaX = 0;
      }, 140);

      // Schwellenwert für Seitenwechsel: 45px akkumulierter Wischweg
      if (Math.abs(macAccumulatedDeltaX) > 45) {
        macWheelCooldown = true;
        const dir = macAccumulatedDeltaX > 0 ? 1 : -1;
        macAccumulatedDeltaX = 0;
        flipBookPage(dir);
        e.preventDefault();

        // Cooldown, um Trägheitsimpulse des Trackpads abzufangen
        setTimeout(() => {
          macWheelCooldown = false;
        }, 400);
      }
    }
  }, { passive: false });

  // 1-Klick Zoom-Umschalter in der Kopfzeile & Palette
  const btnToggleZoom = document.getElementById("btn-toggle-zoom-mode");
  const zoomIcon = document.getElementById("zoom-mode-icon");
  const zoomFitBtn = document.getElementById("btn-book-zoom-fit");
  const zoomWidthBtn = document.getElementById("btn-book-zoom-width");
  const imgEl = document.getElementById("book-page-img");

  function setBookZoomMode(mode) {
    bookZoomMode = mode;
    if (imgEl) imgEl.className = `book-page-img mode-${mode}`;
    if (zoomIcon) zoomIcon.textContent = mode === "fit" ? "↔" : "⛶";
    if (btnToggleZoom) btnToggleZoom.title = mode === "fit" ? "Auf volle Breite umschalten (↔)" : "Ganze Seite einpassen (⛶)";
    if (zoomFitBtn) zoomFitBtn.classList.toggle("active", mode === "fit");
    if (zoomWidthBtn) zoomWidthBtn.classList.toggle("active", mode === "width");
    setTimeout(syncBookAnnotationCanvasSize, 220);
  }

  if (btnToggleZoom) {
    btnToggleZoom.addEventListener("click", () => {
      setBookZoomMode(bookZoomMode === "width" ? "fit" : "width");
    });
  }

  if (zoomFitBtn) {
    zoomFitBtn.addEventListener("click", () => setBookZoomMode("fit"));
  }

  if (zoomWidthBtn) {
    zoomWidthBtn.addEventListener("click", () => setBookZoomMode("width"));
  }

  // Inking Engine starten
  initBookInking();
}

// ====================================================================
// Notizen-Anzeige & Whiteboard-Handoff im Dokument-/Buch-Reader
// ====================================================================
let bookAnnotationCanvas = null;
let bookAnnotationCtx = null;
let bookAnnotationStrokes = [];
let bookAnnotationLoadedKey = null;
let currentBookAnnotationMaterialId = null;
let currentBookAnnotationPage = null;

function initBookInking() {
  bookAnnotationCanvas = document.getElementById("book-annotation-canvas");
  if (!bookAnnotationCanvas) return;
  bookAnnotationCtx = bookAnnotationCanvas.getContext("2d");

  // Button: Seite auf der interaktiven Tafel öffnen & mit Stift beschreiben
  const btnEditOnWb = document.getElementById("btn-edit-page-on-whiteboard");
  if (btnEditOnWb) {
    btnEditOnWb.addEventListener("click", () => {
      if (!activeChapter) return;
      if (typeof window.openBookPageOnWhiteboard === "function") {
        window.openBookPageOnWhiteboard({
          materialId: activeChapter.id,
          page: currentChapterPage,
          pageCount: activeChapter.page_count,
          title: (activeChapter.chapter_number ? ("Einheit " + activeChapter.chapter_number + ": ") : "") + activeChapter.title,
          subjectId: activeBookDetail ? activeBookDetail.subject_id : null
        });
      }
    });
  }

  // Zwei-Finger-Wischen zum Umblättern auf dem iPad (ohne Canvas-Blockaden)
  const wrapper = document.getElementById("book-page-canvas-wrapper");
  let touchStartX = null;
  let touchStartY = null;
  let pageFlipped = false;

  if (wrapper) {
    wrapper.addEventListener("touchstart", (e) => {
      if (e.touches.length === 2) {
        touchStartX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
        touchStartY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        pageFlipped = false;
      } else {
        touchStartX = null;
        touchStartY = null;
      }
    }, { passive: true });

    wrapper.addEventListener("touchmove", (e) => {
      if (e.touches.length === 2 && touchStartX !== null && touchStartY !== null) {
        const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
        const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        const dx = midX - touchStartX;
        const dy = midY - touchStartY;

        if (!pageFlipped && Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.3) {
          pageFlipped = true;
          flipBookPage(dx < 0 ? 1 : -1);
        }
      }
    }, { passive: true });

    wrapper.addEventListener("touchend", () => {
      touchStartX = null;
      touchStartY = null;
      pageFlipped = false;
    }, { passive: true });
  }

  window.addEventListener("resize", () => {
    syncBookAnnotationCanvasSize();
  });
}

// Rückkehr-Funktion von der Tafel zum Buch
window.returnToBookReader = function(targetPage) {
  switchToTab("books");
  if (activeChapter) {
    openChapter(activeChapter, targetPage || currentChapterPage);
  }
};

function syncBookAnnotationCanvasSize() {
  const imgEl = document.getElementById("book-page-img");
  const canvas = document.getElementById("book-annotation-canvas");
  if (!imgEl || !canvas) return;

  const w = imgEl.clientWidth;
  const h = imgEl.clientHeight;
  if (w === 0 || h === 0) return;

  const dpr = window.devicePixelRatio || 1;
  const targetPixelW = Math.round(w * dpr);
  const targetPixelH = Math.round(h * dpr);

  canvas.style.left = `${imgEl.offsetLeft}px`;
  canvas.style.top = `${imgEl.offsetTop}px`;

  if (canvas.width !== targetPixelW || canvas.height !== targetPixelH) {
    canvas.width = targetPixelW;
    canvas.height = targetPixelH;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    const ctx = bookAnnotationCtx || canvas.getContext("2d");
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  redrawBookAnnotations();
}

function redrawBookAnnotations() {
  const canvas = document.getElementById("book-annotation-canvas");
  if (!canvas) return;
  const ctx = bookAnnotationCtx || canvas.getContext("2d");
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const cssW = canvas.clientWidth || (canvas.width / dpr);
  const cssH = canvas.clientHeight || (canvas.height / dpr);
  if (cssW === 0 || cssH === 0) return;

  for (const stroke of bookAnnotationStrokes) {
    if (!stroke.points || stroke.points.length === 0) continue;

    if (stroke.tool === "highlighter") {
      ctx.globalAlpha = 0.38;
      ctx.globalCompositeOperation = "multiply";
      ctx.strokeStyle = stroke.color || "#facc15";
      ctx.lineWidth = stroke.width || 22;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      if (stroke.points.length === 1) {
        const pt = stroke.points[0];
        ctx.beginPath();
        ctx.arc(pt.x * cssW, pt.y * cssH, (stroke.width || 22) / 2, 0, Math.PI * 2);
        ctx.fillStyle = stroke.color || "#facc15";
        ctx.fill();
      } else if (stroke.points.length === 2) {
        ctx.beginPath();
        ctx.moveTo(stroke.points[0].x * cssW, stroke.points[0].y * cssH);
        ctx.lineTo(stroke.points[1].x * cssW, stroke.points[1].y * cssH);
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.moveTo(stroke.points[0].x * cssW, stroke.points[0].y * cssH);
        for (let i = 1; i < stroke.points.length - 1; i++) {
          const p1 = stroke.points[i];
          const p2 = stroke.points[i + 1];
          const midX = (p1.x + p2.x) * 0.5 * cssW;
          const midY = (p1.y + p2.y) * 0.5 * cssH;
          ctx.quadraticCurveTo(p1.x * cssW, p1.y * cssH, midX, midY);
        }
        const last = stroke.points[stroke.points.length - 1];
        ctx.lineTo(last.x * cssW, last.y * cssH);
        ctx.stroke();
      }
    } else {
      ctx.globalAlpha = 1.0;
      ctx.globalCompositeOperation = "source-over";
      ctx.strokeStyle = stroke.color || "#2563eb";
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      const baseWidth = stroke.width || 2.6;
      ctx.lineWidth = baseWidth;
      if (stroke.points.length === 1) {
        const pt = stroke.points[0];
        const r = Math.max(0.5, baseWidth / 2);
        ctx.fillStyle = stroke.color || "#2563eb";
        ctx.beginPath();
        ctx.arc(pt.x * cssW, pt.y * cssH, r, 0, Math.PI * 2);
        ctx.fill();
      } else if (stroke.points.length === 2) {
        ctx.beginPath();
        ctx.moveTo(stroke.points[0].x * cssW, stroke.points[0].y * cssH);
        ctx.lineTo(stroke.points[1].x * cssW, stroke.points[1].y * cssH);
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.moveTo(stroke.points[0].x * cssW, stroke.points[0].y * cssH);
        for (let i = 1; i < stroke.points.length - 1; i++) {
          const p1 = stroke.points[i];
          const p2 = stroke.points[i + 1];
          const midX = (p1.x + p2.x) * 0.5 * cssW;
          const midY = (p1.y + p2.y) * 0.5 * cssH;
          ctx.quadraticCurveTo(p1.x * cssW, p1.y * cssH, midX, midY);
        }
        const last = stroke.points[stroke.points.length - 1];
        ctx.lineTo(last.x * cssW, last.y * cssH);
        ctx.stroke();
      }
    }
  }
}


async function loadBookAnnotations(materialId, pageNum) {
  currentBookAnnotationMaterialId = materialId;
  currentBookAnnotationPage = pageNum;

  bookAnnotationStrokes = [];
  redrawBookAnnotations();

  const key = `${materialId}_${pageNum}`;
  bookAnnotationLoadedKey = key;

  try {
    const res = await fetch(`/api/v1/materials/${materialId}/pages/${pageNum}/annotations`);
    if (res.ok) {
      const data = await res.json();
      if (bookAnnotationLoadedKey === key) {
        let loaded = [];
        if (Array.isArray(data.strokes) && data.strokes.length > 0) {
          loaded = data.strokes;
        } else if (data.strokes_json) {
          try {
            loaded = JSON.parse(data.strokes_json) || [];
          } catch (e) {
            loaded = [];
          }
        }
        bookAnnotationStrokes = loaded;
        redrawBookAnnotations();
      }
    } else {
      console.warn("Laden der Annotationen HTTP Status:", res.status);
    }
  } catch (err) {
    console.error("Fehler beim Laden der Notizen:", err);
  }
}

// Init
async function initApp() {
  document.body.classList.remove("reader-zen-mode");
  document.body.classList.remove("timetable-zen-mode");
  document.documentElement.classList.remove("timetable-zen-mode");
  document.body.classList.remove("whiteboard-zen-mode");
  document.documentElement.classList.remove("whiteboard-zen-mode");
  const safeRun = async (fn, name) => {
    try {
      await fn();
    } catch (err) {
      console.error(`Init error in ${name}:`, err);
    }
  };

  safeRun(setupParentModeEvents, "setupParentModeEvents");
  safeRun(initThemeManager, "initThemeManager");
  await safeRun(checkParentAuthStatus, "checkParentAuthStatus");
  await safeRun(checkEnvironment, "checkEnvironment");
  await safeRun(loadGamificationOverview, "loadGamificationOverview");
  await safeRun(loadProfile, "loadProfile");
  await safeRun(loadTaxonomy, "loadTaxonomy");
  await safeRun(loadPlan, "loadPlan");
  await safeRun(loadMaterials, "loadMaterials");
  await safeRun(checkInboxStatus, "checkInboxStatus");
  await safeRun(loadTodayDashboardWidget, "loadTodayDashboardWidget");
  await safeRun(loadTimetable, "loadTimetable");
  await safeRun(loadBooks, "loadBooks");
  safeRun(setupBookBrowserEvents, "setupBookBrowserEvents");
  safeRun(setupSubjectDetailEvents, "setupSubjectDetailEvents");
  safeRun(setupUploadsPageEvents, "setupUploadsPageEvents");
  safeRun(initDashboardQuickActions, "initDashboardQuickActions");
  safeRun(connectWebSocket, "connectWebSocket");
}

function initDashboardQuickActions() {
  const quickTafel = document.getElementById("btn-quick-tafel");
  if (quickTafel) {
    quickTafel.addEventListener("click", () => switchToTab("whiteboard"));
    quickTafel.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        switchToTab("whiteboard");
      }
    });
  }
  const quickPlanner = document.getElementById("btn-quick-planner");
  if (quickPlanner) {
    quickPlanner.addEventListener("click", () => switchToTab("planner"));
    quickPlanner.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        switchToTab("planner");
      }
    });
  }
  const quickBooks = document.getElementById("btn-quick-books");
  if (quickBooks) {
    quickBooks.addEventListener("click", () => switchToTab("books"));
    quickBooks.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        switchToTab("books");
      }
    });
  }
  const quickUpload = document.getElementById("btn-quick-upload");
  if (quickUpload) {
    quickUpload.addEventListener("click", () => switchToTab("uploads"));
    quickUpload.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        switchToTab("uploads");
      }
    });
  }

  const initialTab = document.querySelector(".nav-tab.active");
  if (initialTab && initialTab.dataset.tab === "whiteboard") {
    document.documentElement.classList.add("whiteboard-zen-mode");
    document.body.classList.add("whiteboard-zen-mode");
  } else if (initialTab && initialTab.dataset.tab === "timetable") {
    document.documentElement.classList.add("timetable-zen-mode");
    document.body.classList.add("timetable-zen-mode");
  }
}

initApp();

