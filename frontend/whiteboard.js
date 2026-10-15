// GoThea Whiteboard Engine (Milestone 5 Frontend)
// Ultra-Low-Latency Apple Pencil Canvas with Infinite Vertical Expansion, Two-Finger Scroll, Pixel/Object Eraser & AI Overlay

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
  const btnScrollTop = document.getElementById("btn-wb-scroll-top");
  const scrollTrack = document.getElementById("wb-scroll-track");
  const scrollThumb = document.getElementById("wb-scroll-thumb");

  // Zoom Steuerung
  const btnWbZoomIn = document.getElementById("btn-wb-zoom-in");
  const btnWbZoomOut = document.getElementById("btn-wb-zoom-out");
  const btnWbZoomReset = document.getElementById("btn-wb-zoom-reset");
  const wbZoomLevelText = document.getElementById("wb-zoom-level-text");

  // Audio- & Tutor-Elemente
  const btnAudioToggle = document.getElementById("btn-wb-audio-toggle");
  const tutorBubble = document.getElementById("wb-tutor-bubble");
  const tutorSpeechText = document.getElementById("wb-tutor-speech-text");
  const btnStopSpeech = document.getElementById("btn-wb-stop-speech");
  const hintIcon = document.getElementById("wb-hint-icon");
  const hintLabel = document.getElementById("wb-hint-label");

  // Unterlagen- & Arbeitsblatt-Elemente
  const materialSelect = document.getElementById("wb-material-select");
  const btnToggleUnderlay = document.getElementById("btn-wb-toggle-underlay");
  const docUnderlay = document.getElementById("wb-doc-underlay");
  const docUnderlayImg = document.getElementById("wb-doc-underlay-img");
  const docTopbar = document.getElementById("wb-doc-topbar");
  const docBadge = document.getElementById("wb-doc-badge");
  const docTitle = document.getElementById("wb-doc-title");
  const docPageInfo = document.getElementById("wb-doc-page-info");
  const btnDocPrev = document.getElementById("btn-wb-doc-prev");
  const btnDocNext = document.getElementById("btn-wb-doc-next");
  const btnDocClose = document.getElementById("btn-wb-doc-close");
  const btnReturnToBook = document.getElementById("btn-wb-doc-return-to-book");
  const docSaveStatus = document.getElementById("wb-doc-save-status");

  let currentTutorAudio = null;
  let tutorAudioEnabled = true;

  let currentSubjectMaterialsList = [];
  let activeMaterial = null;
  let activeMaterialPage = 1;
  let isUnderlayVisible = false;

  // Modus: Buchseite auf der Tafel beschreiben
  let isBookPageMode = false;
  let bookPageContext = null; // { materialId, page, pageCount, title, subjectId }
  let bookPageSaveDebounceTimer = null;

  // Interaktive Aufgaben-Ebene & Modal
  const tasksLayer = document.getElementById("wb-tasks-layer");
  const btnPlaceExercise = document.getElementById("btn-wb-place-exercise");
  const exerciseModal = document.getElementById("wb-exercise-modal");
  const btnExerciseModalClose = document.getElementById("btn-wb-exercise-modal-close");
  const btnExerciseCancel = document.getElementById("btn-wb-exercise-cancel");
  const btnExerciseSubmit = document.getElementById("btn-wb-exercise-submit");
  const btnExerciseSubmitLabel = document.getElementById("btn-wb-exercise-submit-label");
  const exerciseTypeSelect = document.getElementById("wb-exercise-type-select");
  const exerciseTopicInput = document.getElementById("wb-exercise-topic-input");
  const exerciseDiffSelect = document.getElementById("wb-exercise-difficulty-select");
  const exercisePromptInput = document.getElementById("wb-exercise-custom-prompt");

  let exercises = [];

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
  let saveDebounceTimer = null;

  // Viewport Transform & Zoom
  let panX = 0;
  let panY = 0;
  let scale = 1.0;
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

    const clampedScale = Math.max(1.0, Math.min(3.5, Math.round(newScale * 100) / 100));
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
        scale = Math.max(1.0, Math.min(3.5, touchStartScale * ratio));
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

  // 8. KI-Overlay Visualisierung
  function drawOverlayActions(actions) {
    overlayCtx.clearRect(0, 0, overlayCanvas.width / dpr, overlayCanvas.height / dpr);

    const boardW = overlayCanvas.width / dpr;
    const boardH = overlayCanvas.height / dpr;

    actions.forEach(item => {
      if (item.action === "highlight_box" && item.coords) {
        let x = item.coords.x || 0;
        let y = item.coords.y || 0;
        let w = item.coords.w || 200;
        let h = item.coords.h || 60;

        if (item.coords.x_pct !== undefined) {
          if (lastCaptureBounds) {
            x = lastCaptureBounds.minX + (item.coords.x_pct / 100) * lastCaptureBounds.width;
            y = lastCaptureBounds.minY + (item.coords.y_pct / 100) * lastCaptureBounds.height;
            w = (item.coords.w_pct / 100) * lastCaptureBounds.width;
            h = (item.coords.h_pct / 100) * lastCaptureBounds.height;
          } else {
            x = (item.coords.x_pct / 100) * boardW;
            y = (item.coords.y_pct / 100) * boardH;
            w = (item.coords.w_pct / 100) * boardW;
            h = (item.coords.h_pct / 100) * boardH;
          }
        }

        overlayCtx.save();
        overlayCtx.strokeStyle = item.color || "#f59e0b";
        overlayCtx.lineWidth = 3;
        overlayCtx.fillStyle = "rgba(245, 158, 11, 0.12)";
        overlayCtx.beginPath();
        overlayCtx.roundRect(x, y, w, h, 12);
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
    }, 14000);
  }

  // Audio- & Sprachsteuerung des KI-Tutors (OpenAI TTS 'nova' & Barge-In)
  function stopTutorSpeech() {
    if (currentTutorAudio) {
      try {
        currentTutorAudio.pause();
        currentTutorAudio.currentTime = 0;
      } catch (_) {}
      currentTutorAudio = null;
    }
    if (tutorBubble) {
      tutorBubble.style.display = "none";
    }
  }

  function playTutorSpeech(audioBase64, speechText) {
    stopTutorSpeech();

    // Sprechblase auf der Tafel einblenden
    if (tutorBubble && speechText) {
      if (tutorSpeechText) tutorSpeechText.textContent = speechText;
      tutorBubble.style.display = "flex";
    }

    if (!tutorAudioEnabled || !audioBase64) return;

    try {
      const audioUrl = `data:audio/mp3;base64,${audioBase64}`;
      currentTutorAudio = new Audio(audioUrl);

      currentTutorAudio.onended = () => {
        setTimeout(() => {
          if (tutorBubble) tutorBubble.style.display = "none";
        }, 5000);
      };

      currentTutorAudio.onerror = (err) => {
        console.warn("Audio-Wiedergabefehler:", err);
      };

      currentTutorAudio.play().catch((err) => {
        console.warn("Autoplay im Browser blockiert:", err);
      });
    } catch (err) {
      console.warn("Fehler bei Audio-Initialisierung:", err);
    }
  }

  function captureBoardSnapshot() {
    const isChalk = viewport.classList.contains("pattern-chalkboard") ||
      (!viewport.classList.contains("pattern-white") && !viewport.classList.contains("pattern-lines") && !viewport.classList.contains("pattern-grid"));

    const viewW = viewport.clientWidth || 1024;
    const viewH = viewport.clientHeight || 768;

    // Aktueller Bildschirmausschnitt in Weltkoordinaten
    const viewLeft = -panX / scale;
    const viewTop = -panY / scale;
    const viewRight = (-panX + viewW) / scale;
    const viewBottom = (-panY + viewH) / scale;

    // Gesamten Tafelbereich berechnen (von y=0 ganz oben bis ganz unten)
    let minWorldX = 0;
    let minWorldY = 0; // Immer ganz oben anfangen!
    let maxWorldX = Math.max(viewW, viewRight);
    let maxWorldY = Math.max(viewH, viewBottom);

    // Alle Striche der Tafel einbeziehen
    for (let i = 0; i < strokes.length; i++) {
      const s = strokes[i];
      if (s.bbox) {
        if (s.bbox.minX < minWorldX) minWorldX = s.bbox.minX;
        if (s.bbox.maxX > maxWorldX) maxWorldX = s.bbox.maxX;
        if (s.bbox.maxY > maxWorldY) maxWorldY = s.bbox.maxY;
      }
    }

    // Unterlage (Arbeitsblatt/Dokument) einbeziehen
    if (isUnderlayVisible && docUnderlayImg && docUnderlayImg.complete && docUnderlayImg.naturalWidth > 0) {
      const uRight = (docUnderlayImg.offsetLeft || 0) + (docUnderlayImg.offsetWidth || 0);
      const uBottom = (docUnderlayImg.offsetTop || 0) + (docUnderlayImg.offsetHeight || 0);
      if (uRight > maxWorldX) maxWorldX = uRight;
      if (uBottom > maxWorldY) maxWorldY = uBottom;
    }

    // Aufgaben-Karten von Luna einbeziehen
    if (exercises && exercises.length > 0) {
      for (const ex of exercises) {
        const exEl = document.getElementById(`wb-exercise-${ex.id}`);
        const cW = exEl ? exEl.offsetWidth : 440;
        const cH = exEl ? exEl.offsetHeight : 280;
        const eRight = (ex.pos_x || 60) + cW;
        const eBottom = (ex.pos_y || 80) + cH;
        if (eRight > maxWorldX) maxWorldX = eRight;
        if (eBottom > maxWorldY) maxWorldY = eBottom;
      }
    }

    minWorldX = Math.min(0, minWorldX - 20);
    maxWorldX += 40;
    maxWorldY += 60;

    const captureWidth = Math.max(800, maxWorldX - minWorldX);
    const captureHeight = Math.max(600, maxWorldY - minWorldY);

    lastCaptureBounds = {
      minX: minWorldX,
      minY: minWorldY,
      width: captureWidth,
      height: captureHeight
    };

    // Offscreen Canvas mit optimaler Vision-Auflösung erstellen
    const offscreen = document.createElement("canvas");
    let targetW = captureWidth;
    let targetH = captureHeight;
    const maxDim = 1920;
    if (Math.max(targetW, targetH) > maxDim) {
      const s = maxDim / Math.max(targetW, targetH);
      targetW = Math.round(targetW * s);
      targetH = Math.round(targetH * s);
    } else if (targetW < 1200) {
      const s = Math.min(1.5, 1200 / targetW);
      targetW = Math.round(targetW * s);
      targetH = Math.round(targetH * s);
    }
    offscreen.width = targetW;
    offscreen.height = targetH;

    const octx = offscreen.getContext("2d");

    // Skalierung und Nullpunktverschiebung
    const sX = targetW / captureWidth;
    const sY = targetH / captureHeight;
    octx.scale(sX, sY);
    octx.translate(-minWorldX, -minWorldY);

    // 1. Hintergrund
    octx.fillStyle = isChalk ? "#1e293b" : "#ffffff";
    octx.fillRect(minWorldX, minWorldY, captureWidth, captureHeight);

    // 2. Dokumenten-Vorlage einzeichnen falls aktiv
    if (isUnderlayVisible && docUnderlayImg && docUnderlayImg.complete && docUnderlayImg.naturalWidth > 0) {
      try {
        const dx = docUnderlayImg.offsetLeft || 0;
        const dy = docUnderlayImg.offsetTop || 0;
        const dw = docUnderlayImg.offsetWidth || docUnderlayImg.naturalWidth;
        const dh = docUnderlayImg.offsetHeight || docUnderlayImg.naturalHeight;
        octx.drawImage(docUnderlayImg, dx, dy, dw, dh);
      } catch (err) {
        console.warn("Fehler beim Zeichnen der Vorlage in Snapshot:", err);
      }
    }

    // 2.5 Aufgaben-Karten von Luna in den Snapshot einzeichnen (VOR den Schriftzügen, damit die Striche über der Aufgabe sichtbar sind)
    if (exercises && exercises.length > 0) {
      for (let i = 0; i < exercises.length; i++) {
        const ex = exercises[i];
        const exEl = document.getElementById(`wb-exercise-${ex.id}`);
        const cW = exEl ? exEl.offsetWidth : 440;
        const cH = exEl ? exEl.offsetHeight : 280;
        const cx = ex.pos_x || 60;
        const cy = ex.pos_y || 80;

        octx.save();
        octx.fillStyle = isChalk ? "rgba(18, 24, 38, 0.96)" : "#ffffff";
        octx.strokeStyle = "#6366f1";
        octx.lineWidth = 2;
        octx.beginPath();
        octx.roundRect(cx, cy, cW, cH, 12);
        octx.fill();
        octx.stroke();

        // Header
        octx.fillStyle = isChalk ? "rgba(30, 41, 59, 0.9)" : "#f1f5f9";
        octx.beginPath();
        octx.roundRect(cx, cy, cW, 34, [12, 12, 0, 0]);
        octx.fill();

        octx.fillStyle = isChalk ? "#f8fafc" : "#1e293b";
        octx.font = "bold 13px sans-serif";
        octx.fillText(`📝 ${ex.title || 'Aufgabe'}`, cx + 12, cy + 22);

        // Instructions
        octx.fillStyle = isChalk ? "#cbd5e1" : "#334155";
        octx.font = "12px sans-serif";
        const lines = wrapCanvasText(octx, ex.instructions || "", cW - 24);
        let curY = cy + 54;
        for (const l of lines.slice(0, 3)) {
          octx.fillText(l, cx + 12, curY);
          curY += 16;
        }

        try {
          const c = typeof ex.content_json === "string" ? JSON.parse(ex.content_json) : (ex.content_json || {});
          if (c.given || c.problem_statement) {
            octx.fillStyle = isChalk ? "#38bdf8" : "#0284c7";
            octx.font = "bold 14px monospace";
            octx.fillText(c.given || c.problem_statement || "", cx + 12, curY + 16);
          } else if (c.text) {
            octx.fillStyle = isChalk ? "#fbbf24" : "#b45309";
            octx.font = "12px sans-serif";
            let bIdx = 0;
            const cleanText = c.text.replace(/\[\[(.*?)(?::(.*?))?\]\]/g, (m, p1, p2) => {
              bIdx++;
              const num = p2 ? (p1.trim().replace(/^Lücke\s*/i, "") || bIdx) : bIdx;
              return `( ${num}: _______ )`;
            });
            const tLines = wrapCanvasText(octx, cleanText, cW - 24);
            let ty = curY + 14;
            for (const tl of tLines.slice(0, 4)) {
              octx.fillText(tl, cx + 12, ty);
              ty += 16;
            }
          }
        } catch (err) {}

        octx.restore();
      }
    }

    // 3. Alle Striche der Schülerin in voller Höhe einzeichnen (liegt über den Aufgabenkarten)
    for (let i = 0; i < strokes.length; i++) {
      renderStrokeToContext(octx, strokes[i]);
    }

    // 4. Feiner Indikator für Theas aktuellen Bildschirmausschnitt
    const isScrolledOrZoomed = Math.abs(panY) > 20 || Math.abs(panX) > 20 || scale > 1.05 || captureHeight > viewH * 1.25;
    if (isScrolledOrZoomed) {
      octx.save();
      octx.strokeStyle = isChalk ? "rgba(251, 191, 36, 0.65)" : "rgba(37, 99, 235, 0.65)";
      octx.lineWidth = 2.5;
      octx.setLineDash([8, 6]);
      octx.strokeRect(viewLeft, viewTop, viewRight - viewLeft, viewBottom - viewTop);
      octx.fillStyle = isChalk ? "rgba(251, 191, 36, 0.85)" : "rgba(37, 99, 235, 0.85)";
      octx.font = "14px -apple-system, sans-serif";
      octx.fillText("👀 Theas aktueller Bildschirmausschnitt", viewLeft + 10, Math.max(viewTop + 18, 22));
      octx.restore();
    }

    return offscreen.toDataURL("image/jpeg", 0.85);
  }

  // 9. Backend-Persistenz (Auto-Save OHNE teures toDataURL)
  function setBookDocSaveStatus(status) {
    if (!docSaveStatus) return;
    docSaveStatus.style.display = "inline-block";
    if (status === "saving") {
      docSaveStatus.textContent = "Speichere...";
      docSaveStatus.className = "wb-doc-save-status saving";
    } else if (status === "saved") {
      docSaveStatus.textContent = "✓ Gespeichert";
      docSaveStatus.className = "wb-doc-save-status";
    } else if (status === "error") {
      docSaveStatus.textContent = "⚠ Fehler";
      docSaveStatus.className = "wb-doc-save-status saving";
    }
  }

  async function saveBookPageAnnotationsNow() {
    if (!isBookPageMode || !bookPageContext || !docUnderlayImg) return;
    clearTimeout(bookPageSaveDebounceTimer);
    bookPageSaveDebounceTimer = null;
    setBookDocSaveStatus("saving");

    const dx = docUnderlayImg.offsetLeft || 0;
    const dy = docUnderlayImg.offsetTop || 0;
    const dw = docUnderlayImg.offsetWidth || docUnderlayImg.naturalWidth;
    const dh = docUnderlayImg.offsetHeight || docUnderlayImg.naturalHeight;
    if (dw === 0 || dh === 0) return;

    const normalizedStrokes = strokes.map(s => ({
      id: s.id,
      tool: s.tool,
      color: s.color,
      width: s.width,
      points: (s.points || []).map(p => ({
        x: Math.max(0, Math.min(1, (p.x - dx) / dw)),
        y: Math.max(0, Math.min(1, (p.y - dy) / dh)),
        pressure: p.pressure
      }))
    }));

    try {
      const payload = {
        material_id: bookPageContext.materialId,
        page_number: bookPageContext.page,
        strokes: normalizedStrokes,
        strokes_json: JSON.stringify(normalizedStrokes)
      };
      const res = await fetch(`/api/v1/materials/${bookPageContext.materialId}/pages/${bookPageContext.page}/annotations`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        setBookDocSaveStatus("saved");
      } else {
        setBookDocSaveStatus("error");
      }
    } catch (err) {
      console.error("Fehler beim Speichern der Buchseiten-Notizen:", err);
      setBookDocSaveStatus("error");
    }
  }

  function scheduleBookPageAutoSave() {
    clearTimeout(bookPageSaveDebounceTimer);
    bookPageSaveDebounceTimer = setTimeout(() => {
      saveBookPageAnnotationsNow();
    }, 700);
  }

  async function loadBookPageAnnotations() {
    if (!isBookPageMode || !bookPageContext || !docUnderlayImg) return;
    strokes = [];
    undoStack = [];
    redoStack = [];
    redrawAllStrokes();

    const dx = docUnderlayImg.offsetLeft || 0;
    const dy = docUnderlayImg.offsetTop || 0;
    const dw = docUnderlayImg.offsetWidth || docUnderlayImg.naturalWidth;
    const dh = docUnderlayImg.offsetHeight || docUnderlayImg.naturalHeight;
    if (dw === 0 || dh === 0) return;

    try {
      const res = await fetch(`/api/v1/materials/${bookPageContext.materialId}/pages/${bookPageContext.page}/annotations`);
      if (res.ok) {
        const data = await res.json();
        let loaded = [];
        if (Array.isArray(data.strokes) && data.strokes.length > 0) {
          loaded = data.strokes;
        } else if (data.strokes_json) {
          try { loaded = JSON.parse(data.strokes_json) || []; } catch (_) {}
        }

        strokes = loaded.map(s => ({
          id: s.id || ("str_" + Date.now() + "_" + Math.floor(Math.random() * 10000)),
          tool: s.tool || "pen",
          color: s.color || "#2563eb",
          width: s.width || 3,
          points: (s.points || []).map(pt => {
            const px = Array.isArray(pt) ? pt[0] : pt.x;
            const py = Array.isArray(pt) ? pt[1] : pt.y;
            const pr = Array.isArray(pt) ? (pt[2] || 0.5) : (pt.pressure || 0.5);
            return {
              x: dx + px * dw,
              y: dy + py * dh,
              pressure: pr
            };
          })
        }));
        redrawAllStrokes();
        setBookDocSaveStatus("saved");
      }
    } catch (err) {
      console.error("Fehler beim Laden der Buch-Notizen auf Tafel:", err);
    }
  }

  function scheduleAutoSave() {
    if (isBookPageMode) {
      scheduleBookPageAutoSave();
      return;
    }
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

  // 9.1 Unterlagen- & Arbeitsblatt-Verwaltung für die Tafel
  async function loadMaterialsForSubject(subjectId) {
    if (!materialSelect) return;
    materialSelect.innerHTML = `<option value="">Lade Unterlagen...</option>`;
    currentSubjectMaterialsList = [];

    try {
      const res = await fetch(`/api/v1/materials?subject_id=${encodeURIComponent(subjectId)}`);
      if (res.ok) {
        currentSubjectMaterialsList = await res.json();
      }
    } catch (err) {
      console.warn("Fehler beim Laden der Fach-Materialien:", err);
    }

    materialSelect.innerHTML = `<option value="">Freies Üben (ohne Vorlage)</option>`;
    if (currentSubjectMaterialsList.length === 0) {
      clearWhiteboardMaterial();
      return;
    }

    const groups = {
      "Arbeitsblätter": currentSubjectMaterialsList.filter(m => m.kind === "Arbeitsblatt"),
      "Schulbuch": currentSubjectMaterialsList.filter(m => (m.kind || "").includes("Buch")),
      "Hefter": currentSubjectMaterialsList.filter(m => (m.kind || "").includes("Heft")),
      "Tests & Übungen": currentSubjectMaterialsList.filter(m => {
        const k = m.kind || "";
        return k.includes("Test") || k.includes("Klassenarbeit") || k.includes("Übung");
      }),
      "Sonstige": currentSubjectMaterialsList.filter(m => {
        const k = m.kind || "";
        return k !== "Arbeitsblatt" && !k.includes("Buch") && !k.includes("Heft") && !k.includes("Test") && !k.includes("Klassenarbeit") && !k.includes("Übung");
      })
    };

    Object.entries(groups).forEach(([groupName, items]) => {
      if (items.length > 0) {
        const optgroup = document.createElement("optgroup");
        optgroup.label = groupName;
        items.forEach(m => {
          const opt = document.createElement("option");
          opt.value = m.id;
          opt.textContent = `${m.title} (${m.page_count || 1} S.)`;
          optgroup.appendChild(opt);
        });
        materialSelect.appendChild(optgroup);
      }
    });

    if (activeMaterial) {
      materialSelect.value = activeMaterial.id;
    }
  }

  function setWhiteboardMaterial(material, page = 1, showUnderlay = true) {
    activeMaterial = material;
    activeMaterialPage = Math.max(1, Math.min(page, material.page_count || 1));
    if (materialSelect) {
      materialSelect.value = material.id;
    }
    if (btnToggleUnderlay) {
      btnToggleUnderlay.style.display = "inline-block";
    }

    if (showUnderlay) {
      isUnderlayVisible = true;
      renderUnderlayPage();
    }
    updateUnderlayVisibility();
  }

  function clearWhiteboardMaterial() {
    activeMaterial = null;
    activeMaterialPage = 1;
    isUnderlayVisible = false;
    if (materialSelect) materialSelect.value = "";
    if (btnToggleUnderlay) btnToggleUnderlay.style.display = "none";
    updateUnderlayVisibility();
  }

  function renderUnderlayPage() {
    if (!activeMaterial || !docUnderlayImg) return;
    const p = activeMaterialPage;
    docUnderlayImg.src = `/api/v1/materials/${activeMaterial.id}/preview?page=${p}`;

    if (docBadge) docBadge.textContent = activeMaterial.kind || "Vorlage";
    if (docTitle) docTitle.textContent = activeMaterial.title || "Dokument";
    if (docPageInfo) docPageInfo.textContent = `Seite ${p} / ${activeMaterial.page_count || 1}`;

    if (btnDocPrev) btnDocPrev.disabled = p <= 1;
    if (btnDocNext) btnDocNext.disabled = p >= (activeMaterial.page_count || 1);
  }

  function updateUnderlayVisibility() {
    if (!docUnderlay || !docTopbar) return;
    if (isUnderlayVisible && activeMaterial) {
      docUnderlay.style.display = "block";
      docTopbar.style.display = "flex";
      if (btnToggleUnderlay) {
        btnToggleUnderlay.textContent = "🙈 Ausblenden";
        btnToggleUnderlay.classList.add("active");
      }
      updateViewportPan();
    } else {
      docUnderlay.style.display = "none";
      docTopbar.style.display = "none";
      if (btnToggleUnderlay) {
        btnToggleUnderlay.textContent = "📄 Vorlage";
        btnToggleUnderlay.classList.remove("active");
      }
    }
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
          await loadMaterialsForSubject(data.subject_id);
          if (data.board_state_json) {
            try {
              strokes = JSON.parse(data.board_state_json) || [];
              strokes.forEach(s => {
                if (!s.bbox && s.points) s.bbox = computeBoundingBox(s.points);
              });
              panY = 0;
              updateViewportPan();
            } catch (e) {
              strokes = [];
            }
          }
          await loadSessionExercises(data.id);
          // Nur hier verbinden: createNewSession() verbindet selbst (ein zweiter Aufruf würde
          // den gerade aufgebauten Socket wieder schließen)
          connectTutorWebSocket();
        } else {
          await createNewSession();
        }
      } else {
        await createNewSession();
      }
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
        exercises = [];
        if (tasksLayer) tasksLayer.innerHTML = "";
        panY = 0;
        updateViewportPan();
        connectTutorWebSocket();
      }
    } catch (e) {
      console.error("Fehler beim Erstellen einer neuen Sitzung:", e);
    }
  }

  // 10. WebSocket Verbindung
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

  // 11. Toolbar Event-Handler (Apple PencilKit Design: Tools, Dot-Größen, Farb- & Muster-Swatches)
  function setTool(tool) {
    currentTool = tool;
    document.querySelectorAll(".wb-tool-btn").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.tool === tool);
    });
  }

  function setSize(size) {
    currentBaseWidth = parseFloat(size);
    document.querySelectorAll(".wb-dot-btn").forEach(btn => {
      btn.classList.toggle("active", parseFloat(btn.dataset.size) === currentBaseWidth);
    });
  }

  function setColor(color) {
    currentColor = color;
    document.querySelectorAll(".wb-color-swatch").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.color.toLowerCase() === color.toLowerCase());
    });
    // Farbpunkte der Strichstärken dezent mit der gewählten Farbe einfärben
    document.querySelectorAll(".wb-dot").forEach(dot => {
      dot.style.backgroundColor = color;
    });
    if (currentTool === "pixel_eraser" || currentTool === "object_eraser" || currentTool === "eraser") {
      setTool("pen");
    }
  }

  function setPattern(pattern) {
    viewport.className = `wb-viewport ${pattern}`;
    document.querySelectorAll(".wb-pattern-swatch").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.pattern === pattern);
    });
  }

  // Werkzeug-Buttons binden
  document.querySelectorAll(".wb-tool-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.tool) setTool(btn.dataset.tool);
    });
  });

  // Strichstärken (Punkte) binden
  document.querySelectorAll(".wb-dot-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.size) setSize(btn.dataset.size);
    });
  });

  // Farb-Swatches binden
  document.querySelectorAll(".wb-color-swatch").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.color) setColor(btn.dataset.color);
    });
  });

  // Muster-Swatches binden
  document.querySelectorAll(".wb-pattern-swatch").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.pattern) setPattern(btn.dataset.pattern);
    });
  });

  if (btnPenOnly) {
    btnPenOnly.addEventListener("click", () => {
      penOnlyMode = !penOnlyMode;
      btnPenOnly.classList.toggle("active", penOnlyMode);
      const penLabel = document.getElementById("wb-pen-label");
      if (penLabel) penLabel.textContent = penOnlyMode ? "Pencil" : "Touch";
      btnPenOnly.title = penOnlyMode
        ? "Apple Pencil aktiv (Handfläche wird ignoriert)"
        : "Touch-Modus aktiv (Finger und Stift zeichnen)";
    });
  }

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

  if (btnSave) {
    btnSave.addEventListener("click", () => {
      const link = document.createElement("a");
      link.download = `gothea-tafel-${new Date().toISOString().slice(0, 10)}.png`;
      link.href = inkCanvas.toDataURL("image/png");
      link.click();
    });
  }

  if (btnNewSession) {
    btnNewSession.addEventListener("click", async () => {
      if (confirm("Möchtest du eine neue Tafel für das gewählte Fach beginnen?")) {
        await createNewSession();
      }
    });
  }

  if (subjectSelect) {
    subjectSelect.addEventListener("change", async () => {
      await loadMaterialsForSubject(subjectSelect.value);
      await createNewSession();
    });
  }

  // Material-Auswahl Listener
  if (materialSelect) {
    materialSelect.addEventListener("change", () => {
      const matId = materialSelect.value;
      if (!matId) {
        clearWhiteboardMaterial();
      } else {
        const found = currentSubjectMaterialsList.find(m => m.id === matId);
        if (found) {
          setWhiteboardMaterial(found, 1, true);
        }
      }
    });
  }

  // Underlay Ein-/Ausblenden Button
  if (btnToggleUnderlay) {
    btnToggleUnderlay.addEventListener("click", () => {
      isUnderlayVisible = !isUnderlayVisible;
      updateUnderlayVisibility();
    });
  }

  // Vorlagen-Pager Buttons
  if (btnDocPrev) {
    btnDocPrev.addEventListener("click", async () => {
      if (isBookPageMode && bookPageContext && bookPageContext.page > 1) {
        await saveBookPageAnnotationsNow();
        bookPageContext.page--;
        const p = bookPageContext.page;
        if (docPageInfo) docPageInfo.textContent = `Seite ${p} / ${bookPageContext.pageCount || 1}`;
        btnDocPrev.disabled = p <= 1;
        if (btnDocNext) btnDocNext.disabled = p >= bookPageContext.pageCount;
        docUnderlayImg.src = `/api/v1/materials/${bookPageContext.materialId}/preview?page=${p}`;
        loadBookPageAnnotations();
        return;
      }
      if (activeMaterial && activeMaterialPage > 1) {
        activeMaterialPage--;
        renderUnderlayPage();
      }
    });
  }
  if (btnDocNext) {
    btnDocNext.addEventListener("click", async () => {
      if (isBookPageMode && bookPageContext && bookPageContext.page < (bookPageContext.pageCount || 1)) {
        await saveBookPageAnnotationsNow();
        bookPageContext.page++;
        const p = bookPageContext.page;
        if (docPageInfo) docPageInfo.textContent = `Seite ${p} / ${bookPageContext.pageCount || 1}`;
        btnDocPrev.disabled = p <= 1;
        if (btnDocNext) btnDocNext.disabled = p >= bookPageContext.pageCount;
        docUnderlayImg.src = `/api/v1/materials/${bookPageContext.materialId}/preview?page=${p}`;
        loadBookPageAnnotations();
        return;
      }
      if (activeMaterial && activeMaterialPage < (activeMaterial.page_count || 1)) {
        activeMaterialPage++;
        renderUnderlayPage();
      }
    });
  }
  if (btnDocClose) {
    btnDocClose.addEventListener("click", async () => {
      if (isBookPageMode) {
        await saveBookPageAnnotationsNow();
        isBookPageMode = false;
      }
      isUnderlayVisible = false;
      updateUnderlayVisibility();
    });
  }

  if (btnReturnToBook) {
    btnReturnToBook.addEventListener("click", async () => {
      if (isBookPageMode && bookPageContext) {
        await saveBookPageAnnotationsNow();
        const retPage = bookPageContext.page;
        isBookPageMode = false;
        isUnderlayVisible = false;
        updateUnderlayVisibility();
        btnReturnToBook.style.display = "none";
        if (docSaveStatus) docSaveStatus.style.display = "none";
        if (btnDocClose) btnDocClose.style.display = "inline-block";
        strokes = [];
        redrawAllStrokes();
        if (typeof window.returnToBookReader === "function") {
          window.returnToBookReader(retPage);
        }
      }
    });
  }

  // Audio Toggle Button (Lautsprecher)
  if (btnAudioToggle) {
    btnAudioToggle.addEventListener("click", () => {
      tutorAudioEnabled = !tutorAudioEnabled;
      btnAudioToggle.classList.toggle("active", tutorAudioEnabled);
      btnAudioToggle.classList.toggle("muted", !tutorAudioEnabled);
      const iconOn = document.getElementById("wb-audio-icon-on");
      const iconOff = document.getElementById("wb-audio-icon-off");
      if (iconOn && iconOff) {
        iconOn.style.display = tutorAudioEnabled ? "inline-block" : "none";
        iconOff.style.display = tutorAudioEnabled ? "none" : "inline-block";
      }
      btnAudioToggle.title = tutorAudioEnabled ? "Sprachausgabe (TTS) aktiv" : "Sprachausgabe stummgeschaltet";
      if (!tutorAudioEnabled) {
        stopTutorSpeech();
      }
    });
  }

  // Stop Button in der Sprechblase
  if (btnStopSpeech) {
    btnStopSpeech.addEventListener("click", () => {
      stopTutorSpeech();
    });
  }

  // KI-Tutor fragen (Snapshot an Vision + OpenAI TTS Sprachausgabe)
  if (btnRequestHint) {
    btnRequestHint.addEventListener("click", async () => {
      if (!currentSession) return;
      stopTutorSpeech();

      if (strokes.length === 0 && !isUnderlayVisible) {
        playTutorSpeech(null, "Deine Tafel ist noch ganz leer. Schreib mir gerne eine Aufgabe oder deinen Rechenschritt auf!");
        return;
      }

      const origHtml = hintIcon ? hintIcon.innerHTML : "";
      const origText = hintLabel ? hintLabel.textContent : "Tutor fragen";

      if (hintIcon) {
        hintIcon.innerHTML = `<svg class="wb-spinner" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9" stroke-opacity="0.25"></circle><path d="M12 3a9 9 0 0 1 9 9" stroke-linecap="round"></path></svg>`;
      }
      if (hintLabel) hintLabel.textContent = "Luna schaut...";
      btnRequestHint.disabled = true;

      try {
        const snapshot = captureBoardSnapshot();
        const res = await fetch(`/api/v1/whiteboard/sessions/${currentSession.id}/ask-tutor`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            image_base64: snapshot,
            audio_enabled: tutorAudioEnabled,
            material_id: activeMaterial ? activeMaterial.id : null
          })
        });

        if (res.ok) {
          const data = await res.json();
          if (data.actions && data.actions.length > 0) {
            drawOverlayActions(data.actions);
          }
          if (data.tutor_speech) {
            playTutorSpeech(data.audio_base64, data.tutor_speech);
          }
        } else {
          const err = await res.json().catch(() => ({}));
          console.error("Fehler beim Tutor-Aufruf:", err);
          alert(`Hinweis: ${err.detail || "Tutor konnte nicht antworten."}`);
        }
      } catch (e) {
        console.error("Fehler beim Abrufen des KI-Hinweises:", e);
        alert("Netzwerkfehler beim Abrufen des Hinweises.");
      } finally {
        if (hintIcon) hintIcon.innerHTML = origHtml;
        if (hintLabel) hintLabel.textContent = origText;
        btnRequestHint.disabled = false;
      }
    });
  }

  if (btnFullscreen) {
    btnFullscreen.addEventListener("click", () => {
      document.body.classList.toggle("wb-fullscreen-mode");
      setTimeout(resizeCanvases, 100);
    });
  }

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
      setTool("pen");
    } else if (!e.metaKey && !e.ctrlKey && e.key.toLowerCase() === "h") {
      setTool("highlighter");
    } else if (!e.metaKey && !e.ctrlKey && e.key.toLowerCase() === "e") {
      if (currentTool === "pixel_eraser") {
        setTool("object_eraser");
      } else {
        setTool("pixel_eraser");
      }
    }
  });

  // Helper: Text auf Canvas umbrechen
  function wrapCanvasText(ctx, text, maxWidth) {
    if (!text) return [];
    const words = text.split(" ");
    const lines = [];
    let currentLine = words[0] || "";
    for (let i = 1; i < words.length; i++) {
      const word = words[i];
      const width = ctx.measureText(currentLine + " " + word).width;
      if (width < maxWidth) {
        currentLine += " " + word;
      } else {
        lines.push(currentLine);
        currentLine = word;
      }
    }
    if (currentLine) lines.push(currentLine);
    return lines;
  }

  // 12. Interaktives Aufgaben-Subsystem (Task Cards auf der Tafel)
  const EXERCISE_TYPE_LABELS = {
    fill_in_the_blank: "✏️ Lückentext",
    math_problem: "🔢 Rechenaufgabe",
    math_example: "📖 Musterbeispiel",
    physics_diagram: "📈 Physik-Diagramm",
    formula_derivation: "📐 Formel-Herleitung",
    text_question: "📄 Textfrage"
  };

  function renderExerciseContent(ex) {
    let content = {};
    try {
      content = typeof ex.content_json === "string" ? JSON.parse(ex.content_json) : (ex.content_json || {});
    } catch (e) {
      content = {};
    }

    let innerHtml = "";

    if (ex.exercise_type === "fill_in_the_blank") {
      let rawText = content.text || "";
      let blankCount = 0;
      const blanks = content.blanks || [];
      const blanksMap = {};
      blanks.forEach(b => { blanksMap[b.id] = b; });

      let renderedText = rawText.replace(/\[\[(.*?)(?::(.*?))?\]\]/g, (m, p1, p2) => {
        blankCount++;
        let bid = blankCount;
        if (p2) {
          const matchNum = p1.match(/\d+/);
          if (matchNum) bid = parseInt(matchNum[0], 10);
        }
        const bDef = blanksMap[bid] || {};
        const expAns = bDef.expected_answer || bDef.correct_answer || (p2 || "").trim();
        const widthPx = Math.max(180, Math.min(520, Math.max(bDef.width_px || 0, 180 + Math.max(0, expAns.length - 5) * 24)));
        return `<span class="wb-blank-token wb-blank-zone" id="wb-blank-${ex.id}-${bid}" data-exercise-id="${ex.id}" data-blank-id="${bid}" style="min-width: ${widthPx}px;"><span class="wb-blank-num">(${bid})</span><span class="wb-blank-badge" id="wb-blank-badge-${ex.id}-${bid}"></span></span>`;
      });
      if (!rawText.includes("[[")) {
        renderedText = rawText.replace(/_{3,}/g, () => {
          blankCount++;
          const bDef = blanksMap[blankCount] || {};
          const expAns = bDef.expected_answer || bDef.correct_answer || "";
          const widthPx = Math.max(180, Math.min(520, Math.max(bDef.width_px || 0, 180 + Math.max(0, expAns.length - 5) * 24)));
          return `<span class="wb-blank-token wb-blank-zone" id="wb-blank-${ex.id}-${blankCount}" data-exercise-id="${ex.id}" data-blank-id="${blankCount}" style="min-width: ${widthPx}px;"><span class="wb-blank-num">(${blankCount})</span><span class="wb-blank-badge" id="wb-blank-badge-${ex.id}-${blankCount}"></span></span>`;
        });
      }
      innerHtml += `<div class="wb-task-content-box">${renderedText}</div>`;
      if (content.word_bank && content.word_bank.length > 0) {
        innerHtml += `
          <div class="wb-word-bank">
            <span style="font-size: 0.75rem; color: #94a3b8; font-weight: 600;">Wortauswahl:</span>
            ${content.word_bank.map(w => `<span class="wb-word-chip">${w}</span>`).join("")}
          </div>
        `;
      }
      const totalBlanks = blanks.length || blankCount;
      innerHtml += `
        <div class="wb-task-footer">
          <button type="button" class="wb-task-check-btn" id="btn-check-${ex.id}">🔍 Lücken prüfen</button>
          <span class="wb-cloze-progress" id="cloze-progress-${ex.id}">0 / ${totalBlanks} gelöst</span>
        </div>
      `;
    } else if (ex.exercise_type === "physics_diagram") {
      if (content.diagram_svg) {
        innerHtml += `<div class="wb-physics-diagram-wrap">${content.diagram_svg}</div>`;
      }
      if (content.questions && content.questions.length > 0) {
        innerHtml += `
          <div class="wb-task-content-box">
            <strong style="font-size: 0.85rem; color: #38bdf8;">Fragen zum Diagramm:</strong>
            <ol class="wb-physics-questions">
              ${content.questions.map(q => `<li>${q}</li>`).join("")}
            </ol>
          </div>
        `;
      }
    } else if (ex.exercise_type === "formula_derivation") {
      if (content.steps && Array.isArray(content.steps)) {
        innerHtml += `
          <div class="wb-derivation-list">
            ${content.steps.map(s => `
              <div class="wb-derivation-row">
                <span class="wb-derivation-step-num">${s.num || '•'}</span>
                <span class="wb-derivation-text">${s.text || ''}</span>
                <span class="wb-derivation-formula">${s.formula || ''}</span>
              </div>
            `).join("")}
          </div>
        `;
      }
    } else if (ex.exercise_type === "math_example") {
      innerHtml += `
        <div class="wb-task-content-box" style="border-left: 3px solid #6366f1;">
          <div style="font-size: 0.75rem; font-weight: 700; color: #818cf8; text-transform: uppercase;">Musterbeispiel</div>
          <div style="font-size: 0.95rem; margin: 4px 0; font-family: monospace;">${content.example_title || ''}</div>
          <div style="font-size: 0.85rem; color: #cbd5e1; white-space: pre-wrap;">${content.example_solution || ''}</div>
        </div>
        ${content.your_turn ? `
          <div class="wb-task-content-box" style="border-left: 3px solid #10b981; margin-top: 6px;">
            <div style="font-size: 0.75rem; font-weight: 700; color: #34d399; text-transform: uppercase;">Jetzt du:</div>
            <div style="font-size: 0.95rem; margin-top: 4px; font-weight: 600;">${content.your_turn}</div>
          </div>
        ` : ''}
      `;
    } else if (ex.exercise_type === "text_question") {
      if (content.text_snippet) {
        innerHtml += `
          <div class="wb-task-content-box" style="font-style: italic; font-size: 0.86rem; border-left: 3px solid #a855f7;">
            "${content.text_snippet}"
          </div>
        `;
      }
      if (content.questions && content.questions.length > 0) {
        innerHtml += `
          <ol class="wb-physics-questions">
            ${content.questions.map(q => `<li>${q}</li>`).join("")}
          </ol>
        `;
      }
    } else {
      // math_problem
      innerHtml += `
        <div class="wb-task-content-box">
          ${content.problem_statement ? `<div style="font-size: 0.88rem; font-weight: 600; margin-bottom: 6px;">${content.problem_statement}</div>` : ''}
          ${content.given ? `<div style="font-size: 1.15rem; font-family: 'Courier New', monospace; font-weight: 700; color: #38bdf8; margin: 8px 0; text-align: center;">${content.given}</div>` : ''}
          ${content.prompt ? `<div style="font-size: 0.82rem; color: #94a3b8; white-space: pre-line;">${content.prompt}</div>` : ''}
        </div>
      `;
    }

    if (ex.solution_hint) {
      innerHtml += `
        <button type="button" class="wb-task-hint-btn" id="btn-hint-${ex.id}">💡 Tipp aufdecken</button>
        <div class="wb-task-hint-box" id="hint-box-${ex.id}" style="display: none;">
          ${ex.solution_hint}
        </div>
      `;
    }

    return innerHtml;
  }

  function createExerciseCardElement(ex) {
    const card = document.createElement("div");
    card.className = "wb-task-card";
    card.id = `wb-exercise-${ex.id}`;
    card.style.left = `${ex.pos_x || 60}px`;
    card.style.top = `${ex.pos_y || 80}px`;

    const badgeLabel = EXERCISE_TYPE_LABELS[ex.exercise_type] || "Aufgabe";

    card.innerHTML = `
      <div class="wb-task-header" id="wb-task-header-${ex.id}">
        <div class="wb-task-header-left">
          <span class="wb-task-type-badge">${badgeLabel}</span>
          <span class="wb-task-title" title="${ex.title || ''}">${ex.title || 'Aufgabe'}</span>
        </div>
        <div class="wb-task-header-actions">
          <button type="button" class="wb-task-close-btn" id="btn-close-${ex.id}" title="Aufgabe von der Tafel entfernen">✕</button>
        </div>
      </div>
      <div class="wb-task-body">
        ${ex.instructions ? `<div class="wb-task-instructions">${ex.instructions}</div>` : ''}
        ${renderExerciseContent(ex)}
      </div>
    `;

    // Tipp aufdecken Listener
    const hintBtn = card.querySelector(`#btn-hint-${ex.id}`);
    const hintBox = card.querySelector(`#hint-box-${ex.id}`);
    if (hintBtn && hintBox) {
      hintBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = hintBox.style.display !== "none";
        hintBox.style.display = isOpen ? "none" : "block";
        hintBtn.textContent = isOpen ? "💡 Tipp aufdecken" : "🙈 Tipp verbergen";
      });
    }

    // Löschen Listener
    const closeBtn = card.querySelector(`#btn-close-${ex.id}`);
    if (closeBtn) {
      closeBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (confirm("Möchtest du diese Aufgabe von der Tafel entfernen?")) {
          card.remove();
          exercises = exercises.filter(item => item.id !== ex.id);
          if (currentSession) {
            try {
              await fetch(`/api/v1/whiteboard/sessions/${currentSession.id}/exercises/${ex.id}`, {
                method: "DELETE"
              });
            } catch (err) {}
          }
        }
      });
    }

    // Lücken prüfen Listener
    const checkBtn = card.querySelector(`#btn-check-${ex.id}`);
    if (checkBtn) {
      checkBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        checkClozeBlanks(card, ex);
      });
    }

    // Drag-and-Drop auf der Tafel
    const header = card.querySelector(`#wb-task-header-${ex.id}`);
    if (header) {
      attachCardDragHandler(card, header, ex);
    }

    return card;
  }

  async function checkClozeBlanks(card, ex) {
    if (!currentSession) return;
    const checkBtn = card.querySelector(`#btn-check-${ex.id}`);
    const progressEl = card.querySelector(`#cloze-progress-${ex.id}`);
    if (!checkBtn) return;

    const blankEls = Array.from(card.querySelectorAll(".wb-blank-zone"));
    if (blankEls.length === 0) return;

    checkBtn.disabled = true;
    checkBtn.textContent = "⏳ Prüfe...";

    blankEls.forEach(el => {
      el.classList.remove("status-correct", "status-incorrect");
      el.classList.add("status-pending");
      const badge = el.querySelector(".wb-blank-badge");
      if (badge) badge.textContent = "⏳";
    });

    try {
      const cropCanvas = document.createElement("canvas");
      const cropCtx = cropCanvas.getContext("2d");
      const inkRect = inkCanvas.getBoundingClientRect();
      const items = [];

      for (const el of blankEls) {
        const bid = parseInt(el.dataset.blankId, 10);
        const rect = el.getBoundingClientRect();

        const screenLeft = rect.left - inkRect.left;
        const screenTop = rect.top - inkRect.top;
        const vx = (screenLeft - panX) / scale;
        const vy = (screenTop - panY) / scale;
        const vw = rect.width / scale;
        const vh = rect.height / scale;

        const padding = 12;
        const cropX = vx - padding;
        const cropY = vy - padding;
        const cropW = vw + padding * 2;
        const cropH = vh + padding * 2;

        const overlappingStrokes = strokes.filter(s => {
          if (!s.points || s.points.length === 0) return false;
          return s.points.some(p => p.x >= cropX && p.x <= cropX + cropW && p.y >= cropY && p.y <= cropY + cropH);
        });

        if (overlappingStrokes.length === 0) {
          items.push({ blank_id: bid, crop_image_base64: "" });
          continue;
        }

        const cScale = 1.5;
        cropCanvas.width = Math.round(cropW * cScale);
        cropCanvas.height = Math.round(cropH * cScale);

        cropCtx.fillStyle = isChalk ? "#121826" : "#ffffff";
        cropCtx.fillRect(0, 0, cropCanvas.width, cropCanvas.height);

        cropCtx.save();
        cropCtx.scale(cScale, cScale);
        cropCtx.translate(-cropX, -cropY);

        for (const s of overlappingStrokes) {
          renderStrokeToContext(cropCtx, s);
        }
        cropCtx.restore();

        const cropB64 = cropCanvas.toDataURL("image/jpeg", 0.85);
        items.push({ blank_id: bid, crop_image_base64: cropB64 });
      }

      const res = await fetch(`/api/v1/whiteboard/sessions/${currentSession.id}/exercises/${ex.id}/check-blanks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: items,
          audio_enabled: tutorAudioEnabled
        })
      });

      if (res.ok) {
        const data = await res.json();
        let correctCount = 0;

        (data.results || []).forEach(r => {
          const el = card.querySelector(`#wb-blank-${ex.id}-${r.blank_id}`);
          const badge = card.querySelector(`#wb-blank-badge-${ex.id}-${r.blank_id}`);
          if (el) {
            el.classList.remove("status-pending");
            if (r.is_correct) {
              correctCount++;
              el.classList.remove("status-incorrect", "status-unclear");
              el.classList.add("status-correct");
              if (badge) badge.textContent = "✓";
            } else if (r.unclear_handwriting) {
              el.classList.remove("status-correct", "status-incorrect");
              el.classList.add("status-unclear");
              if (badge) badge.textContent = "✍️";
              if (r.hint) el.title = r.hint;
            } else {
              el.classList.remove("status-correct", "status-unclear");
              el.classList.add("status-incorrect");
              if (badge) badge.textContent = r.recognized_text ? `?` : "? leer";
              if (r.hint) el.title = r.hint;
            }
          }
        });

        if (progressEl) {
          progressEl.textContent = `${correctCount} / ${blankEls.length} gelöst`;
        }

        if (data.audio_base64 && tutorAudioEnabled) {
          playTutorSpeech(data.audio_base64, data.tutor_speech);
        }
      }
    } catch (err) {
      console.warn("Fehler bei gezielter Lückenprüfung:", err);
    } finally {
      checkBtn.disabled = false;
      checkBtn.textContent = "🔍 Lücken prüfen";
      blankEls.forEach(el => el.classList.remove("status-pending"));
    }
  }


  function attachCardDragHandler(card, header, ex) {
    let isDragging = false;
    let startScreenX = 0;
    let startScreenY = 0;
    let startPosX = ex.pos_x || 60;
    let startPosY = ex.pos_y || 80;

    header.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".wb-task-close-btn")) return;
      isDragging = true;
      header.setPointerCapture(e.pointerId);
      startScreenX = e.clientX;
      startScreenY = e.clientY;
      startPosX = ex.pos_x || 60;
      startPosY = ex.pos_y || 80;
      card.style.zIndex = "10";
      e.stopPropagation();
    });

    header.addEventListener("pointermove", (e) => {
      if (!isDragging) return;
      const dx = (e.clientX - startScreenX) / scale;
      const dy = (e.clientY - startScreenY) / scale;
      const newX = Math.round(startPosX + dx);
      const newY = Math.round(Math.max(20, startPosY + dy));
      card.style.left = `${newX}px`;
      card.style.top = `${newY}px`;
      e.stopPropagation();
    });

    header.addEventListener("pointerup", async (e) => {
      if (!isDragging) return;
      isDragging = false;
      try { header.releasePointerCapture(e.pointerId); } catch (err) {}
      card.style.zIndex = "4";
      const dx = (e.clientX - startScreenX) / scale;
      const dy = (e.clientY - startScreenY) / scale;
      ex.pos_x = Math.round(startPosX + dx);
      ex.pos_y = Math.round(Math.max(20, startPosY + dy));
      e.stopPropagation();

      if (currentSession) {
        try {
          await fetch(`/api/v1/whiteboard/sessions/${currentSession.id}/exercises/${ex.id}/position`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pos_x: ex.pos_x, pos_y: ex.pos_y })
          });
        } catch (err) {
          console.warn("Fehler beim Speichern der Aufgabenposition:", err);
        }
      }
    });
  }

  function renderAllExercises() {
    if (!tasksLayer) return;
    tasksLayer.innerHTML = "";
    exercises.forEach(ex => {
      const el = createExerciseCardElement(ex);
      tasksLayer.appendChild(el);
    });
  }

  async function loadSessionExercises(sessionId) {
    if (!sessionId) return;
    try {
      const res = await fetch(`/api/v1/whiteboard/sessions/${sessionId}/exercises`);
      if (res.ok) {
        exercises = await res.json();
        renderAllExercises();
      }
    } catch (err) {
      console.warn("Fehler beim Laden der Aufgaben:", err);
    }
  }

  // Modal Handlers
  function openExerciseModal() {
    if (!exerciseModal) return;
    if (activeMaterial && exerciseTopicInput) {
      exerciseTopicInput.placeholder = `z. B. ${activeMaterial.title}`;
    }
    exerciseModal.style.display = "flex";
  }

  function closeExerciseModal() {
    if (exerciseModal) exerciseModal.style.display = "none";
  }

  if (btnPlaceExercise) {
    btnPlaceExercise.addEventListener("click", () => {
      openExerciseModal();
    });
  }
  if (btnExerciseModalClose) {
    btnExerciseModalClose.addEventListener("click", closeExerciseModal);
  }
  if (btnExerciseCancel) {
    btnExerciseCancel.addEventListener("click", closeExerciseModal);
  }

  if (btnExerciseSubmit) {
    btnExerciseSubmit.addEventListener("click", async () => {
      if (!currentSession) {
        await createNewSession();
      }
      if (!currentSession) return;

      const exType = exerciseTypeSelect ? exerciseTypeSelect.value : "auto";
      const topicText = exerciseTopicInput ? exerciseTopicInput.value.trim() : "";
      const diff = exerciseDiffSelect ? exerciseDiffSelect.value : "mittel";
      const promptText = exercisePromptInput ? exercisePromptInput.value.trim() : "";

      btnExerciseSubmit.disabled = true;
      if (btnExerciseSubmitLabel) btnExerciseSubmitLabel.textContent = "Luna erstellt Aufgabe...";

      try {
        // Gute Platzierung ermitteln: rechts neben dem aktuellen Bildschirmausschnitt oder oben
        const viewW = viewport.clientWidth || 1024;
        const initialX = Math.round(Math.max(60, (-panX / scale) + (viewW / scale) * 0.45));
        const initialY = Math.round(Math.max(80, (-panY / scale) + 60));

        const res = await fetch(`/api/v1/whiteboard/sessions/${currentSession.id}/exercises/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exercise_type: exType,
            topic_name: topicText || null,
            difficulty: diff,
            custom_prompt: promptText || null,
            material_id: activeMaterial ? activeMaterial.id : null,
            audio_enabled: tutorAudioEnabled,
            pos_x: initialX,
            pos_y: initialY
          })
        });

        if (res.ok) {
          const newEx = await res.json();
          exercises.push(newEx);
          const cardEl = createExerciseCardElement(newEx);
          if (tasksLayer) tasksLayer.appendChild(cardEl);

          closeExerciseModal();

          // Lunas Sprachausgabe abspielen
          if (newEx.tutor_speech) {
            playTutorSpeech(newEx.audio_base64, newEx.tutor_speech);
          }
        } else {
          alert("Konnte die Aufgabe leider nicht erstellen. Bitte versuche es noch einmal.");
        }
      } catch (err) {
        console.error("Fehler beim Erstellen der Aufgabe:", err);
      } finally {
        btnExerciseSubmit.disabled = false;
        if (btnExerciseSubmitLabel) btnExerciseSubmitLabel.textContent = "Aufgabe auf Tafel legen";
      }
    });
  }

  // Globale Funktion: Material direkt auf der Tafel öffnen
  window.openMaterialOnWhiteboard = async function(materialId, subjectId = null) {
    if (typeof switchToTab === "function") {
      switchToTab("whiteboard");
    } else {
      const tabBtn = document.querySelector('.nav-tab[data-tab="whiteboard"]');
      if (tabBtn) tabBtn.click();
    }

    if (subjectId && subjectSelect && subjectSelect.value !== subjectId) {
      subjectSelect.value = subjectId;
      await loadMaterialsForSubject(subjectId);
    } else if (!currentSubjectMaterialsList.length && subjectSelect) {
      await loadMaterialsForSubject(subjectSelect.value);
    }

    const mat = currentSubjectMaterialsList.find(m => m.id === materialId);
    if (mat) {
      setWhiteboardMaterial(mat, 1, true);
    } else {
      try {
        const r = await fetch(`/api/v1/materials/${materialId}`);
        if (r.ok) {
          const mData = await r.json();
          setWhiteboardMaterial(mData, 1, true);
        }
      } catch (err) {
        console.warn("Fehler beim Öffnen des Materials auf Tafel:", err);
      }
    }
  };

  // Globale Funktion: Buchseite auf der Tafel im Dokument-Notiz-Modus öffnen
  window.openBookPageOnWhiteboard = async function({ materialId, page = 1, pageCount = 1, title = "Buchseite", subjectId = null }) {
    isBookPageMode = true;
    bookPageContext = { materialId, page, pageCount, title, subjectId };

    if (typeof switchToTab === "function") {
      switchToTab("whiteboard");
    } else {
      const tabBtn = document.querySelector('.nav-tab[data-tab="whiteboard"]');
      if (tabBtn) tabBtn.click();
    }

    if (subjectId && subjectSelect && subjectSelect.value !== subjectId) {
      subjectSelect.value = subjectId;
    }

    // Standard-Farbe auf Blau stellen, falls Weiß aktiv ist (damit auf weißer Seite lesbar)
    if (currentColor === "#f8fafc" || currentColor === "#ffffff") {
      setColor("#38bdf8");
    }

    // Viewport zurücksetzen
    panX = 0;
    panY = 0;
    scale = 1.0;

    // Topbar anpassen
    if (docTopbar) docTopbar.style.display = "flex";
    if (btnReturnToBook) btnReturnToBook.style.display = "inline-flex";
    if (docBadge) docBadge.textContent = "📖 Buchseite";
    if (docTitle) docTitle.textContent = title;
    if (docPageInfo) docPageInfo.textContent = `Seite ${page} / ${pageCount || 1}`;
    if (btnDocPrev) btnDocPrev.disabled = page <= 1;
    if (btnDocNext) btnDocNext.disabled = page >= pageCount;
    if (btnDocClose) btnDocClose.style.display = "none";
    if (btnToggleUnderlay) btnToggleUnderlay.style.display = "none";

    // Underlay anzeigen
    isUnderlayVisible = true;
    if (docUnderlay) docUnderlay.style.display = "block";

    const targetSrc = `/api/v1/materials/${materialId}/preview?page=${page}`;
    docUnderlayImg.onload = () => {
      updateViewportPan();
      loadBookPageAnnotations();
    };
    docUnderlayImg.src = targetSrc;
    if (docUnderlayImg.complete && docUnderlayImg.naturalWidth > 0) {
      updateViewportPan();
      loadBookPageAnnotations();
    }
  };
  setTimeout(() => {
    resizeCanvases();
    initSession();
  }, 150);

})();
