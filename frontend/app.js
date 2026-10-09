// Status Handling
const statusBadge = document.getElementById("status-badge");
const statusText = document.getElementById("status-text");
const backendStatus = document.getElementById("backend-status");
const wsStatus = document.getElementById("ws-status");
const hostName = document.getElementById("host-name");

// Aktuellen Host anzeigen
if (window.location.host) {
  hostName.textContent = window.location.host;
}

// 1. Health-Check via HTTP REST
async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    if (res.ok) {
      const data = await res.json();
      backendStatus.textContent = "Online (" + data.device + ")";
      backendStatus.style.color = "var(--success)";
      statusBadge.classList.add("online");
      statusText.textContent = "Verbunden";
    } else {
      backendStatus.textContent = "Fehler " + res.status;
      backendStatus.style.color = "var(--warning)";
    }
  } catch (err) {
    backendStatus.textContent = "Nicht erreichbar";
    backendStatus.style.color = "var(--warning)";
  }
}

// 2. WebSocket Verbindung
function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    wsStatus.textContent = "Verbunden";
    wsStatus.style.color = "var(--success)";
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      console.log("WS Nachricht empfangen:", msg);
    } catch (e) {
      console.log("WS Rohdaten:", event.data);
    }
  };

  ws.onclose = () => {
    wsStatus.textContent = "Getrennt (Reconnecting...)";
    wsStatus.style.color = "var(--warning)";
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => {
    wsStatus.textContent = "Fehler";
    wsStatus.style.color = "var(--warning)";
  };
}

// Initialisierung
checkHealth();
connectWebSocket();
setInterval(checkHealth, 10000);
