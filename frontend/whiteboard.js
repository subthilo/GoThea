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
  const boardSaveWarning = document.getElementById("wb-board-save-warning");
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
  const docUnderlay = document.getElementById("wb-doc-underlay");
  const docUnderlayImg = document.getElementById("wb-doc-underlay-img");
  const docTopbar = document.getElementById("wb-doc-topbar");
  const docPageInfo = document.getElementById("wb-doc-page-info");
  const btnDocPrev = document.getElementById("btn-wb-doc-prev");
  const btnDocNext = document.getElementById("btn-wb-doc-next");
  const btnDocClose = document.getElementById("btn-wb-doc-close");
  const btnReturnToBook = document.getElementById("btn-wb-doc-return-to-book");
  const docSaveStatus = document.getElementById("wb-doc-save-status");

  let currentTutorAudio = null;
  let tutorAudioEnabled = true;

  let currentSubjectMaterialsList = [];

  // Modus: Buchseite auf der Tafel beschreiben
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


  if (!inkCanvas || !overlayCanvas || !viewport) {
    return;
  }

  const inkCtx = inkCanvas.getContext("2d", { desynchronized: true });
  const overlayCtx = overlayCanvas.getContext("2d");

  // State
  let tutorSocket = null;
  let saveDebounceTimer = null;

  // Zeichenkern (js/ink_core.js): gemeinsamer Zustand und Funktionen über surface.…
  const surface = createInkSurface({
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
  });

  // 8. KI-Overlay Visualisierung
  function drawOverlayActions(actions) {
    overlayCtx.clearRect(0, 0, overlayCanvas.width / surface.dpr, overlayCanvas.height / surface.dpr);

    const boardW = overlayCanvas.width / surface.dpr;
    const boardH = overlayCanvas.height / surface.dpr;

    actions.forEach(item => {
      if (item.action === "highlight_box" && item.coords) {
        let x = item.coords.x || 0;
        let y = item.coords.y || 0;
        let w = item.coords.w || 200;
        let h = item.coords.h || 60;

        if (item.coords.x_pct !== undefined) {
          if (surface.lastCaptureBounds) {
            x = surface.lastCaptureBounds.minX + (item.coords.x_pct / 100) * surface.lastCaptureBounds.width;
            y = surface.lastCaptureBounds.minY + (item.coords.y_pct / 100) * surface.lastCaptureBounds.height;
            w = (item.coords.w_pct / 100) * surface.lastCaptureBounds.width;
            h = (item.coords.h_pct / 100) * surface.lastCaptureBounds.height;
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
        overlayCtx.clearRect(0, 0, overlayCanvas.width / surface.dpr, overlayCanvas.height / surface.dpr);
      }
    });

    setTimeout(() => {
      overlayCtx.clearRect(0, 0, overlayCanvas.width / surface.dpr, overlayCanvas.height / surface.dpr);
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
    const viewLeft = -surface.panX / surface.scale;
    const viewTop = -surface.panY / surface.scale;
    const viewRight = (-surface.panX + viewW) / surface.scale;
    const viewBottom = (-surface.panY + viewH) / surface.scale;

    // Gesamten Tafelbereich berechnen (von y=0 ganz oben bis ganz unten)
    let minWorldX = 0;
    let minWorldY = 0; // Immer ganz oben anfangen!
    let maxWorldX = Math.max(viewW, viewRight);
    let maxWorldY = Math.max(viewH, viewBottom);

    // Alle Striche der Tafel einbeziehen
    for (let i = 0; i < surface.strokes.length; i++) {
      const s = surface.strokes[i];
      if (s.bbox) {
        if (s.bbox.minX < minWorldX) minWorldX = s.bbox.minX;
        if (s.bbox.maxX > maxWorldX) maxWorldX = s.bbox.maxX;
        if (s.bbox.maxY > maxWorldY) maxWorldY = s.bbox.maxY;
      }
    }

    // Unterlage (Arbeitsblatt/Dokument) einbeziehen
    if (surface.isUnderlayVisible && docUnderlayImg && docUnderlayImg.complete && docUnderlayImg.naturalWidth > 0) {
      const uRight = (docUnderlayImg.offsetLeft || 0) + (docUnderlayImg.offsetWidth || 0);
      const uBottom = (docUnderlayImg.offsetTop || 0) + (docUnderlayImg.offsetHeight || 0);
      if (uRight > maxWorldX) maxWorldX = uRight;
      if (uBottom > maxWorldY) maxWorldY = uBottom;
    }

    // Aufgaben-Karten von Luna einbeziehen
    if (surface.exercises && surface.exercises.length > 0) {
      for (const ex of surface.exercises) {
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

    surface.lastCaptureBounds = {
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
    if (surface.isUnderlayVisible && docUnderlayImg && docUnderlayImg.complete && docUnderlayImg.naturalWidth > 0) {
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
    if (surface.exercises && surface.exercises.length > 0) {
      for (let i = 0; i < surface.exercises.length; i++) {
        const ex = surface.exercises[i];
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
        octx.fillText(`${ex.title || 'Aufgabe'}`, cx + 12, cy + 22);

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
    for (let i = 0; i < surface.strokes.length; i++) {
      surface.renderStrokeToContext(octx, surface.strokes[i]);
    }

    // 4. Feiner Indikator für Theas aktuellen Bildschirmausschnitt
    const isScrolledOrZoomed = Math.abs(surface.panY) > 20 || Math.abs(surface.panX) > 20 || surface.scale > 1.05 || captureHeight > viewH * 1.25;
    if (isScrolledOrZoomed) {
      octx.save();
      octx.strokeStyle = isChalk ? "rgba(251, 191, 36, 0.65)" : "rgba(37, 99, 235, 0.65)";
      octx.lineWidth = 2.5;
      octx.setLineDash([8, 6]);
      octx.strokeRect(viewLeft, viewTop, viewRight - viewLeft, viewBottom - viewTop);
      octx.fillStyle = isChalk ? "rgba(251, 191, 36, 0.85)" : "rgba(37, 99, 235, 0.85)";
      octx.font = "14px -apple-system, sans-serif";
      octx.fillText("Theas aktueller Bildschirmausschnitt", viewLeft + 10, Math.max(viewTop + 18, 22));
      octx.restore();
    }

    return offscreen.toDataURL("image/jpeg", 0.85);
  }

  // 9. Backend-Persistenz (Auto-Save OHNE teures toDataURL)
  // Speichern läuft unbemerkt im Hintergrund; sichtbar wird nur ein Fehler (sonst gingen Notizen verloren)
  function setBookDocSaveStatus(status) {
    if (!docSaveStatus) return;
    if (status === "error") {
      docSaveStatus.innerHTML = iconText("Warnung", "Nicht gespeichert");
      docSaveStatus.style.display = "inline-flex";
    } else if (status === "saved") {
      docSaveStatus.style.display = "none";
    }
  }

  // Die Notizen einer Seite werden relativ zum Seitenbild gespeichert – dafür muss es geladen sein
  function waitForUnderlayImage(timeoutMs = 8000) {
    if (docUnderlayImg.complete && docUnderlayImg.naturalWidth > 0) return Promise.resolve(true);
    return new Promise((resolve) => {
      const done = (ok) => {
        clearTimeout(timer);
        docUnderlayImg.removeEventListener("load", onLoad);
        docUnderlayImg.removeEventListener("error", onError);
        resolve(ok);
      };
      const onLoad = () => done(docUnderlayImg.naturalWidth > 0);
      const onError = () => done(false);
      const timer = setTimeout(() => done(false), timeoutMs);
      docUnderlayImg.addEventListener("load", onLoad);
      docUnderlayImg.addEventListener("error", onError);
    });
  }

  async function saveBookPageAnnotationsNow() {
    if (!surface.isBookPageMode || !bookPageContext || !docUnderlayImg) return;
    clearTimeout(bookPageSaveDebounceTimer);
    bookPageSaveDebounceTimer = null;
    setBookDocSaveStatus("saving");
    const context = bookPageContext;
    const page = context.page;

    if (!(await waitForUnderlayImage()) || bookPageContext !== context || context.page !== page) {
      // Bild nicht da oder Seite inzwischen gewechselt: sichtbar machen und später erneut versuchen
      setBookDocSaveStatus("error");
      if (bookPageContext === context && context.page === page) scheduleBookPageAutoSave(3000);
      return;
    }

    const dx = docUnderlayImg.offsetLeft || 0;
    const dy = docUnderlayImg.offsetTop || 0;
    const dw = docUnderlayImg.offsetWidth || docUnderlayImg.naturalWidth;
    const dh = docUnderlayImg.offsetHeight || docUnderlayImg.naturalHeight;
    if (dw === 0 || dh === 0) {
      setBookDocSaveStatus("error");
      scheduleBookPageAutoSave(3000);
      return;
    }

    const normalizedStrokes = surface.strokes.map(s => ({
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
        material_id: context.materialId,
        page_number: page,
        strokes: normalizedStrokes,
        strokes_json: JSON.stringify(normalizedStrokes)
      };
      const res = await apiFetch(`/api/v1/materials/${context.materialId}/pages/${page}/annotations`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        setBookDocSaveStatus("saved");
        return;
      }
      console.error("Speichern der Seiten-Notizen: HTTP", res.status);
    } catch (err) {
      console.error("Fehler beim Speichern der Buchseiten-Notizen:", err);
    }
    // Fehlgeschlagen: anzeigen und erneut versuchen, solange die Seite offen ist
    setBookDocSaveStatus("error");
    if (bookPageContext === context && context.page === page) scheduleBookPageAutoSave(3000);
  }

  function scheduleBookPageAutoSave(delayMs = 700) {
    clearTimeout(bookPageSaveDebounceTimer);
    bookPageSaveDebounceTimer = setTimeout(() => {
      saveBookPageAnnotationsNow();
    }, delayMs);
  }

  // Neue Seite: Striche der vorigen Seite entfernen (erst nachdem sie gespeichert sind)
  function clearPageStrokes() {
    surface.strokes = [];
    surface.undoStack = [];
    surface.redoStack = [];
    surface.redrawAllStrokes();
  }

  // Lädt die gespeicherten Notizen der Seite. Was Thea inzwischen schon gezeichnet hat, bleibt erhalten
  // (zusammengeführt über die Strich-IDs, daher schadet doppeltes Laden nicht).
  async function loadBookPageAnnotations() {
    if (!surface.isBookPageMode || !bookPageContext || !docUnderlayImg) return;
    const context = bookPageContext;
    const page = context.page;

    const dx = docUnderlayImg.offsetLeft || 0;
    const dy = docUnderlayImg.offsetTop || 0;
    const dw = docUnderlayImg.offsetWidth || docUnderlayImg.naturalWidth;
    const dh = docUnderlayImg.offsetHeight || docUnderlayImg.naturalHeight;
    if (dw === 0 || dh === 0) return;

    try {
      const res = await apiFetch(`/api/v1/materials/${context.materialId}/pages/${page}/annotations`);
      if (bookPageContext !== context || context.page !== page) return;  // Seite inzwischen gewechselt
      if (res.ok) {
        const data = await res.json();
        let loaded = [];
        if (Array.isArray(data.strokes) && data.strokes.length > 0) {
          loaded = data.strokes;
        } else if (data.strokes_json) {
          try { loaded = JSON.parse(data.strokes_json) || []; } catch (_) {}
        }

        const loadedStrokes = loaded.map(s => ({
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
        const loadedIds = new Set(loadedStrokes.map(s => s.id));
        const drawnMeanwhile = surface.strokes.filter(s => !loadedIds.has(s.id));
        surface.strokes = loadedStrokes.concat(drawnMeanwhile);
        surface.redrawAllStrokes();
        if (drawnMeanwhile.length) scheduleBookPageAutoSave();
        else setBookDocSaveStatus("saved");
      }
    } catch (err) {
      console.error("Fehler beim Laden der Buch-Notizen auf Tafel:", err);
    }
  }

  function scheduleAutoSave() {
    if (surface.isBookPageMode) {
      scheduleBookPageAutoSave();
      return;
    }
    clearTimeout(saveDebounceTimer);
    saveDebounceTimer = setTimeout(async () => {
      if (!surface.currentSession || surface.isBookPageMode) return;
      try {
        const payload = {
          board_state_json: JSON.stringify(surface.strokes)
        };
        await apiFetch(`/api/v1/whiteboard/sessions/${surface.currentSession.id}/state`, {
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
      const res = await apiFetch(`/api/v1/materials?subject_id=${encodeURIComponent(subjectId)}`);
      if (res.ok) {
        currentSubjectMaterialsList = await res.json();
      }
    } catch (err) {
      console.warn("Fehler beim Laden der Fach-Materialien:", err);
    }

    materialSelect.innerHTML = `<option value="">Freies Üben (ohne Vorlage)</option>`;
    if (currentSubjectMaterialsList.length === 0) {
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
  }

  // Dokument-Unterlage und ihre Kopfleiste ausblenden (Ende des Dokumentmodus)
  function updateUnderlayVisibility() {
    if (!docUnderlay || !docTopbar) return;
    docUnderlay.style.display = "none";
    docTopbar.style.display = "none";
  }

  async function initSession() {
    try {
      // 1. Fächer in Dropdown einbinden
      const subRes = await apiFetch("/api/v1/taxonomy/subjects");
      if (subRes.ok) {
        const subjects = await subRes.json();
        subjectSelect.innerHTML = subjects.map(s => `
          <option value="${s.id}">${escapeHtml(s.name)}</option>
        `).join("");
      }

      // 2. Zuletzt geöffnete Tafel wieder öffnen (oder eine neue anlegen)
      await openLastBoard(null);
      await loadMaterialsForSubject(subjectSelect.value);
    } catch (e) {
      console.error("Fehler beim Initialisieren der Sitzung:", e);
    }
  }

  async function createNewSession() {
    await startNewBoard(subjectSelect.value || "sub_math");
  }

  // 10. WebSocket Verbindung
  function connectTutorWebSocket() {
    if (!surface.currentSession) return;
    if (tutorSocket) {
      tutorSocket.close();
    }

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/ws/tutor/${surface.currentSession.id}`;

    try {
      tutorSocket = new WebSocket(wsUrl);

      tutorSocket.onopen = () => {
        wsDot.style.background = "#10b981";
        wsDot.style.boxShadow = "0 0 8px #10b981";
        wsStatus.textContent = "Live verbunden";
        if (wsDot.parentElement) wsDot.parentElement.title = "Live verbunden";
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
        if (wsDot.parentElement) wsDot.parentElement.title = "Offline";
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
    surface.currentTool = tool;
    document.querySelectorAll(".wb-tool-btn").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.tool === tool);
    });
  }

  function setSize(size) {
    surface.currentBaseWidth = parseFloat(size);
    document.querySelectorAll(".wb-dot-btn").forEach(btn => {
      btn.classList.toggle("active", parseFloat(btn.dataset.size) === surface.currentBaseWidth);
    });
  }

  function setColor(color) {
    surface.currentColor = color;
    document.querySelectorAll(".wb-color-swatch").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.color.toLowerCase() === color.toLowerCase());
    });
    // Farbpunkte der Strichstärken dezent mit der gewählten Farbe einfärben
    document.querySelectorAll(".wb-dot").forEach(dot => {
      dot.style.backgroundColor = color;
    });
    if (surface.currentTool === "pixel_eraser" || surface.currentTool === "object_eraser" || surface.currentTool === "eraser") {
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
      surface.penOnlyMode = !surface.penOnlyMode;
      btnPenOnly.classList.toggle("active", surface.penOnlyMode);
      const penLabel = document.getElementById("wb-pen-label");
      if (penLabel) penLabel.textContent = surface.penOnlyMode ? "Pencil" : "Touch";
      btnPenOnly.title = surface.penOnlyMode
        ? "Apple Pencil aktiv (Handfläche wird ignoriert)"
        : "Touch-Modus aktiv (Finger und Stift zeichnen)";
    });
  }

  if (btnUndo) {
    btnUndo.addEventListener("click", () => {
      if (surface.undoStack.length === 0) return;
      const action = surface.undoStack.pop();

      if (action.type === "add_stroke") {
        const idx = surface.strokes.lastIndexOf(action.stroke);
        if (idx !== -1) {
          surface.strokes.splice(idx, 1);
        }
        surface.redoStack.push(action);
      } else if (action.type === "delete_strokes") {
        for (let i = action.items.length - 1; i >= 0; i--) {
          const item = action.items[i];
          surface.strokes.splice(item.index, 0, item.stroke);
        }
        surface.redoStack.push(action);
      } else if (action.type === "clear") {
        surface.strokes = [...action.previous];
        surface.redoStack.push(action);
      }

      surface.redrawAllStrokes();
      scheduleAutoSave();
    });
  }

  if (btnRedo) {
    btnRedo.addEventListener("click", () => {
      if (surface.redoStack.length === 0) return;
      const action = surface.redoStack.pop();

      if (action.type === "add_stroke") {
        surface.strokes.push(action.stroke);
        surface.undoStack.push(action);
      } else if (action.type === "delete_strokes") {
        action.items.forEach(item => {
          const idx = surface.strokes.indexOf(item.stroke);
          if (idx !== -1) {
            surface.strokes.splice(idx, 1);
          }
        });
        surface.undoStack.push(action);
      } else if (action.type === "clear") {
        surface.strokes = [];
        surface.undoStack.push(action);
      }

      surface.redrawAllStrokes();
      scheduleAutoSave();
    });
  }

  if (btnClear) {
    btnClear.addEventListener("click", () => {
      if (surface.strokes.length === 0) return;
      if (confirm("Möchtest du die gesamte Tafel leeren?")) {
        surface.undoStack.push({ type: "clear", previous: [...surface.strokes] });
        surface.redoStack = [];
        surface.strokes = [];
        surface.redrawAllStrokes();
        overlayCtx.clearRect(0, 0, overlayCanvas.width / surface.dpr, overlayCanvas.height / surface.dpr);
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

  // Neue Tafel: die bisherige wird gespeichert und bleibt in der Liste (keine Rückfrage nötig)
  if (btnNewSession) {
    btnNewSession.addEventListener("click", queued(() => startNewBoard(subjectSelect.value)));
  }

  // Fachwechsel: zuletzt geöffnete Tafel des Fachs (oder eine neue)
  if (subjectSelect) {
    subjectSelect.addEventListener("change", queued(async () => {
      const subjectId = subjectSelect.value;
      await loadMaterialsForSubject(subjectId);
      await openLastBoard(subjectId);
    }));
  }

  // Unterlage wählen: das Dokument öffnet sich mit seinen eigenen Notizen (pro Seite)
  if (materialSelect) {
    materialSelect.addEventListener("change", queued(async () => {
      const matId = materialSelect.value;
      if (!matId) {
        await closeDocument();
      } else if (!(surface.isBookPageMode && bookPageContext && bookPageContext.materialId === matId)) {
        await openMaterialDocument(matId, subjectSelect.value);
      }
    }));
  }

  // Vorlagen-Pager Buttons
  if (btnDocPrev) {
    btnDocPrev.addEventListener("click", async () => {
      if (surface.isBookPageMode && bookPageContext && bookPageContext.page > 1) {
        await saveBookPageAnnotationsNow();
        bookPageContext.page--;
        const p = bookPageContext.page;
        if (docPageInfo) docPageInfo.textContent = `${p} / ${bookPageContext.pageCount || 1}`;
        btnDocPrev.disabled = p <= 1;
        if (btnDocNext) btnDocNext.disabled = p >= bookPageContext.pageCount;
        clearPageStrokes();
        docUnderlayImg.src = `/api/v1/materials/${bookPageContext.materialId}/preview?page=${p}`;
        loadBookPageAnnotations();
      }
    });
  }
  if (btnDocNext) {
    btnDocNext.addEventListener("click", async () => {
      if (surface.isBookPageMode && bookPageContext && bookPageContext.page < (bookPageContext.pageCount || 1)) {
        await saveBookPageAnnotationsNow();
        bookPageContext.page++;
        const p = bookPageContext.page;
        if (docPageInfo) docPageInfo.textContent = `${p} / ${bookPageContext.pageCount || 1}`;
        btnDocPrev.disabled = p <= 1;
        if (btnDocNext) btnDocNext.disabled = p >= bookPageContext.pageCount;
        clearPageStrokes();
        docUnderlayImg.src = `/api/v1/materials/${bookPageContext.materialId}/preview?page=${p}`;
        loadBookPageAnnotations();
      }
    });
  }
  // Dokument schließen: Notizen speichern, zurück zur zuletzt geöffneten Tafel des Fachs
  if (btnDocClose) {
    btnDocClose.addEventListener("click", queued(closeDocument));
  }

  if (btnReturnToBook) {
    btnReturnToBook.addEventListener("click", queued(async () => {
      if (!surface.isBookPageMode || !bookPageContext) return;
      const retPage = bookPageContext.page;
      const subjectId = bookPageContext.subjectId || subjectSelect.value;
      await saveBookPageAnnotationsNow();
      exitDocumentMode();
      if (typeof window.returnToBookReader === "function") {
        window.returnToBookReader(retPage);
      }
      // Im Hintergrund die Tafel des Fachs bereitlegen, damit der nächste Besuch nicht leer ist
      await openLastBoard(subjectId);
    }));
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
      if (!surface.currentSession) return;
      stopTutorSpeech();

      if (surface.strokes.length === 0 && !surface.isUnderlayVisible) {
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
        const res = await apiFetch(`/api/v1/whiteboard/sessions/${surface.currentSession.id}/ask-tutor`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            image_base64: snapshot,
            audio_enabled: tutorAudioEnabled,
            material_id: null
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
      setTimeout(surface.resizeCanvases, 100);
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
      if (surface.currentTool === "pixel_eraser") {
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
    fill_in_the_blank: `${icon("Schreibwerkzeuge")} Lückentext`,
    math_problem: `${icon("Mathematik")} Rechenaufgabe`,
    math_example: `${icon("Lesen")} Musterbeispiel`,
    physics_diagram: `${icon("Physik")} Physik-Diagramm`,
    formula_derivation: `${icon("Geodreieck")} Formel-Herleitung`,
    text_question: `${icon("Dokumente")} Textfrage`
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
          <button type="button" class="wb-task-check-btn" id="btn-check-${ex.id}">${icon("Suche")} Lücken prüfen</button>
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
        <button type="button" class="wb-task-hint-btn" id="btn-hint-${ex.id}">${icon("Tipp")} Tipp aufdecken</button>
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
          <button type="button" class="wb-task-close-btn" id="btn-close-${ex.id}" title="Aufgabe von der Tafel entfernen">${icon("Schließen")}</button>
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
        hintBtn.innerHTML = isOpen ? iconText("Tipp", "Tipp aufdecken") : iconText("Verbergen", "Tipp verbergen");
      });
    }

    // Löschen Listener
    const closeBtn = card.querySelector(`#btn-close-${ex.id}`);
    if (closeBtn) {
      closeBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (confirm("Möchtest du diese Aufgabe von der Tafel entfernen?")) {
          card.remove();
          surface.exercises = surface.exercises.filter(item => item.id !== ex.id);
          if (surface.currentSession) {
            try {
              await apiFetch(`/api/v1/whiteboard/sessions/${surface.currentSession.id}/exercises/${ex.id}`, {
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
    if (!surface.currentSession) return;
    const checkBtn = card.querySelector(`#btn-check-${ex.id}`);
    const progressEl = card.querySelector(`#cloze-progress-${ex.id}`);
    if (!checkBtn) return;

    const blankEls = Array.from(card.querySelectorAll(".wb-blank-zone"));
    if (blankEls.length === 0) return;

    checkBtn.disabled = true;
    checkBtn.innerHTML = iconText("Sanduhr", "Prüfe...");

    blankEls.forEach(el => {
      el.classList.remove("status-correct", "status-incorrect");
      el.classList.add("status-pending");
      const badge = el.querySelector(".wb-blank-badge");
      if (badge) badge.innerHTML = icon("Sanduhr");
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
        const vx = (screenLeft - surface.panX) / surface.scale;
        const vy = (screenTop - surface.panY) / surface.scale;
        const vw = rect.width / surface.scale;
        const vh = rect.height / surface.scale;

        const padding = 12;
        const cropX = vx - padding;
        const cropY = vy - padding;
        const cropW = vw + padding * 2;
        const cropH = vh + padding * 2;

        const overlappingStrokes = surface.strokes.filter(s => {
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
          surface.renderStrokeToContext(cropCtx, s);
        }
        cropCtx.restore();

        const cropB64 = cropCanvas.toDataURL("image/jpeg", 0.85);
        items.push({ blank_id: bid, crop_image_base64: cropB64 });
      }

      const res = await apiFetch(`/api/v1/whiteboard/sessions/${surface.currentSession.id}/exercises/${ex.id}/check-blanks`, {
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
              if (badge) badge.innerHTML = icon("Haken");
            } else if (r.unclear_handwriting) {
              el.classList.remove("status-correct", "status-incorrect");
              el.classList.add("status-unclear");
              if (badge) badge.innerHTML = icon("Schreibwerkzeuge");
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
      checkBtn.innerHTML = iconText("Suche", "Lücken prüfen");
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
      const dx = (e.clientX - startScreenX) / surface.scale;
      const dy = (e.clientY - startScreenY) / surface.scale;
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
      const dx = (e.clientX - startScreenX) / surface.scale;
      const dy = (e.clientY - startScreenY) / surface.scale;
      ex.pos_x = Math.round(startPosX + dx);
      ex.pos_y = Math.round(Math.max(20, startPosY + dy));
      e.stopPropagation();

      if (surface.currentSession) {
        try {
          await apiFetch(`/api/v1/whiteboard/sessions/${surface.currentSession.id}/exercises/${ex.id}/position`, {
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
    surface.exercises.forEach(ex => {
      const el = createExerciseCardElement(ex);
      tasksLayer.appendChild(el);
    });
  }

  async function loadSessionExercises(sessionId) {
    if (!sessionId) return;
    try {
      const res = await apiFetch(`/api/v1/whiteboard/sessions/${sessionId}/exercises`);
      if (res.ok) {
        surface.exercises = await res.json();
        renderAllExercises();
      }
    } catch (err) {
      console.warn("Fehler beim Laden der Aufgaben:", err);
    }
  }

  // Modal Handlers
  function openExerciseModal() {
    if (!exerciseModal) return;
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
      if (!surface.currentSession) {
        await createNewSession();
      }
      if (!surface.currentSession) return;

      const exType = exerciseTypeSelect ? exerciseTypeSelect.value : "auto";
      const topicText = exerciseTopicInput ? exerciseTopicInput.value.trim() : "";
      const diff = exerciseDiffSelect ? exerciseDiffSelect.value : "mittel";
      const promptText = exercisePromptInput ? exercisePromptInput.value.trim() : "";

      btnExerciseSubmit.disabled = true;
      if (btnExerciseSubmitLabel) btnExerciseSubmitLabel.textContent = "Luna erstellt Aufgabe...";

      try {
        // Gute Platzierung ermitteln: rechts neben dem aktuellen Bildschirmausschnitt oder oben
        const viewW = viewport.clientWidth || 1024;
        const initialX = Math.round(Math.max(60, (-surface.panX / surface.scale) + (viewW / surface.scale) * 0.45));
        const initialY = Math.round(Math.max(80, (-surface.panY / surface.scale) + 60));

        const res = await apiFetch(`/api/v1/whiteboard/sessions/${surface.currentSession.id}/exercises/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exercise_type: exType,
            topic_name: topicText || null,
            difficulty: diff,
            custom_prompt: promptText || null,
            material_id: null,
            audio_enabled: tutorAudioEnabled,
            pos_x: initialX,
            pos_y: initialY
          })
        });

        if (res.ok) {
          const newEx = await res.json();
          surface.exercises.push(newEx);
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

  // 13. Tafel-Verwaltung (wie Notizen): Jede freie Tafel gehört zu einem Fach. Wer etwas anderes
  //     öffnet oder beginnt, schließt die aktuelle Tafel – vorher wird sie vollständig gespeichert –
  //     und kann sie aus der Liste wieder öffnen. Dokumente (Mitschrift, Arbeitsblatt, Buchseite)
  //     sind keine eigene Tafel: ihre Notizen liegen pro Material und Seite (page_annotations).
  const btnBoards = document.getElementById("btn-wb-boards");
  const boardTitleEl = document.getElementById("wb-board-title");
  const boardsPanel = document.getElementById("wb-boards-panel");
  const boardsPanelTitle = document.getElementById("wb-boards-panel-title");
  const boardsList = document.getElementById("wb-boards-list");
  const btnBoardsNew = document.getElementById("btn-wb-boards-new");

  // Wechsel laufen nacheinander: ein Doppeltipp darf nicht zwei Tafeln gleichzeitig öffnen.
  // Nur Einstiegspunkte (Klicks, globale Funktionen) werden eingereiht, nie Aufrufe untereinander.
  let boardQueue = Promise.resolve();
  function queued(fn) {
    return (...args) => {
      boardQueue = boardQueue.then(async () => {
        await fn(...args);
        if (boardSaveWarning) boardSaveWarning.style.display = "none";
      }).catch((err) => {
        console.error("Tafel-Wechsel fehlgeschlagen:", err);
        // Sichtbar nur im Fehlerfall – sonst läuft das Speichern unbemerkt
        if (boardSaveWarning) {
          boardSaveWarning.innerHTML = iconText("Warnung", "Nicht gespeichert");
          boardSaveWarning.style.display = "inline-flex";
        }
      });
      return boardQueue;
    };
  }

  function updateBoardTitle() {
    if (!boardTitleEl) return;
    if (surface.isBookPageMode && bookPageContext) {
      boardTitleEl.textContent = bookPageContext.title || "Dokument";
    } else {
      boardTitleEl.textContent = surface.currentSession ? (surface.currentSession.title || "Tafel") : "Tafel";
    }
  }

  function applyBoard(board) {
    surface.currentSession = board;
    let loaded = [];
    try {
      loaded = JSON.parse(board.board_state_json || "[]") || [];
    } catch (e) {
      loaded = [];
    }
    surface.strokes = Array.isArray(loaded) ? loaded : [];
    surface.strokes.forEach(s => {
      if (!s.bbox && s.points) s.bbox = surface.computeBoundingBox(s.points);
    });
    surface.undoStack = [];
    surface.redoStack = [];
    surface.exercises = [];
    if (tasksLayer) tasksLayer.innerHTML = "";
    if (subjectSelect && board.subject_id) subjectSelect.value = board.subject_id;
    surface.panY = 0;
    surface.updateViewportPan();
    updateBoardTitle();
    loadSessionExercises(board.id);
    connectTutorWebSocket();
  }

  // Vorschaubild der ganzen Tafel (Liste und KI-Name), unabhängig vom sichtbaren Ausschnitt
  function renderBoardThumbnail() {
    const inked = surface.strokes.filter(s => s.points && s.points.length && s.tool !== "pixel_eraser" && s.tool !== "eraser");
    if (inked.length === 0) return null;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    inked.forEach(s => s.points.forEach(p => {
      if (p.x < minX) minX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.x > maxX) maxX = p.x;
      if (p.y > maxY) maxY = p.y;
    }));
    const W = 480, H = 320, PAD = 18;
    const w = Math.max(maxX - minX, 1);
    const h = Math.max(maxY - minY, 1);
    const k = Math.min((W - 2 * PAD) / w, (H - 2 * PAD) / h, 2);

    // Striche (inkl. Radierer) auf eine transparente Ebene, dann auf den Tafelhintergrund
    const ink = document.createElement("canvas");
    ink.width = W;
    ink.height = H;
    const inkLayer = ink.getContext("2d");
    inkLayer.setTransform(k, 0, 0, k, (W - w * k) / 2 - minX * k, (H - h * k) / 2 - minY * k);
    surface.strokes.forEach(s => surface.renderStrokeToContext(inkLayer, s));

    const out = document.createElement("canvas");
    out.width = W;
    out.height = H;
    const outCtx = out.getContext("2d");
    outCtx.fillStyle = getComputedStyle(viewport).backgroundColor || "#121620";
    outCtx.fillRect(0, 0, W, H);
    outCtx.drawImage(ink, 0, 0);
    return out.toDataURL("image/jpeg", 0.75);
  }

  async function saveBoardNow(withThumbnail) {
    clearTimeout(saveDebounceTimer);
    if (!surface.currentSession || surface.isBookPageMode) return;
    const payload = { board_state_json: JSON.stringify(surface.strokes) };
    if (withThumbnail) {
      const thumb = renderBoardThumbnail();
      if (thumb) payload.snapshot_data_url = thumb;
    }
    const res = await apiFetch(`/api/v1/whiteboard/sessions/${surface.currentSession.id}/state`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(`Tafel nicht gespeichert (HTTP ${res.status})`);
  }

  async function closeCurrentBoard() {
    if (!surface.currentSession) return;
    const board = surface.currentSession;
    const empty = surface.strokes.length === 0;
    await saveBoardNow(true);  // scheitert das Speichern, bleibt die Tafel offen
    surface.currentSession = null;
    const closing = apiFetch(`/api/v1/boards/${board.id}/close`, { method: "POST", keepalive: true }).catch(() => {});
    // Leere Tafeln verwirft der Server sofort – abwarten, damit sie nicht wieder auftauchen.
    // Sonst nicht warten: den Namen vergibt die KI im Hintergrund.
    if (empty) await closing;
  }

  function exitDocumentMode() {
    surface.isBookPageMode = false;
    bookPageContext = null;
    clearTimeout(bookPageSaveDebounceTimer);
    surface.isUnderlayVisible = false;
    updateUnderlayVisibility();
    if (btnReturnToBook) btnReturnToBook.style.display = "none";
    if (docSaveStatus) docSaveStatus.style.display = "none";
    if (btnDocClose) btnDocClose.style.display = "inline-block";
    if (materialSelect) materialSelect.value = "";
    surface.strokes = [];
    surface.undoStack = [];
    surface.redoStack = [];
    surface.redrawAllStrokes();
    updateBoardTitle();
  }

  async function leaveCurrent() {
    if (surface.isBookPageMode) {
      await saveBookPageAnnotationsNow();
      exitDocumentMode();
    } else {
      await closeCurrentBoard();
    }
  }

  async function startNewBoard(subjectId) {
    await leaveCurrent();
    applyBoard(await apiJson("/api/v1/boards", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject_id: subjectId || subjectSelect.value || "sub_math" })
    }));
  }

  async function openBoard(boardId) {
    if (!surface.isBookPageMode && surface.currentSession && surface.currentSession.id === boardId) return;
    await leaveCurrent();
    applyBoard(await apiJson(`/api/v1/boards/${boardId}/open`, { method: "POST" }));
  }

  async function openLastBoard(subjectId) {
    // Schon die Tafel dieses Fachs offen? Dann bleibt sie offen.
    if (!surface.isBookPageMode && surface.currentSession && subjectId && surface.currentSession.subject_id === subjectId) return;
    await leaveCurrent();
    const query = subjectId ? `?subject_id=${encodeURIComponent(subjectId)}` : "";
    const last = await apiJson(`/api/v1/boards/last${query}`);
    if (last) {
      applyBoard(await apiJson(`/api/v1/boards/${last.id}/open`, { method: "POST" }));
    } else {
      await startNewBoard(subjectId);
    }
  }

  // Dokument auf der Tafel: Notizen pro Seite, Zeichnen nur auf der Seite
  async function openDocument({ materialId, page = 1, pageCount = 1, title = "Dokument", subjectId = null, badge = "Dokument", returnToBook = false }) {
    await leaveCurrent();
    surface.isBookPageMode = true;
    bookPageContext = { materialId, page, pageCount, title, subjectId };
    surface.strokes = [];
    surface.undoStack = [];
    surface.redoStack = [];
    surface.redrawAllStrokes();
    if (tasksLayer) tasksLayer.innerHTML = "";

    if (subjectId && subjectSelect && subjectSelect.value !== subjectId) {
      subjectSelect.value = subjectId;
      await loadMaterialsForSubject(subjectId);
    }
    if (materialSelect) {
      materialSelect.value = currentSubjectMaterialsList.some(m => m.id === materialId) ? materialId : "";
    }
    updateBoardTitle();

    // Standard-Farbe auf Blau stellen, falls Weiß aktiv ist (damit auf weißer Seite lesbar)
    if (surface.currentColor === "#f8fafc" || surface.currentColor === "#ffffff") {
      setColor("#38bdf8");
    }

    // Viewport zurücksetzen
    surface.panX = 0;
    surface.panY = 0;
    surface.scale = 1.0;

    // Topbar anpassen
    if (docTopbar) docTopbar.style.display = "flex";
    if (btnReturnToBook) btnReturnToBook.style.display = returnToBook ? "inline-flex" : "none";
    if (docPageInfo) docPageInfo.textContent = `${page} / ${pageCount || 1}`;
    if (btnDocPrev) btnDocPrev.disabled = page <= 1;
    if (btnDocNext) btnDocNext.disabled = page >= pageCount;
    if (btnDocClose) btnDocClose.style.display = returnToBook ? "none" : "inline-block";

    // Underlay anzeigen
    surface.isUnderlayVisible = true;
    if (docUnderlay) docUnderlay.style.display = "block";

    const targetSrc = `/api/v1/materials/${materialId}/preview?page=${page}`;
    docUnderlayImg.onload = () => {
      surface.updateViewportPan();
      loadBookPageAnnotations();
    };
    docUnderlayImg.src = targetSrc;
    if (docUnderlayImg.complete && docUnderlayImg.naturalWidth > 0) {
      surface.updateViewportPan();
      loadBookPageAnnotations();
    }
  }

  async function openMaterialDocument(materialId, subjectId) {
    const mat = currentSubjectMaterialsList.find(m => m.id === materialId)
      || await apiJson(`/api/v1/materials/${materialId}`);
    await openDocument({
      materialId,
      page: 1,
      pageCount: mat.page_count || 1,
      title: mat.title || "Dokument",
      subjectId: subjectId || mat.subject_id,
      badge: mat.kind || "Dokument"
    });
  }

  async function closeDocument() {
    if (!surface.isBookPageMode) return;
    const subjectId = (bookPageContext && bookPageContext.subjectId) || subjectSelect.value;
    await saveBookPageAnnotationsNow();
    exitDocumentMode();
    await openLastBoard(subjectId);
  }

  // Liste der Tafeln eines Fachs
  function formatBoardDate(iso) {
    if (!iso) return "";
    const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);  // Server liefert UTC
    return `${d.toLocaleDateString("de-DE", { day: "numeric", month: "short" })}, ${d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}`;
  }

  function makeIconButton(iconName, title, onClick) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "wb-boards-icon-btn";
    btn.title = title;
    btn.setAttribute("aria-label", title);
    btn.innerHTML = icon(iconName);
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      onClick();
    });
    return btn;
  }

  function createBoardListItem(b) {
    const item = document.createElement("div");
    item.className = "wb-boards-item";
    if (!surface.isBookPageMode && surface.currentSession && surface.currentSession.id === b.id) item.classList.add("active");

    const thumb = document.createElement(b.has_thumbnail ? "img" : "div");
    thumb.className = "wb-boards-thumb";
    if (b.has_thumbnail) {
      thumb.src = `/api/v1/boards/${b.id}/thumbnail?v=${encodeURIComponent(b.updated_at || "")}`;
      thumb.alt = "";
    }

    const text = document.createElement("div");
    text.className = "wb-boards-text";
    const title = document.createElement("div");
    title.className = "wb-boards-title";
    title.textContent = b.title || "Tafel";
    const meta = document.createElement("div");
    meta.className = "wb-boards-meta";
    meta.textContent = formatBoardDate(b.updated_at || b.created_at);
    text.append(title, meta);

    const actions = document.createElement("div");
    actions.className = "wb-boards-actions";
    actions.append(
      makeIconButton("Schreibwerkzeuge", "Umbenennen", () => renameBoard(b)),
      makeIconButton("Archiv", "Archivieren", () => archiveBoard(b))
    );

    item.append(thumb, text, actions);
    item.addEventListener("click", () => {
      closeBoardsPanel();
      queued(openBoard)(b.id);
    });
    return item;
  }

  async function renderBoardsPanel() {
    if (!boardsList) return;
    const option = subjectSelect && subjectSelect.selectedOptions[0];
    if (boardsPanelTitle) boardsPanelTitle.textContent = `Tafeln · ${option ? option.textContent.trim() : ""}`;
    let boards = [];
    try {
      boards = await apiJson(`/api/v1/boards?subject_id=${encodeURIComponent(subjectSelect.value)}`);
    } catch (err) {
      console.warn("Tafeln nicht geladen:", err);
    }
    boardsList.textContent = "";
    if (boards.length === 0) {
      const empty = document.createElement("div");
      empty.className = "wb-boards-empty";
      empty.textContent = "Noch keine Tafeln in diesem Fach.";
      boardsList.appendChild(empty);
      return;
    }
    boards.forEach(b => boardsList.appendChild(createBoardListItem(b)));
  }

  async function renameBoard(b) {
    const name = prompt("Name der Tafel:", b.title || "");
    if (name === null || !name.trim()) return;
    try {
      const updated = await apiJson(`/api/v1/boards/${b.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: name.trim().slice(0, 60) })
      });
      if (surface.currentSession && surface.currentSession.id === b.id) {
        surface.currentSession.title = updated.title;
        surface.currentSession.title_source = updated.title_source;
        updateBoardTitle();
      }
    } catch (err) {
      console.warn("Umbenennen fehlgeschlagen:", err);
    }
    renderBoardsPanel();
  }

  const archiveBoard = queued(async (b) => {
    if (!confirm(`„${b.title || "Tafel"}“ archivieren? Die Tafel verschwindet aus der Liste.`)) return;
    const isCurrent = !surface.isBookPageMode && surface.currentSession && surface.currentSession.id === b.id;
    if (isCurrent) {
      await saveBoardNow(true);
      surface.currentSession = null;
    }
    await apiJson(`/api/v1/boards/${b.id}/archive`, { method: "POST" });
    if (isCurrent) await openLastBoard(subjectSelect.value);
    renderBoardsPanel();
  });

  // Die Liste liegt fest über dem Bildschirm (sonst schnitte die seitlich scrollbare Kopfleiste
  // sie ab) – direkt unter dem Knopf, ohne rechts über den Rand zu ragen.
  function positionBoardsPanel() {
    const r = btnBoards.getBoundingClientRect();
    const width = boardsPanel.offsetWidth || 420;
    boardsPanel.style.top = `${Math.round(r.bottom + 8)}px`;
    boardsPanel.style.left = `${Math.round(Math.max(8, Math.min(r.left, window.innerWidth - width - 8)))}px`;
  }

  function closeBoardsPanel() {
    if (boardsPanel) boardsPanel.style.display = "none";
  }

  if (btnBoards && boardsPanel) {
    btnBoards.addEventListener("click", () => {
      if (boardsPanel.style.display !== "none") {
        closeBoardsPanel();
        return;
      }
      boardsPanel.style.display = "flex";
      positionBoardsPanel();
      renderBoardsPanel();
    });
    // Die Kopfleiste scrollt seitlich: Liste schließen statt vom Knopf wegzurutschen
    const headerBar = btnBoards.closest(".wb-header-bar");
    if (headerBar) headerBar.addEventListener("scroll", closeBoardsPanel, { passive: true });
    window.addEventListener("resize", closeBoardsPanel);
    // Außerhalb tippen schließt die Liste (pointerdown, weil die Tafel Klicks unterdrückt)
    document.addEventListener("pointerdown", (e) => {
      if (boardsPanel.style.display === "none") return;
      if (boardsPanel.contains(e.target) || btnBoards.contains(e.target)) return;
      closeBoardsPanel();
    }, true);
  }
  if (btnBoardsNew) {
    btnBoardsNew.addEventListener("click", () => {
      closeBoardsPanel();
      queued(startNewBoard)(subjectSelect.value);
    });
  }

  // Globale Einstiege (Fachseite, Dokumentkarten, Buchleser)
  function showBoardTab() {
    if (typeof switchToTab === "function") {
      switchToTab("whiteboard");
    } else {
      const tabBtn = document.querySelector('.nav-tab[data-tab="whiteboard"]');
      if (tabBtn) tabBtn.click();
    }
  }

  window.openMaterialOnWhiteboard = function(materialId, subjectId = null) {
    showBoardTab();
    return queued(openMaterialDocument)(materialId, subjectId);
  };

  window.openBookPageOnWhiteboard = function({ materialId, page = 1, pageCount = 1, title = "Buchseite", subjectId = null }) {
    showBoardTab();
    return queued(openDocument)({ materialId, page, pageCount, title, subjectId, badge: "Buchseite", returnToBook: true });
  };

  window.openBoardOnWhiteboard = function(boardId) {
    showBoardTab();
    return queued(openBoard)(boardId);
  };

  window.openNewBoardOnWhiteboard = function(subjectId) {
    showBoardTab();
    return queued(startNewBoard)(subjectId);
  };

  // Von der Fachseite aus: Umbenennen (alle) und Löschen (nur Eltern). Läuft hier, weil die Tafel
  // die gerade geöffnete Tafel kennt – Titel nachziehen, nicht auf eine gelöschte Tafel speichern.
  window.renameBoardFromList = (b) => renameBoard(b);

  window.deleteBoardFromList = queued(async (b) => {
    const isCurrent = !surface.isBookPageMode && surface.currentSession && surface.currentSession.id === b.id;
    if (isCurrent) {
      clearTimeout(saveDebounceTimer);
      surface.currentSession = null;
    }
    const res = await apiFetch(`/api/v1/boards/${encodeURIComponent(b.id)}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`Tafel nicht gelöscht (HTTP ${res.status})`);
    if (isCurrent) await openLastBoard(subjectSelect.value);
    renderBoardsPanel();
  });

  setTimeout(() => {
    surface.resizeCanvases();
    queued(initSession)();
  }, 150);

})();
