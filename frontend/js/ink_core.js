// GoThea Zeichenkern – Tafel und Dokument-Notizen: Ansicht & Zoom, Koordinaten & Druck, Radierer,
// Strichstil, Live-Zeichnen, Pointer-Events, iOS-Gesten-Sperren und Pinch.
// Unverändert aus whiteboard.js herausgelöst: Der Pencil-Kern ist fragil und mühsam erarbeitet.
// Änderungen am Schreibverhalten nur als eigene Commits, mit tests/e2e/test_pencil.py und auf dem iPad geprüft.
// Zustand, den auch whiteboard.js braucht, liegt hier und ist über das zurückgegebene Objekt erreichbar.

function createInkSurface(env) {
  const {
    viewport,
    inkCanvas,
    overlayCanvas,
    btnScrollTop,
    scrollTrack,
    scrollThumb,
    btnWbZoomIn,
    btnWbZoomOut,
    btnWbZoomReset,
    wbZoomLevelText,
    docUnderlay,
    docUnderlayImg,
    tasksLayer,
    inkCtx,
    overlayCtx,
    stopTutorSpeech,
    scheduleAutoSave,
    sendCanvasUpdate,
  } = env;

  // Gemeinsamer Zustand (bisher in whiteboard.js)
  let isUnderlayVisible = false;
  let isBookPageMode = false;
  let exercises = [];
  let currentSession = null;
  let isDrawing = false;
  let currentTool = "pen"; // 'pen', 'highlighter', 'pixel_eraser', 'object_eraser'
  let currentColor = "#f8fafc";
  let currentBaseWidth = 4;
  let currentSmoothWidth = 4;
  let penOnlyMode = true; // Palm rejection: ignore finger touch for drawing
  let activePointerId = null; // Track current active pencil/pen pointer
  let strokes = [];
  let undoStack = []; // Stores action history { type: 'add'|'delete'|'clear', ... }
  let redoStack = [];
  let currentStroke = null;
  let lastPoint = null;
  let lastMidPoint = null;
  let dragDeletedItems = []; // For object_eraser drag session
  let dpr = window.devicePixelRatio || 1;

  // Viewport Transform & Zoom
  let panX = 0;
  let panY = 0;
  let scale = 1.0;
  let zoomEnabled = true; // aus: Zwei Finger verschieben nur (Übungsblätter mit Kästchen fester Größe)
  const maxScale = () => (zoomEnabled ? 3.5 : 1.0);
  let activeTouches = new Map(); // pointerId -> { x, y }
  let isTwoFingerPanning = false;
  let scrollbarFadeTimer = null;
  let lastCaptureBounds = null;

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

      updateViewportPan();
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

  // 2. High-Precision Coordinate & Pressure Extractor (Board Virtual Coordinates)
  function getEventPoint(e) {
    const rect = inkCanvas.getBoundingClientRect();
    const pressure = (typeof e.pressure === "number" && e.pressure > 0) ? e.pressure : 0.5;
    const screenX = e.clientX - rect.left;
    const screenY = e.clientY - rect.top;
    return {
      x: (screenX - panX) / scale,
      y: (screenY - panY) / scale,
      screenX: screenX,
      screenY: screenY,
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

  // 3. Viewport Panning & Zooming
  function updateViewportPan() {
    inkCtx.setTransform(dpr * scale, 0, 0, dpr * scale, panX * dpr, panY * dpr);
    overlayCtx.setTransform(dpr * scale, 0, 0, dpr * scale, panX * dpr, panY * dpr);
    viewport.style.backgroundPositionY = `${panY}px`;
    viewport.style.backgroundPositionX = `${panX}px`;
    viewport.style.backgroundSize = `${24 * scale}px ${24 * scale}px`;

    if (docUnderlay && isUnderlayVisible) {
      docUnderlay.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
      docUnderlay.style.transformOrigin = "0 0";
    }

    if (tasksLayer) {
      tasksLayer.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
      tasksLayer.style.transformOrigin = "0 0";
    }

    redrawAllStrokes();
    updateScrollUI();
  }

  function setZoomLevel(newScale, centerScreenX = null, centerScreenY = null) {
    const rect = viewport.getBoundingClientRect();
    const cx = centerScreenX !== null ? centerScreenX : rect.width / 2;
    const cy = centerScreenY !== null ? centerScreenY : rect.height / 2;

    const clampedScale = Math.max(1.0, Math.min(maxScale(), Math.round(newScale * 100) / 100));
    if (Math.abs(clampedScale - scale) < 0.01) return;

    // Virtueller Punkt unter dem Zoom-Zentrum
    const vx = (cx - panX) / scale;
    const vy = (cy - panY) / scale;

    scale = clampedScale;

    if (scale === 1.0) {
      panX = 0;
      panY = Math.min(0, panY);
    } else {
      panX = cx - vx * scale;
      panY = cy - vy * scale;
    }

    updateViewportPan();
    updateZoomUI();
  }

  function updateZoomUI() {
    if (wbZoomLevelText) {
      wbZoomLevelText.textContent = `${Math.round(scale * 100)}%`;
    }
  }

  if (btnWbZoomIn) {
    btnWbZoomIn.addEventListener("click", () => setZoomLevel(scale + 0.35));
  }
  if (btnWbZoomOut) {
    btnWbZoomOut.addEventListener("click", () => setZoomLevel(scale - 0.35));
  }
  if (btnWbZoomReset) {
    btnWbZoomReset.addEventListener("click", () => setZoomLevel(1.0));
  }

  function updateScrollUI() {
    // "Zum Anfang" Button ein-/ausblenden
    if (btnScrollTop) {
      if (panY < -60) {
        btnScrollTop.style.display = "flex";
      } else {
        btnScrollTop.style.display = "none";
      }
    }

    // Scrollbar-Position berechnen
    if (scrollTrack && scrollThumb) {
      scrollTrack.classList.add("visible");
      clearTimeout(scrollbarFadeTimer);
      scrollbarFadeTimer = setTimeout(() => {
        scrollTrack.classList.remove("visible");
      }, 1200);

      let maxStrokeY = 0;
      for (let i = 0; i < strokes.length; i++) {
        if (strokes[i].bbox && strokes[i].bbox.maxY > maxStrokeY) {
          maxStrokeY = strokes[i].bbox.maxY;
        }
      }
      const viewH = viewport.clientHeight || 600;
      const totalH = Math.max(viewH, -panY + viewH, maxStrokeY + 400);

      const trackH = scrollTrack.clientHeight || (viewH - 24);
      const thumbH = Math.max(30, Math.min(trackH, (viewH / totalH) * trackH));
      scrollThumb.style.height = `${thumbH}px`;

      const maxScroll = Math.max(1, totalH - viewH);
      const scrollRatio = Math.min(1, Math.max(0, (-panY) / maxScroll));
      const thumbTop = scrollRatio * (trackH - thumbH);
      scrollThumb.style.top = `${thumbTop}px`;
    }
  }

  // Button: Sanft zum Anfang der Tafel springen
  if (btnScrollTop) {
    btnScrollTop.addEventListener("click", () => {
      const startPanY = panY;
      const startPanX = panX;
      const startScale = scale;
      const startTime = performance.now();
      const duration = 250;

      function anim(time) {
        const progress = Math.min(1, (time - startTime) / duration);
        const ease = 1 - Math.pow(1 - progress, 3);
        panY = startPanY * (1 - ease);
        panX = startPanX * (1 - ease);
        scale = startScale + (1.0 - startScale) * ease;
        updateViewportPan();
        updateZoomUI();
        if (progress < 1) {
          requestAnimationFrame(anim);
        } else {
          panY = 0;
          panX = 0;
          scale = 1.0;
          updateViewportPan();
          updateZoomUI();
        }
      }
      requestAnimationFrame(anim);
    });
  }

  // Mac Trackpad & Mausrad-Scrolling (Pinch-to-Zoom & Pan)
  function handleWheel(e) {
    e.preventDefault();
    if (e.ctrlKey) {
      // 2-Finger Trackpad Pinch on macOS (Chrome, Firefox, Safari)
      const rect = viewport.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      const zoomFactor = Math.exp(-e.deltaY * 0.01);
      setZoomLevel(scale * zoomFactor, cx, cy);
    } else {
      panY -= e.deltaY;
      panX -= e.deltaX;
      if (scale <= 1.01) {
        panX = 0;
        if (panY > 0) panY = 0;
      }
      updateViewportPan();
    }
  }

  viewport.addEventListener("wheel", handleWheel, { passive: false });
  inkCanvas.addEventListener("wheel", handleWheel, { passive: false });

  // 4. Geometry Math for Object Eraser (Stroke Hit-Testing)
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

  // 5. Tool Styles Setup
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

  function renderStrokeToContext(ctx, stroke) {
    if (!stroke.points || stroke.points.length === 0) return;

    ctx.save();
    applyToolStyle(ctx, stroke.tool, stroke.color, stroke.width);

    const pts = stroke.points;
    if (pts.length === 1) {
      ctx.beginPath();
      ctx.arc(pts[0].x, pts[0].y, Math.max(1, stroke.width / 2), 0, Math.PI * 2);
      ctx.fillStyle = (stroke.tool === "pixel_eraser" || stroke.tool === "eraser") ? "#000" : stroke.color;
      ctx.fill();
    } else if (pts.length === 2) {
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y);
      ctx.lineTo(pts[1].x, pts[1].y);
      ctx.stroke();
    } else {
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y);
      for (let j = 1; j < pts.length - 1; j++) {
        const midX = (pts[j].x + pts[j + 1].x) * 0.5;
        const midY = (pts[j].y + pts[j + 1].y) * 0.5;
        ctx.quadraticCurveTo(pts[j].x, pts[j].y, midX, midY);
      }
      const last = pts[pts.length - 1];
      ctx.lineTo(last.x, last.y);
      ctx.stroke();
    }

    ctx.restore();
  }

  function drawStoredStroke(stroke) {
    renderStrokeToContext(inkCtx, stroke);
  }

  // 6. Ultra-Fluid Live Drawing Loop
  function drawLiveSegment(pt) {
    if (!lastPoint) {
      lastPoint = pt;
      return;
    }

    let targetWidth;
    if (currentTool === "pixel_eraser" || currentTool === "eraser") {
      targetWidth = (currentBaseWidth * 5) / scale;
    } else if (currentTool === "highlighter") {
      targetWidth = (currentBaseWidth * 3.5) / scale;
    } else {
      targetWidth = Math.max(1.0, (currentBaseWidth * (0.35 + pt.pressure * 1.3)) / scale);
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
    const radius = Math.max(16, (currentBaseWidth * 4) / scale);
    let hitAny = false;

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

  // 7. Pointer Events Handling
  let activeDraggingCard = null;

  function handlePointerDown(e) {
    e.preventDefault();

    if (e.pointerType === "touch") {
      activeTouches.set(e.pointerId, { x: e.clientX, y: e.clientY });

      // Sobald 2 Finger aufliegen -> kein Zeichnen, Zwei-Finger-Scroll übernimmt
      if (activeTouches.size >= 2) {
        isTwoFingerPanning = true;
        if (activeDraggingCard) {
          activeDraggingCard = null;
        }
        if (isDrawing) {
          isDrawing = false;
          currentStroke = null;
          lastPoint = null;
          redrawAllStrokes();
        }
        return;
      }
    }

    if (isTwoFingerPanning) return;

    // Prüfen, ob der Klick/Touch auf interaktive Elemente einer Aufgabenkarte trifft
    if (typeof document.elementsFromPoint === "function") {
      const elementsUnder = document.elementsFromPoint(e.clientX, e.clientY) || [];
      const closeBtn = elementsUnder.find(el => el.classList && el.classList.contains("wb-task-close-btn"));
      if (closeBtn) {
        closeBtn.click();
        return;
      }

      const hintBtn = elementsUnder.find(el => el.classList && el.classList.contains("wb-task-hint-btn"));
      if (hintBtn) {
        hintBtn.click();
        return;
      }

      const checkBtn = elementsUnder.find(el => el.classList && el.classList.contains("wb-task-check-btn"));
      if (checkBtn) {
        checkBtn.click();
        return;
      }

      const taskHeader = elementsUnder.find(el => el.classList && el.classList.contains("wb-task-header"));
      if (taskHeader && !elementsUnder.some(el => el.classList && el.classList.contains("wb-task-close-btn"))) {
        const card = taskHeader.closest(".wb-task-card");
        const exId = card ? card.id.replace("wb-exercise-", "") : null;
        const ex = exercises.find(item => item.id === exId);
        if (card && ex) {
          activeDraggingCard = {
            card,
            ex,
            pointerId: e.pointerId,
            startScreenX: e.clientX,
            startScreenY: e.clientY,
            startPosX: ex.pos_x || 60,
            startPosY: ex.pos_y || 80
          };
          card.style.zIndex = "10";
          try {
            inkCanvas.setPointerCapture(e.pointerId);
          } catch (_) {}
          return;
        }
      }
    }

    // Im Pencil-Modus wird 1 einzelner Touch ignoriert
    if (e.pointerType === "touch" && penOnlyMode) {
      return;
    }

    if (activePointerId !== null && activePointerId !== e.pointerId) return;

    activePointerId = e.pointerId;
    try {
      inkCanvas.setPointerCapture(e.pointerId);
    } catch (_) {}

    // Barge-In: Sprachausgabe sofort stoppen, sobald die Schülerin den Stift ansetzt
    stopTutorSpeech();

    isDrawing = true;
    const pt = getEventPoint(e);

    // Strikte Begrenzung im Buchseiten-Modus: Kein Malen außerhalb der Buchseite!
    if (isBookPageMode && docUnderlayImg) {
      const dx = docUnderlayImg.offsetLeft || 0;
      const dy = docUnderlayImg.offsetTop || 0;
      const dw = docUnderlayImg.offsetWidth || docUnderlayImg.naturalWidth;
      const dh = docUnderlayImg.offsetHeight || docUnderlayImg.naturalHeight;
      if (dw > 0 && dh > 0) {
        if (pt.x < dx || pt.x > dx + dw || pt.y < dy || pt.y > dy + dh) {
          isDrawing = false;
          activePointerId = null;
          try {
            if (inkCanvas.hasPointerCapture(e.pointerId)) {
              inkCanvas.releasePointerCapture(e.pointerId);
            }
          } catch (_) {}
          return;
        }
      }
    }

    lastPoint = pt;
    lastMidPoint = pt;
    const strokeWidth = currentBaseWidth / scale;
    currentSmoothWidth = strokeWidth;

    if (currentTool === "object_eraser") {
      dragDeletedItems = [];
      checkAndEraseObjectsAtPoint(pt);
      return;
    }

    currentStroke = {
      tool: currentTool,
      color: currentColor,
      width: strokeWidth,
      points: [pt]
    };

    applyToolStyle(inkCtx, currentTool, currentColor, strokeWidth);

    inkCtx.beginPath();
    const isEraser = currentTool === "pixel_eraser" || currentTool === "eraser";
    const dotRadius = isEraser ? (strokeWidth * 2.5) : Math.max(0.5, strokeWidth / 2);
    inkCtx.arc(pt.x, pt.y, dotRadius, 0, Math.PI * 2);
    inkCtx.fillStyle = isEraser ? "#000" : currentColor;
    inkCtx.fill();
  }

  function handlePointerMove(e) {
    e.preventDefault();

    if (activeDraggingCard) {
      if (e.pointerId !== activeDraggingCard.pointerId) return;
      const dx = (e.clientX - activeDraggingCard.startScreenX) / scale;
      const dy = (e.clientY - activeDraggingCard.startScreenY) / scale;
      const newX = Math.round(activeDraggingCard.startPosX + dx);
      const newY = Math.round(Math.max(20, activeDraggingCard.startPosY + dy));
      activeDraggingCard.card.style.left = `${newX}px`;
      activeDraggingCard.card.style.top = `${newY}px`;
      return;
    }

    // Wenn zwei Finger auf dem Glas liegen, zeichnen wir nicht
    if (isTwoFingerPanning) return;
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

    if (!currentStroke || !lastPoint || !lastMidPoint) return;

    inkCtx.beginPath();
    inkCtx.moveTo(lastMidPoint.x, lastMidPoint.y);
    for (let i = 0; i < events.length; i++) {
      const pt = getEventPoint(events[i]);
      if (isBookPageMode && docUnderlayImg) {
        const dx = docUnderlayImg.offsetLeft || 0;
        const dy = docUnderlayImg.offsetTop || 0;
        const dw = docUnderlayImg.offsetWidth || docUnderlayImg.naturalWidth;
        const dh = docUnderlayImg.offsetHeight || docUnderlayImg.naturalHeight;
        if (dw > 0 && dh > 0) {
          pt.x = Math.max(dx, Math.min(dx + dw, pt.x));
          pt.y = Math.max(dy, Math.min(dy + dh, pt.y));
        }
      }
      currentStroke.points.push(pt);

      const midX = (lastPoint.x + pt.x) * 0.5;
      const midY = (lastPoint.y + pt.y) * 0.5;
      inkCtx.quadraticCurveTo(lastPoint.x, lastPoint.y, midX, midY);

      lastPoint = pt;
      lastMidPoint = { x: midX, y: midY };
    }
    inkCtx.stroke();
  }

  function handlePointerUp(e) {
    e.preventDefault();

    if (activeDraggingCard) {
      if (e.pointerId === activeDraggingCard.pointerId) {
        const dragging = activeDraggingCard;
        activeDraggingCard = null;
        try {
          inkCanvas.releasePointerCapture(e.pointerId);
        } catch (_) {}
        dragging.card.style.zIndex = "2";
        const dx = (e.clientX - dragging.startScreenX) / scale;
        const dy = (e.clientY - dragging.startScreenY) / scale;
        dragging.ex.pos_x = Math.round(dragging.startPosX + dx);
        dragging.ex.pos_y = Math.round(Math.max(20, dragging.startPosY + dy));
        if (currentSession) {
          try {
            fetch(`/api/v1/whiteboard/sessions/${currentSession.id}/exercises/${dragging.ex.id}/position`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ pos_x: dragging.ex.pos_x, pos_y: dragging.ex.pos_y })
            }).catch(console.warn);
          } catch (err) {
            console.warn("Fehler beim Speichern der Aufgabenposition:", err);
          }
        }
      }
      return;
    }

    if (e.pointerType === "touch") {
      activeTouches.delete(e.pointerId);
      if (activeTouches.size < 2) {
        isTwoFingerPanning = false;
      }
    }

    if (isTwoFingerPanning) return;
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
      if (!isBookPageMode) {
        sendCanvasUpdate([currentStroke]);
      }
      scheduleAutoSave();
    }

    try {
      if (activePointerId !== null && inkCanvas.hasPointerCapture(e.pointerId)) {
        inkCanvas.releasePointerCapture(e.pointerId);
      }
    } catch (_) {}

    if (lastMidPoint && lastPoint && (lastMidPoint.x !== lastPoint.x || lastMidPoint.y !== lastPoint.y)) {
      inkCtx.beginPath();
      inkCtx.moveTo(lastMidPoint.x, lastMidPoint.y);
      inkCtx.lineTo(lastPoint.x, lastPoint.y);
      inkCtx.stroke();
    }

    isDrawing = false;
    activePointerId = null;
    currentStroke = null;
    lastPoint = null;
    lastMidPoint = null;
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
    if (!e.target.closest("input, textarea")) {
      e.preventDefault();
    }
  }, { capture: true });

  // Globale Unterdrückung von iOS Safari Textselektion & 'Teilen...'-Callouts
  document.addEventListener("selectstart", (e) => {
    if (!e.target.closest("input, textarea")) {
      e.preventDefault();
    }
  }, { capture: true });

  document.addEventListener("selectionchange", () => {
    const activeEl = document.activeElement;
    if (!activeEl || (!activeEl.matches("input, textarea") && !activeEl.isContentEditable)) {
      const sel = window.getSelection();
      if (sel && sel.rangeCount > 0) {
        sel.removeAllRanges();
      }
    }
  });

  // 2-Finger Mac Safari Trackpad Pinch-to-Zoom
  let gestureStartScale = 1.0;
  const handleGestureStart = (e) => {
    e.preventDefault();
    gestureStartScale = scale;
  };
  const handleGestureChange = (e) => {
    e.preventDefault();
    const rect = viewport.getBoundingClientRect();
    const cx = (typeof e.clientX === "number" && e.clientX > 0) ? (e.clientX - rect.left) : (rect.width / 2);
    const cy = (typeof e.clientY === "number" && e.clientY > 0) ? (e.clientY - rect.top) : (rect.height / 2);
    setZoomLevel(gestureStartScale * e.scale, cx, cy);
  };
  const handleGestureEnd = (e) => {
    e.preventDefault();
  };

  inkCanvas.addEventListener("gesturestart", handleGestureStart, { passive: false, capture: true });
  inkCanvas.addEventListener("gesturechange", handleGestureChange, { passive: false, capture: true });
  inkCanvas.addEventListener("gestureend", handleGestureEnd, { passive: false, capture: true });
  viewport.addEventListener("gesturestart", handleGestureStart, { passive: false, capture: true });
  viewport.addEventListener("gesturechange", handleGestureChange, { passive: false, capture: true });
  viewport.addEventListener("gestureend", handleGestureEnd, { passive: false, capture: true });

  viewport.addEventListener("touchstart", (e) => {
    if (!e.target.closest(".wb-floating-toolbar, button, select, input, textarea")) {
      e.preventDefault();
    }
  }, { passive: false });

  // 1:1 Physikalisches Zwei-Finger-Pinch-to-Zoom & Pan (Touch Events)
  let touchStartDist = null;
  let touchStartScale = 1.0;
  let pinchVirtualX = null;
  let pinchVirtualY = null;

  inkCanvas.addEventListener("touchstart", (e) => {
    // IMMER e.preventDefault(), um WebKit Edit-Menu ('Teilen...') bei schnellem Stiftansetzen zu blockieren
    e.preventDefault();
    if (e.touches.length === 2) {
      isTwoFingerPanning = true;
      if (isDrawing) {
        isDrawing = false;
        currentStroke = null;
        lastPoint = null;
        redrawAllStrokes();
      }
      const rect = inkCanvas.getBoundingClientRect();
      const t1 = e.touches[0];
      const t2 = e.touches[1];
      const cx = (t1.clientX + t2.clientX) / 2 - rect.left;
      const cy = (t1.clientY + t2.clientY) / 2 - rect.top;
      const dist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);

      touchStartDist = dist;
      touchStartScale = scale;

      pinchVirtualX = (cx - panX) / scale;
      pinchVirtualY = (cy - panY) / scale;
    }
  }, { passive: false, capture: true });

  inkCanvas.addEventListener("touchmove", (e) => {
    e.preventDefault();
    if (e.touches.length === 2 && touchStartDist !== null) {
      const rect = inkCanvas.getBoundingClientRect();
      const t1 = e.touches[0];
      const t2 = e.touches[1];
      const cx = (t1.clientX + t2.clientX) / 2 - rect.left;
      const cy = (t1.clientY + t2.clientY) / 2 - rect.top;
      const dist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);

      // Pinch Zoom
      if (touchStartDist > 15) {
        const ratio = dist / touchStartDist;
        scale = Math.max(1.0, Math.min(maxScale(), touchStartScale * ratio));
      }

      let newPanX = cx - pinchVirtualX * scale;
      let newPanY = cy - pinchVirtualY * scale;

      if (scale <= 1.01) {
        scale = 1.0;
        newPanX = 0;
        newPanY = Math.min(0, newPanY);
      } else {
        const maxPanX = rect.width * 0.5;
        const minPanX = -rect.width * (scale - 0.5);
        newPanX = Math.max(minPanX, Math.min(maxPanX, newPanX));
        newPanY = Math.min(80 * scale, newPanY);
      }

      panX = newPanX;
      panY = newPanY;

      updateViewportPan();
      updateZoomUI();
    }
  }, { passive: false, capture: true });

  inkCanvas.addEventListener("touchend", (e) => {
    e.preventDefault();
    if (e.touches.length < 2) {
      touchStartDist = null;
      pinchVirtualX = null;
      pinchVirtualY = null;
      isTwoFingerPanning = false;
    }
  }, { passive: false, capture: true });

  inkCanvas.addEventListener("touchcancel", (e) => {
    e.preventDefault();
    touchStartDist = null;
    pinchVirtualX = null;
    pinchVirtualY = null;
    isTwoFingerPanning = false;
  }, { passive: false, capture: true });

  return {
    get isUnderlayVisible() { return isUnderlayVisible; },
    set isUnderlayVisible(value) { isUnderlayVisible = value; },
    get isBookPageMode() { return isBookPageMode; },
    set isBookPageMode(value) { isBookPageMode = value; },
    get exercises() { return exercises; },
    set exercises(value) { exercises = value; },
    get currentSession() { return currentSession; },
    set currentSession(value) { currentSession = value; },
    get isDrawing() { return isDrawing; },
    set isDrawing(value) { isDrawing = value; },
    get zoomEnabled() { return zoomEnabled; },
    set zoomEnabled(value) { zoomEnabled = value; if (!value) setZoomLevel(1.0); },
    get currentTool() { return currentTool; },
    set currentTool(value) { currentTool = value; },
    get currentColor() { return currentColor; },
    set currentColor(value) { currentColor = value; },
    get currentBaseWidth() { return currentBaseWidth; },
    set currentBaseWidth(value) { currentBaseWidth = value; },
    get currentSmoothWidth() { return currentSmoothWidth; },
    set currentSmoothWidth(value) { currentSmoothWidth = value; },
    get penOnlyMode() { return penOnlyMode; },
    set penOnlyMode(value) { penOnlyMode = value; },
    get activePointerId() { return activePointerId; },
    set activePointerId(value) { activePointerId = value; },
    get strokes() { return strokes; },
    set strokes(value) { strokes = value; },
    get undoStack() { return undoStack; },
    set undoStack(value) { undoStack = value; },
    get redoStack() { return redoStack; },
    set redoStack(value) { redoStack = value; },
    get currentStroke() { return currentStroke; },
    set currentStroke(value) { currentStroke = value; },
    get lastPoint() { return lastPoint; },
    set lastPoint(value) { lastPoint = value; },
    get lastMidPoint() { return lastMidPoint; },
    set lastMidPoint(value) { lastMidPoint = value; },
    get dragDeletedItems() { return dragDeletedItems; },
    set dragDeletedItems(value) { dragDeletedItems = value; },
    get dpr() { return dpr; },
    set dpr(value) { dpr = value; },
    get panX() { return panX; },
    set panX(value) { panX = value; },
    get panY() { return panY; },
    set panY(value) { panY = value; },
    get scale() { return scale; },
    set scale(value) { scale = value; },
    get lastCaptureBounds() { return lastCaptureBounds; },
    set lastCaptureBounds(value) { lastCaptureBounds = value; },
    resizeCanvases,
    computeBoundingBox,
    updateViewportPan,
    redrawAllStrokes,
    renderStrokeToContext,
  };
}
