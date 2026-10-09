// GoThea Whiteboard Engine (Milestone 5 Frontend)
// Low-Latency Apple Pencil / Touch 2D Canvas with HiDPI, Palm Rejection & AI Tutor Overlay

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
    return; // Tab nicht vorhanden
  }

  const inkCtx = inkCanvas.getContext("2d");
  const overlayCtx = overlayCanvas.getContext("2d");

  // State
  let currentSession = null;
  let tutorSocket = null;
  let isDrawing = false;
  let currentTool = "pen"; // 'pen', 'highlighter', 'eraser'
  let currentColor = "#f8fafc";
  let currentBaseWidth = 4;
  let penOnlyMode = true; // Palm rejection: ignore finger touch when active
  let strokes = []; // Array aller Striche für Replay & Undo/Redo
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
    inkCanvas.width = rect.width * dpr;
    inkCanvas.height = rect.height * dpr;
    overlayCanvas.width = rect.width * dpr;
    overlayCanvas.height = rect.height * dpr;

    inkCanvas.style.width = `${rect.width}px`;
    inkCanvas.style.height = `${rect.height}px`;
    overlayCanvas.style.width = `${rect.width}px`;
    overlayCanvas.style.height = `${rect.height}px`;

    inkCtx.scale(dpr, dpr);
    overlayCtx.scale(dpr, dpr);

    redrawAllStrokes();
  }

  window.addEventListener("resize", () => {
    resizeCanvases();
  });

  // Re-adjust canvas whenever the whiteboard tab is activated
  document.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      if (tab.dataset.tab === "whiteboard") {
        setTimeout(resizeCanvases, 50);
      }
    });
  });

  // 2. Stroke Rendering & Smoothing
  function getCanvasCoords(e) {
    const rect = inkCanvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      pressure: e.pressure && e.pressure > 0 ? e.pressure : 0.5,
      pointerType: e.pointerType || "mouse"
    };
  }

  function redrawAllStrokes() {
    inkCtx.clearRect(0, 0, inkCanvas.width / dpr, inkCanvas.height / dpr);

    strokes.forEach(stroke => {
      drawSingleStroke(stroke);
    });
  }

  function drawSingleStroke(stroke) {
    if (!stroke.points || stroke.points.length === 0) return;

    inkCtx.save();
    inkCtx.lineCap = "round";
    inkCtx.lineJoin = "round";

    if (stroke.tool === "eraser") {
      inkCtx.globalCompositeOperation = "destination-out";
      inkCtx.strokeStyle = "rgba(0,0,0,1)";
      inkCtx.lineWidth = stroke.width * 4;
    } else if (stroke.tool === "highlighter") {
      inkCtx.globalCompositeOperation = "source-over";
      inkCtx.globalAlpha = 0.35;
      inkCtx.strokeStyle = stroke.color;
      inkCtx.lineWidth = stroke.width * 3.5;
    } else {
      inkCtx.globalCompositeOperation = "source-over";
      inkCtx.globalAlpha = 1.0;
      inkCtx.strokeStyle = stroke.color;
      inkCtx.lineWidth = stroke.width;
    }

    if (stroke.points.length === 1) {
      const p = stroke.points[0];
      inkCtx.beginPath();
      inkCtx.arc(p.x, p.y, (stroke.width * (0.5 + p.pressure * 0.8)) / 2, 0, Math.PI * 2);
      inkCtx.fillStyle = stroke.tool === "eraser" ? "#000" : stroke.color;
      inkCtx.fill();
      inkCtx.restore();
      return;
    }

    inkCtx.beginPath();
    inkCtx.moveTo(stroke.points[0].x, stroke.points[0].y);

    for (let i = 1; i < stroke.points.length - 1; i++) {
      const xc = (stroke.points[i].x + stroke.points[i + 1].x) / 2;
      const yc = (stroke.points[i].y + stroke.points[i + 1].y) / 2;
      inkCtx.quadraticCurveTo(stroke.points[i].x, stroke.points[i].y, xc, yc);
    }

    const last = stroke.points[stroke.points.length - 1];
    inkCtx.lineTo(last.x, last.y);
    inkCtx.stroke();
    inkCtx.restore();
  }

  // 3. Pointer Events (Pencil & Touch Handling)
  function handlePointerDown(e) {
    // Palm Rejection: Ignore touch if pencil-only is turned on
    if (penOnlyMode && e.pointerType === "touch") {
      return;
    }

    inkCanvas.setPointerCapture(e.pointerId);
    isDrawing = true;
    redoStack = []; // Reset Redo Stack bei neuem Strich

    const pt = getCanvasCoords(e);
    lastPoint = pt;

    currentStroke = {
      tool: currentTool,
      color: currentColor,
      width: currentBaseWidth,
      points: [pt]
    };

    // Barge-In Signal an WebSocket (falls KI gerade spricht oder aktiv ist)
    notifyTutorInterrupt();

    // Sofort ersten Punkt visualisieren
    inkCtx.save();
    inkCtx.lineCap = "round";
    inkCtx.lineJoin = "round";
    if (currentTool === "eraser") {
      inkCtx.globalCompositeOperation = "destination-out";
      inkCtx.lineWidth = currentBaseWidth * 4;
      inkCtx.strokeStyle = "#000";
    } else if (currentTool === "highlighter") {
      inkCtx.globalAlpha = 0.35;
      inkCtx.lineWidth = currentBaseWidth * 3.5;
      inkCtx.strokeStyle = currentColor;
    } else {
      inkCtx.lineWidth = currentBaseWidth * (0.5 + pt.pressure * 0.8);
      inkCtx.strokeStyle = currentColor;
    }

    inkCtx.beginPath();
    inkCtx.arc(pt.x, pt.y, inkCtx.lineWidth / 2, 0, Math.PI * 2);
    inkCtx.fillStyle = currentTool === "eraser" ? "#000" : currentColor;
    inkCtx.fill();
    inkCtx.restore();
  }

  function handlePointerMove(e) {
    if (!isDrawing || !currentStroke) return;
    if (penOnlyMode && e.pointerType === "touch") return;

    const pt = getCanvasCoords(e);
    currentStroke.points.push(pt);

    // Live Liniensegment zeichnen
    inkCtx.save();
    inkCtx.lineCap = "round";
    inkCtx.lineJoin = "round";

    if (currentTool === "eraser") {
      inkCtx.globalCompositeOperation = "destination-out";
      inkCtx.lineWidth = currentBaseWidth * 4;
      inkCtx.strokeStyle = "#000";
    } else if (currentTool === "highlighter") {
      inkCtx.globalAlpha = 0.35;
      inkCtx.lineWidth = currentBaseWidth * 3.5;
      inkCtx.strokeStyle = currentColor;
    } else {
      inkCtx.lineWidth = currentBaseWidth * (0.5 + pt.pressure * 0.8);
      inkCtx.strokeStyle = currentColor;
    }

    inkCtx.beginPath();
    inkCtx.moveTo(lastPoint.x, lastPoint.y);
    const xc = (lastPoint.x + pt.x) / 2;
    const yc = (lastPoint.y + pt.y) / 2;
    inkCtx.quadraticCurveTo(lastPoint.x, lastPoint.y, xc, yc);
    inkCtx.stroke();
    inkCtx.restore();

    lastPoint = pt;
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

  inkCanvas.addEventListener("pointerdown", handlePointerDown);
  inkCanvas.addEventListener("pointermove", handlePointerMove);
  inkCanvas.addEventListener("pointerup", handlePointerUp);
  inkCanvas.addEventListener("pointercancel", handlePointerUp);

  // 4. KI-Overlay Visualisierung
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

        // Pulsierendes Leuchten
        overlayCtx.shadowColor = item.color || "#f59e0b";
        overlayCtx.shadowBlur = 12;
        overlayCtx.stroke();
        overlayCtx.restore();
      } else if (item.action === "latex_hint") {
        overlayCtx.save();
        overlayCtx.fillStyle = "#ffffff";
        overlayCtx.font = "600 16px -apple-system, BlinkMacSystemFont, sans-serif";
        const coords = item.coords || { x: 100, y: 100 };

        // Hint-Badge
        overlayCtx.fillStyle = "rgba(30, 41, 59, 0.95)";
        overlayCtx.strokeStyle = "#6366f1";
        overlayCtx.lineWidth = 1.5;
        overlayCtx.beginPath();
        overlayCtx.roundRect(coords.x - 10, coords.y - 25, 380, 42, 8);
        overlayCtx.fill();
        overlayCtx.stroke();

        overlayCtx.fillStyle = "#f8fafc";
        overlayCtx.fillText(item.latex || "Hinweis des KI-Tutors", coords.x + 6, coords.y);
        overlayCtx.restore();
      } else if (item.action === "clear") {
        overlayCtx.clearRect(0, 0, overlayCanvas.width / dpr, overlayCanvas.height / dpr);
      }
    });

    // Automatisches Ausblenden des Overlays nach 12 Sekunden
    setTimeout(() => {
      overlayCtx.clearRect(0, 0, overlayCanvas.width / dpr, overlayCanvas.height / dpr);
    }, 12000);
  }

  // 5. Backend-Persistenz & Auto-Save
  function scheduleAutoSave() {
    clearTimeout(saveDebounceTimer);
    saveDebounceTimer = setTimeout(async () => {
      if (!currentSession) return;
      try {
        const payload = {
          board_state_json: JSON.stringify(strokes),
          snapshot_data_url: inkCanvas.toDataURL("image/png")
        };
        await fetch(`/api/v1/whiteboard/sessions/${currentSession.id}/state`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      } catch (err) {
        console.error("Auto-Save Fehler:", err);
      }
    }, 1200);
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

  // 6. WebSocket Verbindung (Echtzeit-Kanal)
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
        wsStatus.textContent = "Getrennt (Offline-Modus)";
      };
    } catch (e) {
      console.error("WebSocket Verbindungsfehler:", e);
    }
  }

  function notifyTutorInterrupt() {
    if (tutorSocket && tutorSocket.readyState === WebSocket.OPEN) {
      tutorSocket.send(JSON.stringify({
        type: "user_interrupt",
        reason: "pencil_touch",
        timestamp: Date.now()
      }));
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

  // 7. Toolbar Event-Handler
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
      // Falls Radierer aktiv war, zurück zum Stift schalten
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

  // Neuer Sitzungs-Button
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

  // KI-Tipp Anfordern (Löst Demonstration auf Overlay aus)
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

  // Tastenkombinationen (Undo: Cmd/Ctrl+Z, Redo: Cmd/Ctrl+Y, Stift: P, Eraser: E)
  window.addEventListener("keydown", (e) => {
    // Nur aktiv, wenn Tab "whiteboard" sichtbar ist
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

  // Start Initialization
  setTimeout(() => {
    resizeCanvases();
    initSession();
  }, 200);

})();
