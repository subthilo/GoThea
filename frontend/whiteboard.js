// GoThea Whiteboard Engine (Milestone 5 Frontend)
// Ultra-Low-Latency Apple Pencil & Touch Canvas with Pixel-Eraser, Object-Eraser, Coalesced Events & AI Overlay

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
  let currentTool = "pen"; // 'pen', 'highlighter', 'pixel_eraser', 'object_eraser'
  let currentColor = "#f8fafc";
  let currentBaseWidth = 4;
  let currentSmoothWidth = 4;
  let penOnlyMode = true; // Palm rejection: ignore finger touch
  let activePointerId = null; // Track current active pencil/pen pointer
  let strokes = [];
  let undoStack = []; // Stores action history { type: 'add'|'delete'|'clear', ... }
  let redoStack = [];
  let currentStroke = null;
  let lastPoint = null;
  let dragDeletedItems = []; // For object_eraser drag session
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

  function computeBoundingBox(points) {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    }
    return { minX, maxX, minY, maxY };
  }

  // 3. Geometry Math for Object Eraser (Stroke Hit-Testing)
  function distToSegment(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const lenSq = dx * dx + dy * dy;
    if (lenSq === 0) {
      const sx = px - x1;
      const sy = py - y1;
      return Math.sqrt(sx * sx + sy * sy);
    }
    let t = ((px - x1) * dx + (py - y1) * dy) / lenSq;
    t = Math.max(0, Math.min(1, t));
    const cx = x1 + t * dx;
    const cy = y1 + t * dy;
    const ex = px - cx;
    const ey = py - cy;
    return Math.sqrt(ex * ex + ey * ey);
  }

  function strokeHitsPoint(stroke, px, py, radius) {
    if (!stroke.points || stroke.points.length === 0) return false;
    const threshold = radius + (stroke.width || 3) / 2;

    // Fast Bounding Box check
    if (stroke.bbox) {
      if (px < stroke.bbox.minX - threshold || px > stroke.bbox.maxX + threshold ||
          py < stroke.bbox.minY - threshold || py > stroke.bbox.maxY + threshold) {
        return false;
      }
    }

    const pts = stroke.points;
    if (pts.length === 1) {
      const dx = px - pts[0].x;
      const dy = py - pts[0].y;
      return (dx * dx + dy * dy) <= (threshold * threshold);
    }

    for (let i = 0; i < pts.length - 1; i++) {
      if (distToSegment(px, py, pts[i].x, pts[i].y, pts[i + 1].x, pts[i + 1].y) <= threshold) {
        return true;
      }
    }
    return false;
  }

  // 4. Tool Styles Setup
  function applyToolStyle(ctx, tool, color, baseWidth) {
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    if (tool === "pixel_eraser" || tool === "eraser") {
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
      inkCtx.fillStyle = (stroke.tool === "pixel_eraser" || stroke.tool === "eraser") ? "#000" : stroke.color;
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

  // 5. Ultra-Fluid Live Drawing Loop
  function drawLiveSegment(pt) {
    if (!lastPoint) {
      lastPoint = pt;
      return;
    }

    let targetWidth;
    if (currentTool === "pixel_eraser" || currentTool === "eraser") {
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

  function checkAndEraseObjectsAtPoint(pt) {
    const radius = Math.max(16, currentBaseWidth * 4);
    let hitAny = false;

    // Check backwards from newest to oldest
    for (let i = strokes.length - 1; i >= 0; i--) {
      if (strokeHitsPoint(strokes[i], pt.x, pt.y, radius)) {
        const removed = strokes.splice(i, 1)[0];
        dragDeletedItems.push({ stroke: removed, index: i });
        hitAny = true;
      }
    }

    if (hitAny) {
      redrawAllStrokes();
    }
  }

  function handlePointerDown(e) {
    // 1. IMMER preventDefault aufrufen, damit Safari NIE das 'Teilen...' Menü öffnet!
    e.preventDefault();

    // Palm Rejection: Berührungen mit Handfläche/Finger ignorieren im Pencil-Modus
    if (penOnlyMode && e.pointerType === "touch") {
      return;
    }

    // Wenn bereits ein Pointer zeichnet, Zweitberührungen ignorieren
    if (activePointerId !== null && activePointerId !== e.pointerId) {
      return;
    }

    activePointerId = e.pointerId;
    try {
      inkCanvas.setPointerCapture(e.pointerId);
    } catch (_) {}

    isDrawing = true;
    const pt = getEventPoint(e);
    lastPoint = pt;
    currentSmoothWidth = currentBaseWidth;

    if (currentTool === "object_eraser") {
      dragDeletedItems = [];
      checkAndEraseObjectsAtPoint(pt);
      return;
    }

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
    const isEraser = currentTool === "pixel_eraser" || currentTool === "eraser";
    const dotRadius = isEraser ? (currentBaseWidth * 2.5) : Math.max(1, currentBaseWidth / 2);
    inkCtx.arc(pt.x, pt.y, dotRadius, 0, Math.PI * 2);
    inkCtx.fillStyle = isEraser ? "#000" : currentColor;
    inkCtx.fill();
  }

  function handlePointerMove(e) {
    e.preventDefault();
    if (!isDrawing) return;
    if (activePointerId !== null && e.pointerId !== activePointerId) return;
    if (penOnlyMode && e.pointerType === "touch") return;

    const events = (e.getCoalescedEvents && e.getCoalescedEvents().length > 0)
      ? e.getCoalescedEvents()
      : [e];

    if (currentTool === "object_eraser") {
      for (let i = 0; i < events.length; i++) {
        const pt = getEventPoint(events[i]);
        checkAndEraseObjectsAtPoint(pt);
      }
      return;
    }

    if (!currentStroke) return;

    for (let i = 0; i < events.length; i++) {
      const pt = getEventPoint(events[i]);
      currentStroke.points.push(pt);
      drawLiveSegment(pt);
    }
  }

  function handlePointerUp(e) {
    e.preventDefault();
    if (activePointerId !== null && e.pointerId !== activePointerId) return;

    if (currentTool === "object_eraser") {
      if (dragDeletedItems.length > 0) {
        undoStack.push({ type: "delete_strokes", items: dragDeletedItems });
        redoStack = [];
        scheduleAutoSave();
      }
      dragDeletedItems = [];
    } else if (isDrawing && currentStroke && currentStroke.points.length > 0) {
      currentStroke.bbox = computeBoundingBox(currentStroke.points);
      strokes.push(currentStroke);
      undoStack.push({ type: "add_stroke", stroke: currentStroke });
      redoStack = [];
      sendCanvasUpdate([currentStroke]);
      scheduleAutoSave();
    }

    try {
      if (activePointerId !== null && inkCanvas.hasPointerCapture(e.pointerId)) {
        inkCanvas.releasePointerCapture(e.pointerId);
      }
    } catch (_) {}

    isDrawing = false;
    activePointerId = null;
    currentStroke = null;
    lastPoint = null;
  }

  // Pointer Event-Listener mit passive: false für e.preventDefault()
  inkCanvas.addEventListener("pointerdown", handlePointerDown, { passive: false });
  inkCanvas.addEventListener("pointermove", handlePointerMove, { passive: false });
  inkCanvas.addEventListener("pointerup", handlePointerUp, { passive: false });
  inkCanvas.addEventListener("pointercancel", handlePointerUp, { passive: false });

  // 100% Unterdrückung des iOS Safari 'Teilen...' Menüs und nativer Gesten
  const blockNativeGesture = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  inkCanvas.addEventListener("contextmenu", blockNativeGesture, { capture: true });
  viewport.addEventListener("contextmenu", blockNativeGesture, { capture: true });
  document.addEventListener("contextmenu", (e) => {
    if (e.target && e.target.closest && e.target.closest("#tab-whiteboard")) {
      e.preventDefault();
    }
  }, { capture: true });

  // Native Touch Events auf dem Canvas abfangen, damit WebKit keine Textselektion startet
  inkCanvas.addEventListener("touchstart", (e) => {
    e.preventDefault();
  }, { passive: false, capture: true });

  inkCanvas.addEventListener("touchmove", (e) => {
    e.preventDefault();
  }, { passive: false, capture: true });

  inkCanvas.addEventListener("touchend", (e) => {
    e.preventDefault();
  }, { passive: false, capture: true });

  inkCanvas.addEventListener("touchcancel", (e) => {
    e.preventDefault();
  }, { passive: false, capture: true });

  // 6. KI-Overlay Visualisierung
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

  // 7. Backend-Persistenz (Auto-Save OHNE teures toDataURL)
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
              strokes.forEach(s => {
                if (!s.bbox && s.points) s.bbox = computeBoundingBox(s.points);
              });
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
        undoStack = [];
        redoStack = [];
        redrawAllStrokes();
        connectTutorWebSocket();
      }
    } catch (e) {
      console.error("Fehler beim Erstellen einer neuen Sitzung:", e);
    }
  }

  // 8. WebSocket Verbindung
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

  // 9. Toolbar Event-Handler
  // Werkzeugauswahl (Stift, Marker, Pixelradierer, Objektradierer)
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

  // Farben (schaltet automatisch vom Radierer zum Stift um)
  document.querySelectorAll(".wb-color-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".wb-color-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentColor = btn.dataset.color;
      if (currentTool === "pixel_eraser" || currentTool === "object_eraser" || currentTool === "eraser") {
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

  // Leistungsstarkes Undo / Redo (unterstützt Striche, Objektradierer & Clear)
  if (btnUndo) {
    btnUndo.addEventListener("click", () => {
      if (undoStack.length === 0) return;
      const action = undoStack.pop();

      if (action.type === "add_stroke") {
        const idx = strokes.lastIndexOf(action.stroke);
        if (idx !== -1) {
          strokes.splice(idx, 1);
        }
        redoStack.push(action);
      } else if (action.type === "delete_strokes") {
        // Gelöschte Objekte wiederherstellen
        for (let i = action.items.length - 1; i >= 0; i--) {
          const item = action.items[i];
          strokes.splice(item.index, 0, item.stroke);
        }
        redoStack.push(action);
      } else if (action.type === "clear") {
        strokes = [...action.previous];
        redoStack.push(action);
      }

      redrawAllStrokes();
      scheduleAutoSave();
    });
  }

  if (btnRedo) {
    btnRedo.addEventListener("click", () => {
      if (redoStack.length === 0) return;
      const action = redoStack.pop();

      if (action.type === "add_stroke") {
        strokes.push(action.stroke);
        undoStack.push(action);
      } else if (action.type === "delete_strokes") {
        action.items.forEach(item => {
          const idx = strokes.indexOf(item.stroke);
          if (idx !== -1) {
            strokes.splice(idx, 1);
          }
        });
        undoStack.push(action);
      } else if (action.type === "clear") {
        strokes = [];
        undoStack.push(action);
      }

      redrawAllStrokes();
      scheduleAutoSave();
    });
  }

  // Tafel leeren (mit Undo-Rettung)
  if (btnClear) {
    btnClear.addEventListener("click", () => {
      if (strokes.length === 0) return;
      if (confirm("Möchtest du die gesamte Tafel leeren?")) {
        undoStack.push({ type: "clear", previous: [...strokes] });
        redoStack = [];
        strokes = [];
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

  // Tastenkombinationen (Undo: Cmd/Ctrl+Z, Redo: Cmd/Ctrl+Y, P: Stift, H: Marker, E: Radierer toggle)
  window.addEventListener("keydown", (e) => {
    const tabWb = document.getElementById("tab-whiteboard");
    if (!tabWb || !tabWb.classList.contains("active")) return;

    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
      e.preventDefault();
      btnUndo.click();
    } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "y") {
      e.preventDefault();
      btnRedo.click();
    } else if (!e.metaKey && !e.ctrlKey && e.key.toLowerCase() === "p") {
      const penBtn = document.querySelector('.wb-tool-btn[data-tool="pen"]');
      if (penBtn) penBtn.click();
    } else if (!e.metaKey && !e.ctrlKey && e.key.toLowerCase() === "h") {
      const hBtn = document.querySelector('.wb-tool-btn[data-tool="highlighter"]');
      if (hBtn) hBtn.click();
    } else if (!e.metaKey && !e.ctrlKey && e.key.toLowerCase() === "e") {
      // Toggle between pixel_eraser and object_eraser
      if (currentTool === "pixel_eraser") {
        const objBtn = document.querySelector('.wb-tool-btn[data-tool="object_eraser"]');
        if (objBtn) objBtn.click();
      } else {
        const pixBtn = document.querySelector('.wb-tool-btn[data-tool="pixel_eraser"]');
        if (pixBtn) pixBtn.click();
      }
    }
  });

  // Start
  setTimeout(() => {
    resizeCanvases();
    initSession();
  }, 150);

})();
