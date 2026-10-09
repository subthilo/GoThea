// GoThea Whiteboard Engine (Milestone 5 Frontend)
// Ultra-Low-Latency Apple Pencil & Touch Canvas with Coalesced Events, Pressure Smoothing & AI Overlay

(function() {
  // DOM Elements
  const viewport = document.getElementById("wb-viewport");
  const inkCanvas = document.getElementById("wb-canvas");
  const overlayCanvas = document.getElementById("wb-overlay");
  const subjectSelect = document.getElementById("wb-subject-select");
  const wsDot = document.getElementById("wb-ws-dot");
  const wsStatus = document.getElementById("wb-ws-status");
  const btnNewSession = document.getElementById("btn-wb-new-session");
  const btnRequestHint = document.getElementById("btn-wb-request-hint");
  const btnFullscreen = document.getElementById("btn-wb-fullscreen");
  const patternSelect = document.getElementById("wb-pattern-select");
  const btnPenOnly = document.getElementById("btn-wb-pen-only");
  const btnUndo = document.getElementById("btn-wb-undo");
  const btnRedo = document.getElementById("btn-wb-redo");
  const btnClear = document.getElementById("btn-wb-clear");
  const btnSave = document.getElementById("btn-wb-save");

  if (!inkCanvas || !overlayCanvas || !viewport) {
    return;
  }

  const inkCtx = inkCanvas.getContext("2d", { desynchronized: true });
  const overlayCtx = overlayCanvas.getContext("2d");

  // State
  let currentSession = null;
  let tutorSocket = null;
  let isDrawing = false;
  let currentTool = "pen"; // 'pen', 'highlighter', 'eraser'
  let currentColor = "#f8fafc";
  let currentBaseWidth = 4;
  let currentSmoothWidth = 4;
  let penOnlyMode = true; // Palm rejection: ignore finger touch
  let strokes = [];
  let redoStack = [];
  let currentStroke = null;
  let lastPoint = null;
  let dpr = window.devicePixelRatio || 1;
  let saveDebounceTimer = null;

  // 1. Canvas Resize & HiDPI Alignment
  function resizeCanvases() {
    const rect = viewport.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;

    dpr = window.devicePixelRatio || 1;
    const w = Math.floor(rect.width * dpr);
    const h = Math.floor(rect.height * dpr);

    if (inkCanvas.width !== w || inkCanvas.height !== h) {
      inkCanvas.width = w;
      inkCanvas.height = h;
      overlayCanvas.width = w;
      overlayCanvas.height = h;

      inkCanvas.style.width = `${rect.width}px`;
      inkCanvas.style.height = `${rect.height}px`;
      overlayCanvas.style.width = `${rect.width}px`;
      overlayCanvas.style.height = `${rect.height}px`;

      inkCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
      overlayCtx.setTransform(dpr, 0, 0, dpr, 0, 0);

      redrawAllStrokes();
    }
  }

  window.addEventListener("resize", resizeCanvases);

  // Tab activation
  document.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      if (tab.dataset.tab === "whiteboard") {
        setTimeout(resizeCanvases, 50);
      }
    });
  });

  // 2. High-Precision Coordinate & Pressure Extractor
  function getEventPoint(e) {
    const rect = inkCanvas.getBoundingClientRect();
    const pressure = (typeof e.pressure === "number" && e.pressure > 0) ? e.pressure : 0.5;
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      pressure: pressure,
      pointerType: e.pointerType || "mouse"
    };
  }

  // 3. Tool Styles Setup
  function applyToolStyle(ctx, tool, color, baseWidth) {
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    if (tool === "eraser") {
      ctx.globalCompositeOperation = "destination-out";
      ctx.strokeStyle = "rgba(0,0,0,1)";
      ctx.lineWidth = baseWidth * 5;
    } else if (tool === "highlighter") {
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 0.35;
      ctx.strokeStyle = color;
      ctx.lineWidth = baseWidth * 3.5;
    } else {
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1.0;
      ctx.strokeStyle = color;
      ctx.lineWidth = baseWidth;
    }
  }

  function redrawAllStrokes() {
    inkCtx.save();
    inkCtx.setTransform(1, 0, 0, 1, 0, 0);
    inkCtx.clearRect(0, 0, inkCanvas.width, inkCanvas.height);
    inkCtx.restore();

    for (let i = 0; i < strokes.length; i++) {
      drawStoredStroke(strokes[i]);
    }
  }

  function drawStoredStroke(stroke) {
    if (!stroke.points || stroke.points.length === 0) return;

    inkCtx.save();
    applyToolStyle(inkCtx, stroke.tool, stroke.color, stroke.width);

    const pts = stroke.points;
    if (pts.length === 1) {
      inkCtx.beginPath();
      inkCtx.arc(pts[0].x, pts[0].y, Math.max(1, stroke.width / 2), 0, Math.PI * 2);
      inkCtx.fillStyle = stroke.tool === "eraser" ? "#000" : stroke.color;
      inkCtx.fill();
    } else {
      inkCtx.beginPath();
      inkCtx.moveTo(pts[0].x, pts[0].y);
      for (let j = 1; j < pts.length; j++) {
        inkCtx.lineTo(pts[j].x, pts[j].y);
      }
      inkCtx.stroke();
    }

    inkCtx.restore();
  }

  // 4. Ultra-Fluid Live Drawing Loop
  function drawLiveSegment(pt) {
    if (!lastPoint) {
      lastPoint = pt;
      return;
    }

    // Dynamic pressure smoothing (avoids jerky/dotted line width changes)
    let targetWidth;
    if (currentTool === "eraser") {
      targetWidth = currentBaseWidth * 5;
    } else if (currentTool === "highlighter") {
      targetWidth = currentBaseWidth * 3.5;
    } else {
      targetWidth = Math.max(1.5, currentBaseWidth * (0.35 + pt.pressure * 1.3));
    }
    currentSmoothWidth = currentSmoothWidth * 0.6 + targetWidth * 0.4;

    inkCtx.lineWidth = currentSmoothWidth;
    inkCtx.beginPath();
    inkCtx.moveTo(lastPoint.x, lastPoint.y);
    inkCtx.lineTo(pt.x, pt.y);
    inkCtx.stroke();

    lastPoint = pt;
  }

  function handlePointerDown(e) {
    // Palm Rejection: Ignore touch if pencil-only is turned on
    if (penOnlyMode && e.pointerType === "touch") {
      return;
    }
    e.preventDefault();

    isDrawing = true;
    redoStack = [];

    const pt = getEventPoint(e);
    lastPoint = pt;
    currentSmoothWidth = currentBaseWidth;

    currentStroke = {
      tool: currentTool,
      color: currentColor,
      width: currentBaseWidth,
      points: [pt]
    };

    // Context einmalig einstellen
    applyToolStyle(inkCtx, currentTool, currentColor, currentBaseWidth);

    // Initialen Punkt zeichnen
    inkCtx.beginPath();
    const dotRadius = currentTool === "eraser" ? (currentBaseWidth * 2.5) : Math.max(1, currentBaseWidth / 2);
    inkCtx.arc(pt.x, pt.y, dotRadius, 0, Math.PI * 2);
    inkCtx.fillStyle = currentTool === "eraser" ? "#000" : currentColor;
    inkCtx.fill();
  }

  function handlePointerMove(e) {
    if (!isDrawing || !currentStroke) return;
    if (penOnlyMode && e.pointerType === "touch") return;
    e.preventDefault();

    // Coalesced Events: Greift Hardware-Updates mit voller Rate (120Hz/240Hz) ab
    const events = (e.getCoalescedEvents && e.getCoalescedEvents().length > 0)
      ? e.getCoalescedEvents()
      : [e];

    for (let i = 0; i < events.length; i++) {
      const pt = getEventPoint(events[i]);
      currentStroke.points.push(pt);
      drawLiveSegment(pt);
    }
  }

  function handlePointerUp(e) {
    if (!isDrawing) return;
    isDrawing = false;

    if (currentStroke && currentStroke.points.length > 0) {
      strokes.push(currentStroke);
      sendCanvasUpdate([currentStroke]);
      scheduleAutoSave();
    }

    currentStroke = null;
    lastPoint = null;
  }

  // Pointer Event-Listener mit passive: false für e.preventDefault()
  inkCanvas.addEventListener("pointerdown", handlePointerDown, { passive: false });
  inkCanvas.addEventListener("pointermove", handlePointerMove, { passive: false });
  inkCanvas.addEventListener("pointerup", handlePointerUp, { passive: false });
  inkCanvas.addEventListener("pointercancel", handlePointerUp, { passive: false });
  inkCanvas.addEventListener("pointerleave", handlePointerUp, { passive: false });

  // 5. KI-Overlay Visualisierung
  function drawOverlayActions(actions) {
    overlayCtx.clearRect(0, 0, overlayCanvas.width / dpr, overlayCanvas.height / dpr);

    actions.forEach(item => {
      if (item.action === "highlight_box" && item.coords) {
        overlayCtx.save();
        overlayCtx.strokeStyle = item.color || "#f59e0b";
        overlayCtx.lineWidth = 3;
        overlayCtx.fillStyle = "rgba(245, 158, 11, 0.12)";
        overlayCtx.beginPath();
        overlayCtx.roundRect(item.coords.x, item.coords.y, item.coords.w, item.coords.h, 12);
        overlayCtx.fill();
        overlayCtx.stroke();
        overlayCtx.restore();
      } else if (item.action === "latex_hint") {
        overlayCtx.save();
        const coords = item.coords || { x: 100, y: 100 };

        overlayCtx.fillStyle = "rgba(30, 41, 59, 0.95)";
        overlayCtx.strokeStyle = "#6366f1";
        overlayCtx.lineWidth = 1.5;
        overlayCtx.beginPath();
        overlayCtx.roundRect(coords.x - 10, coords.y - 25, 420, 44, 8);
        overlayCtx.fill();
        overlayCtx.stroke();

        overlayCtx.fillStyle = "#f8fafc";
        overlayCtx.font = "600 16px -apple-system, BlinkMacSystemFont, sans-serif";
        overlayCtx.fillText(item.latex || "Hinweis des KI-Tutors", coords.x + 6, coords.y + 4);
        overlayCtx.restore();
      } else if (item.action === "clear") {
        overlayCtx.clearRect(0, 0, overlayCanvas.width / dpr, overlayCanvas.height / dpr);
      }
    });

    setTimeout(() => {
      overlayCtx.clearRect(0, 0, overlayCanvas.width / dpr, overlayCanvas.height / dpr);
    }, 12000);
  }

  // 6. Backend-Persistenz (Auto-Save OHNE teures toDataURL)
  function scheduleAutoSave() {
    clearTimeout(saveDebounceTimer);
    saveDebounceTimer = setTimeout(async () => {
      if (!currentSession) return;
      try {
        const payload = {
          board_state_json: JSON.stringify(strokes)
        };
        await fetch(`/api/v1/whiteboard/sessions/${currentSession.id}/state`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      } catch (err) {
        console.error("Auto-Save Fehler:", err);
      }
    }, 1500);
  }

  async function initSession() {
    try {
      // 1. Fächer in Dropdown einbinden
      const subRes = await fetch("/api/v1/taxonomy/subjects");
      if (subRes.ok) {
        const subjects = await subRes.json();
        subjectSelect.innerHTML = subjects.map(s => `
          <option value="${s.id}">${s.icon} ${s.name}</option>
        `).join("");
      }

      // 2. Aktive Session suchen oder anlegen
      const actRes = await fetch("/api/v1/whiteboard/sessions/active");
      if (actRes.ok) {
        const data = await actRes.json();
        if (data) {
          currentSession = data;
          subjectSelect.value = data.subject_id;
          if (data.board_state_json) {
            try {
              strokes = JSON.parse(data.board_state_json) || [];
              redrawAllStrokes();
            } catch (e) {
              strokes = [];
            }
          }
        } else {
          await createNewSession();
        }
      } else {
        await createNewSession();
      }

      connectTutorWebSocket();
    } catch (e) {
      console.error("Fehler beim Initialisieren der Sitzung:", e);
    }
  }

  async function createNewSession() {
    const selectedSub = subjectSelect.value || "sub_math";
    try {
      const res = await fetch("/api/v1/whiteboard/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject_id: selectedSub,
          title: "Tafelübung",
          grade_level: 7
        })
      });
      if (res.ok) {
        currentSession = await res.json();
        strokes = [];
        redoStack = [];
        redrawAllStrokes();
        connectTutorWebSocket();
      }
    } catch (e) {
      console.error("Fehler beim Erstellen einer neuen Sitzung:", e);
    }
  }

  // 7. WebSocket Verbindung
  function connectTutorWebSocket() {
    if (!currentSession) return;
    if (tutorSocket) {
      tutorSocket.close();
    }

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/ws/tutor/${currentSession.id}`;

    try {
      tutorSocket = new WebSocket(wsUrl);

      tutorSocket.onopen = () => {
        wsDot.style.background = "#10b981";
        wsDot.style.boxShadow = "0 0 8px #10b981";
        wsStatus.textContent = "Live verbunden";
      };

      tutorSocket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "board_actions" && msg.actions) {
            drawOverlayActions(msg.actions);
          }
        } catch (e) {}
      };

      tutorSocket.onclose = () => {
        wsDot.style.background = "#ef4444";
        wsDot.style.boxShadow = "0 0 8px #ef4444";
        wsStatus.textContent = "Offline-Modus";
      };
    } catch (e) {
      console.error("WebSocket Verbindungsfehler:", e);
    }
  }

  function sendCanvasUpdate(newStrokes) {
    if (tutorSocket && tutorSocket.readyState === WebSocket.OPEN) {
      tutorSocket.send(JSON.stringify({
        type: "canvas_update",
        strokes: newStrokes,
        timestamp: Date.now()
      }));
    }
  }

  // 8. Toolbar Event-Handler
  // Werkzeugauswahl
  document.querySelectorAll(".wb-tool-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".wb-tool-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentTool = btn.dataset.tool;
    });
  });

  // Strichstärken
  document.querySelectorAll(".wb-size-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".wb-size-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentBaseWidth = parseFloat(btn.dataset.size);
    });
  });

  // Farben
  document.querySelectorAll(".wb-color-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".wb-color-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentColor = btn.dataset.color;
      if (currentTool === "eraser") {
        document.querySelectorAll(".wb-tool-btn").forEach(b => b.classList.remove("active"));
        const penBtn = document.querySelector('.wb-tool-btn[data-tool="pen"]');
        if (penBtn) penBtn.classList.add("active");
        currentTool = "pen";
      }
    });
  });

  // Muster-Wechsel
  if (patternSelect) {
    patternSelect.addEventListener("change", (e) => {
      viewport.className = `wb-viewport ${e.target.value}`;
    });
  }

  // Stift-Modus (Palm Rejection)
  if (btnPenOnly) {
    btnPenOnly.addEventListener("click", () => {
      penOnlyMode = !penOnlyMode;
      btnPenOnly.classList.toggle("active", penOnlyMode);
      document.getElementById("wb-pen-label").textContent = penOnlyMode ? "Pencil" : "Touch";
      btnPenOnly.title = penOnlyMode
        ? "Apple Pencil aktiv (Handfläche wird ignoriert)"
        : "Touch-Modus aktiv (Finger und Stift zeichnen)";
    });
  }

  // Undo / Redo
  if (btnUndo) {
    btnUndo.addEventListener("click", () => {
      if (strokes.length > 0) {
        const popped = strokes.pop();
        redoStack.push(popped);
        redrawAllStrokes();
        scheduleAutoSave();
      }
    });
  }

  if (btnRedo) {
    btnRedo.addEventListener("click", () => {
      if (redoStack.length > 0) {
        const restored = redoStack.pop();
        strokes.push(restored);
        redrawAllStrokes();
        scheduleAutoSave();
      }
    });
  }

  // Tafel leeren
  if (btnClear) {
    btnClear.addEventListener("click", () => {
      if (strokes.length === 0) return;
      if (confirm("Möchtest du die gesamte Tafel leeren?")) {
        strokes = [];
        redoStack = [];
        redrawAllStrokes();
        overlayCtx.clearRect(0, 0, overlayCanvas.width / dpr, overlayCanvas.height / dpr);
        scheduleAutoSave();
      }
    });
  }

  // Snapshot herunterladen
  if (btnSave) {
    btnSave.addEventListener("click", () => {
      const link = document.createElement("a");
      link.download = `gothea-tafel-${new Date().toISOString().slice(0, 10)}.png`;
      link.href = inkCanvas.toDataURL("image/png");
      link.click();
    });
  }

  // Neue Sitzung
  if (btnNewSession) {
    btnNewSession.addEventListener("click", async () => {
      if (confirm("Möchtest du eine neue Tafel für das gewählte Fach beginnen?")) {
        await createNewSession();
      }
    });
  }

  // Fach wechseln
  if (subjectSelect) {
    subjectSelect.addEventListener("change", async () => {
      await createNewSession();
    });
  }

  // KI-Tipp Anfordern
  if (btnRequestHint) {
    btnRequestHint.addEventListener("click", async () => {
      if (!currentSession) return;
      try {
        const res = await fetch(`/api/v1/whiteboard/sessions/${currentSession.id}/mock-tutor-hint`, {
          method: "POST"
        });
        if (res.ok) {
          const data = await res.json();
          if (data.actions) {
            drawOverlayActions(data.actions);
          }
        }
      } catch (e) {
        console.error("Fehler beim Abrufen des KI-Hinweises:", e);
      }
    });
  }

  // Vollbild-Modus
  if (btnFullscreen) {
    btnFullscreen.addEventListener("click", () => {
      document.body.classList.toggle("wb-fullscreen-mode");
      setTimeout(resizeCanvases, 100);
    });
  }

  // Tastenkombinationen
  window.addEventListener("keydown", (e) => {
    const tabWb = document.getElementById("tab-whiteboard");
    if (!tabWb || !tabWb.classList.contains("active")) return;

    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
      e.preventDefault();
      btnUndo.click();
    } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "y") {
      e.preventDefault();
      btnRedo.click();
    }
  });

  // Start
  setTimeout(() => {
    resizeCanvases();
    initSession();
  }, 150);

})();
