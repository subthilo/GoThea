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
    const res = await apiFetch("/api/v1/exercises/gamification/overview");
    if (!res.ok) return;
    const data = await res.json();

    // Dashboard Chips
    const levelNumEl = document.getElementById("game-level-num");
    const levelTitleEl = document.getElementById("game-level-title");
    const levelIconEl = document.getElementById("game-level-icon");
    const streakDaysEl = document.getElementById("game-streak-days");
    const totalStarsEl = document.getElementById("game-total-stars");
    const totalXpEl = document.getElementById("game-total-xp");

    if (levelNumEl) levelNumEl.textContent = data.level?.level || 1;
    if (levelTitleEl) levelTitleEl.textContent = data.level?.title || "Wissens-Entdeckerin";
    if (levelIconEl) levelIconEl.innerHTML = `<img src="/static/Icons/Level.svg" class="capsule-svg-icon" alt="Level">`;

    if (streakDaysEl) streakDaysEl.textContent = data.streak_days || 0;
    if (totalStarsEl) totalStarsEl.textContent = data.total_stars || 0;
    if (totalXpEl) totalXpEl.textContent = data.total_xp || 0;

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
          barXpEl.innerHTML = `${icon("Stern")} ${data.total_xp}`;
        } else {
          barXpEl.textContent = `${lvl.current_level_xp} / ${lvl.needed_level_xp}`;
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
        persistence: "/static/Icons/Daumen hoch.svg",
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

