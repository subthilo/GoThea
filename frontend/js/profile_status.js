// 3. Profil Speichern Event
document.getElementById("btn-save-profile").addEventListener("click", async () => {
  const name = document.getElementById("prof-name").value;
  const grade_level = parseInt(document.getElementById("prof-grade").value, 10);
  const school_type = document.getElementById("prof-school").value;
  const feedback = document.getElementById("prof-feedback");

  try {
    const res = await apiFetch("/api/v1/profile", {
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
    const res = await apiFetch("/api/v1/env");
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

