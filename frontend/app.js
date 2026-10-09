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

// Tab Navigation
document.querySelectorAll(".nav-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));

    btn.classList.add("active");
    const target = document.getElementById(`tab-${btn.dataset.tab}`);
    if (target) target.classList.add("active");
  });
});

// 1. Profil laden
async function loadProfile() {
  try {
    const res = await fetch("/api/v1/profile");
    if (res.ok) {
      currentProfile = await res.json();
      badgeGrade.textContent = `${currentProfile.grade_level}. Klasse`;
      userGreeting.textContent = `Hallo, ${currentProfile.name}! 👋`;
      userSubtitle.textContent = `${currentProfile.grade_level}. Klasse ${currentProfile.school_type} • Land ${currentProfile.federal_state} (Niveaustufe E)`;

      // Profil-Formular initialisieren
      document.getElementById("prof-name").value = currentProfile.name;
      document.getElementById("prof-grade").value = currentProfile.grade_level;
      document.getElementById("prof-school").value = currentProfile.school_type;
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

      statSubjectsCount.textContent = currentSubjects.length;
      statTopicsCount.textContent = allTopics.length;

      // Group topics by subject
      const topicsBySubject = {};
      allTopics.forEach((t) => {
        if (!topicsBySubject[t.subject_id]) topicsBySubject[t.subject_id] = [];
        topicsBySubject[t.subject_id].push(t);
      });

      renderDashboardSubjects(currentSubjects, topicsBySubject);
      renderDetailedSubjects(currentSubjects, topicsBySubject);
    }
  } catch (err) {
    console.error("Fehler beim Laden der Fächer:", err);
  }
}

// Render Dashboard Cards
function renderDashboardSubjects(subjects, topicsMap) {
  dashboardSubjectsGrid.innerHTML = "";
  subjects.forEach((s) => {
    const topics = topicsMap[s.id] || [];
    const card = document.createElement("div");
    card.className = "subject-card";
    card.style.borderLeft = `4px solid ${s.color_code}`;

    const topicPreview = topics.slice(0, 2).map((t) => t.name).join(", ");

    card.innerHTML = `
      <div>
        <div class="subject-header">
          <div class="subject-badge-icon">${s.icon}</div>
          <div class="subject-name">${s.name}</div>
        </div>
        <div class="subject-topics-summary">
          ${topics.length > 0 ? topicPreview : "Noch keine Themen hinterlegt"}
        </div>
      </div>
      <div class="subject-footer">
        <span>${topics.length} Themen im Katalog</span>
        <span style="color: ${s.color_code}; font-weight: 600;">Klasse ${s.min_grade}–${s.max_grade}</span>
      </div>
    `;
    dashboardSubjectsGrid.appendChild(card);
  });
}

// Render Detailed View
function renderDetailedSubjects(subjects, topicsMap) {
  subjectsDetailedList.innerHTML = "";
  subjects.forEach((s) => {
    const topics = topicsMap[s.id] || [];
    const box = document.createElement("div");
    box.className = "subject-detail-box";

    let pillsHtml = topics.map((t) => `
      <div class="topic-pill">
        <span>${t.name}</span>
        ${t.rlp_level_code ? `<span class="topic-rlp-tag">RLP ${t.rlp_level_code}</span>` : ""}
      </div>
    `).join("");

    if (topics.length === 0) {
      pillsHtml = `<span style="color: var(--text-muted);">Keine Themen für diese Klassenstufe hinterlegt.</span>`;
    }

    box.innerHTML = `
      <h3>${s.icon} ${s.name}</h3>
      <div class="topic-pills">${pillsHtml}</div>
    `;
    subjectsDetailedList.appendChild(box);
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
    statusBadge.classList.add("online");
    statusText.textContent = "Verbunden";
  };

  ws.onclose = () => {
    statusBadge.classList.remove("online");
    statusText.textContent = "Verbindung getrennt";
    setTimeout(connectWebSocket, 3000);
  };
}

// Init
async function initApp() {
  await loadProfile();
  await loadTaxonomy();
  connectWebSocket();
}

initApp();
