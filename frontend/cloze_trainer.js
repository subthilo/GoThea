/**
 * GoThea Cloze Trainer (Lückentext-Übungsfenster)
 * 
 * Features:
 * - Eigenes fokussiertes Übungsfenster (Modal) für Lückentexte
 * - Geerdet auf Unterrichtsmaterialien & Schulfächer
 * - Zwei Eingabemodi: 🖐️ Ziehen (Drag & Drop) & ✍️ Schreiben (Handschrift / Apple Pencil)
 * - Stille 3-Sekunden Hintergrund-Auswertung beim Schreiben (Debounce)
 * - Synchrones "Gemeinsam durchgehen" mit Satz-TTS, Pause bei Fehlern,
 *   sofortigen Luna-Audio-Interjektionen (Phrasen-Pool) und Korrekturschleife.
 */

(function () {
  'use strict';

  // State
  let currentExercise = null;
  let currentMode = 'drag'; // 'drag' | 'handwrite'
  let currentSubjectId = null;
  let currentSubjectName = 'Allgemein';
  let currentMaterialId = null;
  let activeAudio = null;

  // Blanks & Evaluation state
  // blankState[blankId] = { value: '', canvas: null, ctx: null, lastDraw: 0, timer: null, evalResult: null, dirty: false }
  const blankState = {};
  let isReviewing = false;
  let reviewSentenceIndex = 0;
  let hasPendingError = false;

  // DOM Elements
  const modal = document.getElementById('modal-cloze-trainer');
  const modalTitle = document.getElementById('cloze-modal-title');
  const modalSubject = document.getElementById('cloze-modal-subject');
  const modalTopic = document.getElementById('cloze-modal-topic');
  const modalDocSource = document.getElementById('cloze-modal-doc-source');
  const lunaAvatar = document.getElementById('cloze-luna-avatar');
  const lunaBanner = document.getElementById('cloze-luna-banner');
  const lunaBannerText = document.getElementById('cloze-luna-banner-text');
  const loadingState = document.getElementById('cloze-loading-state');
  const loadingText = document.getElementById('cloze-loading-text');
  const exerciseContent = document.getElementById('cloze-exercise-content');
  const sentencesContainer = document.getElementById('cloze-sentences-container');
  const wordbankContainer = document.getElementById('cloze-wordbank-container');
  const wordbankChips = document.getElementById('cloze-wordbank-chips');
  const progressBadge = document.getElementById('cloze-progress-badge');
  const statusHint = document.getElementById('cloze-status-hint');
  const btnClose = document.getElementById('btn-close-cloze-modal');
  const btnModeDrag = document.getElementById('btn-mode-drag');
  const btnModeHandwrite = document.getElementById('btn-mode-handwrite');
  const btnClear = document.getElementById('btn-cloze-clear');
  const btnReview = document.getElementById('btn-cloze-review');
  const reviewBtnIcon = document.getElementById('cloze-review-btn-icon');
  const reviewBtnLabel = document.getElementById('cloze-review-btn-label');

  // Trigger from Subject Detail Page
  const btnSubjectStart = document.getElementById('btn-subject-start-exercise');

  function init() {
    if (!modal) return;

    // Modal Close
    if (btnClose) {
      btnClose.addEventListener('click', closeClozeTrainer);
    }

    // Mode Toggle
    if (btnModeDrag) {
      btnModeDrag.addEventListener('click', () => setMode('drag'));
    }
    if (btnModeHandwrite) {
      btnModeHandwrite.addEventListener('click', () => setMode('handwrite'));
    }

    // Actions
    if (btnClear) {
      btnClear.addEventListener('click', resetBlanks);
    }
    if (btnReview) {
      btnReview.addEventListener('click', onReviewButtonClick);
    }
  }

  /**
   * Öffnet den Cloze Trainer und lädt / generiert eine Lückentext-Übung
   */
  async function openClozeTrainer(options = {}) {
    let targetSubjectId = options.subjectId;
    if (!targetSubjectId) {
      targetSubjectId = window.currentDetailSubjectId || (window.currentSubject ? window.currentSubject.id : null);
    }
    const s = (window.cachedSubjects || []).find(x => x.id === targetSubjectId) || window.currentSubject;
    currentSubjectId = targetSubjectId || (s ? s.id : (window.currentDetailSubjectId || 'sub_english'));
    currentSubjectName = options.subjectName || (s ? s.name : 'Schulfach');
    currentMaterialId = options.materialId || null;

    modalSubject.textContent = currentSubjectName;
    modalTopic.textContent = options.topicName || 'Lerneinheit aus deinen Schulheften';
    modalTitle.textContent = 'Lückentext-Übung';

    if (options.sourceMaterialTitle) {
      modalDocSource.style.display = 'inline-block';
      modalDocSource.textContent = `📄 ${options.sourceMaterialTitle}`;
    } else {
      modalDocSource.style.display = 'none';
    }

    setMode('drag');
    resetState();
    modal.style.display = 'flex';

    // Übung laden
    await fetchOrGenerateExercise();
  }

  function closeClozeTrainer() {
    stopCurrentAudio();
    modal.style.display = 'none';
    resetState();
  }

  function resetState() {
    stopCurrentAudio();
    currentExercise = null;
    isReviewing = false;
    reviewSentenceIndex = 0;
    hasPendingError = false;
    Object.keys(blankState).forEach(k => {
      if (blankState[k].timer) clearTimeout(blankState[k].timer);
      delete blankState[k];
    });
    setLunaSpeaking(false);
    setLunaBanner('Fülle die Lücken aus. Klicke danach auf "Gemeinsam durchgehen", dann lese ich dir den Text vor!', 'info');
    updateReviewButtonState('normal');
  }

  function setMode(mode) {
    currentMode = mode;
    if (mode === 'drag') {
      btnModeDrag.classList.add('active');
      btnModeHandwrite.classList.remove('active');
      wordbankContainer.style.display = 'block';
    } else {
      btnModeHandwrite.classList.add('active');
      btnModeDrag.classList.remove('active');
      wordbankContainer.style.display = 'none';
    }
    renderExerciseContent();
  }

  /**
   * Lädt eine geerdete Lückentext-Übung vom Backend
   */
  async function fetchOrGenerateExercise() {
    showLoading(true, `Luna erstellt deine Übung für ${currentSubjectName}...`);

    try {
      const payload = {
        subject_id: currentSubjectId,
        material_id: currentMaterialId,
        difficulty: 'mittel',
        audio_enabled: true
      };

      const res = await fetch('/api/v1/exercises/cloze/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error(`Fehler beim Laden (${res.status})`);
      }

      const data = await res.json();
      currentExercise = data;

      if (data.title) modalTitle.textContent = data.title;
      if (data.topic) modalTopic.textContent = data.topic;
      if (data.source_material_title) {
        modalDocSource.style.display = 'inline-block';
        modalDocSource.textContent = `📄 ${data.source_material_title}`;
      }

      // Initialisiere blank states
      const blanks = (data.content && data.content.blanks) || [];
      blanks.forEach(b => {
        blankState[b.id] = {
          value: '',
          canvas: null,
          ctx: null,
          lastDraw: 0,
          timer: null,
          evalResult: null,
          dirty: false,
          def: b
        };
      });

      showLoading(false);
      renderExerciseContent();
      updateProgress();

      // Begrüßung / Vorlesung falls vorhanden
      if (data.tutor_speech) {
        setLunaBanner(`Luna: "${data.tutor_speech}"`, 'info');
      }

    } catch (err) {
      console.error('Fehler beim Generieren der Übung:', err);
      showLoading(false);
      setLunaBanner(`Konnte die Übung nicht laden: ${err.message}`, 'error');
    }
  }

  function showLoading(show, msg) {
    if (show) {
      loadingState.style.display = 'flex';
      exerciseContent.style.display = 'none';
      if (msg) loadingText.textContent = msg;
    } else {
      loadingState.style.display = 'none';
      exerciseContent.style.display = 'block';
    }
  }

  /**
   * Rendert die Sätze und Wortkarten
   */
  function renderExerciseContent() {
    if (!currentExercise || !currentExercise.content) return;
    const content = currentExercise.content;
    let sentences = content.sentences || [];
    const blanks = content.blanks || [];
    const wordBank = content.word_bank || [];

    if (sentences.length === 0 && content.text) {
      sentences = [{
        index: 1,
        text: content.text,
        text_with_blanks: content.text,
        blank_ids: blanks.map(b => b.id)
      }];
    }

    // 1. Sätze rendern
    sentencesContainer.innerHTML = '';
    sentences.forEach((s, sIdx) => {
      const sRow = document.createElement('div');
      sRow.className = 'cloze-sentence-row';
      sRow.id = `cloze-sentence-${sIdx}`;
      sRow.dataset.sentenceIndex = sIdx;

      // Text mit Lücken parsen
      let sText = s.text_with_blanks || s.text || '';
      // Ersetze [blank_X] oder [X] oder [[...]]
      const parts = sText.split(/(\[blank_\d+\]|\[\d+\]|\[\[.*?\]\])/g);

      parts.forEach(part => {
        if (!part) return;
        let blankId = null;
        const matchBlank = part.match(/\[(?:blank_)?(\d+)\]/);
        if (matchBlank) {
          blankId = parseInt(matchBlank[1], 10);
        } else {
          const matchToken = part.match(/\[\[(.*?)(?::(.*?))?\]\]/);
          if (matchToken) {
            const p1 = (matchToken[1] || '').trim();
            const numMatch = p1.match(/\d+/);
            if (numMatch) {
              blankId = parseInt(numMatch[0], 10);
            } else {
              const targetWord = (matchToken[2] || p1).trim().toLowerCase();
              const found = blanks.find(b => (b.expected_answer || '').toLowerCase() === targetWord);
              if (found) blankId = found.id;
            }
          }
        }

        if (blankId !== null) {
          const blankDef = blanks.find(b => b.id === blankId) || { id: blankId };
          const slot = createBlankSlotElement(blankDef, sIdx);
          sRow.appendChild(slot);
        } else {
          const span = document.createElement('span');
          span.textContent = part;
          sRow.appendChild(span);
        }
      });

      sentencesContainer.appendChild(sRow);
    });

    // 2. Wortspeicher rendern (Drag-Modus)
    renderWordBank(wordBank);

    // Initialisiere Handschrift-Canvas, falls Modus aktiv
    if (currentMode === 'handwrite') {
      setTimeout(initHandwriteCanvases, 50);
    }
  }

  function renderWordBank(wordBank) {
    wordbankChips.innerHTML = '';
    wordBank.forEach(word => {
      const chip = document.createElement('div');
      chip.className = 'cloze-word-chip';
      chip.textContent = word;
      chip.draggable = true;
      chip.dataset.word = word;

      // Prüfe, ob das Wort bereits in einer Lücke genutzt wird
      const isUsed = Object.values(blankState).some(b => b.value === word);
      if (isUsed) chip.classList.add('used');

      chip.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', word);
        e.dataTransfer.effectAllowed = 'copy';
      });

      // Klick als Fallback für Touch/iPad
      chip.addEventListener('click', () => {
        if (chip.classList.contains('used')) return;
        // Finde die erste leere Lücke
        const firstEmptyId = Object.keys(blankState).find(id => !blankState[id].value);
        if (firstEmptyId) {
          fillBlankWithValue(firstEmptyId, word);
        }
      });

      wordbankChips.appendChild(chip);
    });
  }

  /**
   * Erzeugt das DOM-Element für eine einzelne Lücke
   */
  function createBlankSlotElement(blankDef, sentenceIndex) {
    const bId = blankDef.id;
    const bState = blankState[bId] || { value: '', evalResult: null };

    if (currentMode === 'drag') {
      // Drag & Drop Element
      const dropEl = document.createElement('span');
      dropEl.className = 'cloze-blank-drop';
      dropEl.id = `cloze-blank-slot-${bId}`;
      dropEl.dataset.blankId = bId;

      if (bState.value) {
        dropEl.textContent = bState.value;
        dropEl.classList.add('is-filled');
      } else {
        dropEl.textContent = '______';
      }

      // Drag Events
      dropEl.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropEl.classList.add('drag-over');
      });
      dropEl.addEventListener('dragleave', () => {
        dropEl.classList.remove('drag-over');
      });
      dropEl.addEventListener('drop', (e) => {
        e.preventDefault();
        dropEl.classList.remove('drag-over');
        const word = e.dataTransfer.getData('text/plain');
        if (word) {
          fillBlankWithValue(bId, word);
        }
      });

      // Klick zum Leeren
      dropEl.addEventListener('click', () => {
        if (bState.value) {
          fillBlankWithValue(bId, '');
        }
      });

      return dropEl;

    } else {
      // Handschrift Canvas Element
      const wrap = document.createElement('span');
      wrap.className = 'cloze-blank-write-container';
      wrap.id = `cloze-blank-write-${bId}`;

      const canvasWrap = document.createElement('span');
      canvasWrap.className = 'cloze-blank-canvas-wrap';

      const canvas = document.createElement('canvas');
      canvas.className = 'cloze-blank-canvas';
      canvas.id = `cloze-canvas-${bId}`;
      canvas.dataset.blankId = bId;

      const clearBtn = document.createElement('button');
      clearBtn.type = 'button';
      clearBtn.className = 'cloze-blank-clear-btn';
      clearBtn.title = 'Lücke löschen';
      clearBtn.textContent = '🧹';
      clearBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearBlankCanvas(bId);
      });

      const statusBadge = document.createElement('span');
      statusBadge.className = 'cloze-blank-status-badge';
      statusBadge.id = `cloze-status-${bId}`;

      canvasWrap.appendChild(canvas);
      wrap.appendChild(canvasWrap);
      wrap.appendChild(clearBtn);
      wrap.appendChild(statusBadge);

      return wrap;
    }
  }

  function fillBlankWithValue(blankId, word) {
    if (!blankState[blankId]) return;
    blankState[blankId].value = word;
    blankState[blankId].evalResult = null; // Zurücksetzen

    const el = document.getElementById(`cloze-blank-slot-${blankId}`);
    if (el) {
      if (word) {
        el.textContent = word;
        el.classList.add('is-filled');
        el.classList.remove('is-wrong', 'is-correct');
      } else {
        el.textContent = '______';
        el.classList.remove('is-filled', 'is-wrong', 'is-correct');
      }
    }

    // Aktualisiere Wortspeicher Chips
    if (currentExercise && currentExercise.content) {
      renderWordBank(currentExercise.content.word_bank || []);
    }
    updateProgress();
  }

  /**
   * Initialisiert alle Handschrift-Canvas mit Retina-Auflösung & Event-Handling
   */
  function initHandwriteCanvases() {
    const canvases = sentencesContainer.querySelectorAll('.cloze-blank-canvas');
    const dpr = window.devicePixelRatio || 1;

    canvases.forEach(canvas => {
      const bId = parseInt(canvas.dataset.blankId, 10);
      const rect = canvas.getBoundingClientRect();
      const width = rect.width || 160;
      const height = rect.height || 48;

      canvas.width = width * dpr;
      canvas.height = height * dpr;

      const ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2.5;

      if (blankState[bId]) {
        blankState[bId].canvas = canvas;
        blankState[bId].ctx = ctx;
      }

      attachDrawingEvents(canvas, ctx, bId);
    });
  }

  function attachDrawingEvents(canvas, ctx, blankId) {
    let isDrawing = false;
    let lastX = 0;
    let lastY = 0;

    function getCoords(e) {
      const rect = canvas.getBoundingClientRect();
      let clientX = e.clientX;
      let clientY = e.clientY;
      if (clientX === undefined && e.touches && e.touches.length > 0) {
        clientX = e.touches[0].clientX;
        clientY = e.touches[0].clientY;
      }
      return {
        x: (clientX !== undefined ? clientX : 0) - rect.left,
        y: (clientY !== undefined ? clientY : 0) - rect.top
      };
    }

    function startDraw(e) {
      if (e.cancelable) e.preventDefault();
      try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
      isDrawing = true;
      const coords = getCoords(e);
      lastX = coords.x;
      lastY = coords.y;

      // Wenn zuvor ein 3-Sekunden-Timer lief, jetzt stoppen
      if (blankState[blankId] && blankState[blankId].timer) {
        clearTimeout(blankState[blankId].timer);
        blankState[blankId].timer = null;
      }
    }

    function draw(e) {
      if (!isDrawing) return;
      if (e.cancelable) e.preventDefault();
      const coords = getCoords(e);

      ctx.beginPath();
      ctx.moveTo(lastX, lastY);
      ctx.lineTo(coords.x, coords.y);
      ctx.stroke();

      lastX = coords.x;
      lastY = coords.y;

      if (blankState[blankId]) {
        blankState[blankId].dirty = true;
        blankState[blankId].lastDraw = Date.now();
      }
    }

    function stopDraw(e) {
      if (!isDrawing) return;
      isDrawing = false;
      try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}

      // Starte 3-Sekunden Debounce-Timer für lautlose KI-Überprüfung im Hintergrund
      scheduleSilentEvaluation(blankId);
      updateProgress();
    }

    // Pointer Events (Apple Pencil & Touch & Mouse)
    canvas.addEventListener('pointerdown', startDraw);
    canvas.addEventListener('pointermove', draw);
    canvas.addEventListener('pointerup', stopDraw);
    canvas.addEventListener('pointercancel', stopDraw);
    canvas.addEventListener('pointerleave', stopDraw);

    // iOS Safari Anti-Callout ('Teilen...') & Geste-Blockierung
    const blockNative = (e) => {
      if (e.cancelable) e.preventDefault();
    };
    canvas.addEventListener('contextmenu', blockNative, { capture: true });
    canvas.addEventListener('selectstart', blockNative, { capture: true });
    canvas.addEventListener('gesturestart', blockNative, { passive: false, capture: true });
    canvas.addEventListener('gesturechange', blockNative, { passive: false, capture: true });
    canvas.addEventListener('gestureend', blockNative, { passive: false, capture: true });
    canvas.addEventListener('touchstart', blockNative, { passive: false, capture: true });
    canvas.addEventListener('touchmove', blockNative, { passive: false, capture: true });
    canvas.addEventListener('touchend', blockNative, { passive: false, capture: true });
    canvas.addEventListener('touchcancel', blockNative, { passive: false, capture: true });
  }

  function clearBlankCanvas(blankId) {
    const b = blankState[blankId];
    if (!b || !b.canvas || !b.ctx) return;

    const dpr = window.devicePixelRatio || 1;
    b.ctx.clearRect(0, 0, b.canvas.width / dpr, b.canvas.height / dpr);
    b.dirty = false;
    b.evalResult = null;
    if (b.timer) {
      clearTimeout(b.timer);
      b.timer = null;
    }

    const wrap = b.canvas.closest('.cloze-blank-canvas-wrap');
    if (wrap) wrap.classList.remove('is-correct', 'is-wrong');

    const badge = document.getElementById(`cloze-status-${blankId}`);
    if (badge) badge.textContent = '';

    updateProgress();
  }

  /**
   * 3-Sekunden Timer: Sendet lautlos im Hintergrund einen Mini-Crop zur KI
   */
  function scheduleSilentEvaluation(blankId) {
    const b = blankState[blankId];
    if (!b || !b.dirty) return;

    if (b.timer) clearTimeout(b.timer);

    const badge = document.getElementById(`cloze-status-${blankId}`);
    if (badge) badge.textContent = '⏳';

    b.timer = setTimeout(async () => {
      await performSilentBlankCheck(blankId);
    }, 3000); // 3 Sekunden Inaktivität
  }

  async function performSilentBlankCheck(blankId) {
    const b = blankState[blankId];
    if (!b || !b.canvas || !b.dirty) return;

    const badge = document.getElementById(`cloze-status-${blankId}`);
    const cropBase64 = b.canvas.toDataURL('image/png');

    try {
      const expectedAns = (b.def && (b.def.expected_answer || b.def.correct_answer)) || '';
      const payload = {
        blank_id: blankId,
        crop_image_base64: cropBase64,
        exercise_title: (currentExercise && currentExercise.title) || 'Lückentext',
        expected_answer: expectedAns,
        alternatives: (b.def && b.def.alternatives) || [],
        hint: (b.def && b.def.hint) || null
      };

      const res = await fetch('/api/v1/exercises/cloze/check-single-blank', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error('Check fehlgeschlagen');

      const data = await res.json();
      b.evalResult = data;
      b.value = data.recognized_text || '';

      // Dezentes Feedback
      if (badge) {
        badge.textContent = '✓';
        badge.title = `Erkannt: "${data.recognized_text || ''}"`;
      }
    } catch (err) {
      console.warn(`Lautloser Check für Lücke ${blankId} fehlgeschlagen:`, err);
      if (badge) badge.textContent = '';
    }
  }

  function updateProgress() {
    const blanks = (currentExercise && currentExercise.content && currentExercise.content.blanks) || [];
    let filledCount = 0;

    blanks.forEach(b => {
      const state = blankState[b.id];
      if (currentMode === 'drag') {
        if (state && state.value) filledCount++;
      } else {
        if (state && state.dirty) filledCount++;
      }
    });

    progressBadge.textContent = `${filledCount} / ${blanks.length} ausgefüllt`;

    if (filledCount === blanks.length && blanks.length > 0) {
      statusHint.textContent = '✨ Alle Lücken gefüllt! Bereit zum Durchgehen.';
    } else {
      statusHint.textContent = '';
    }
  }

  function resetBlanks() {
    stopCurrentAudio();
    isReviewing = false;
    hasPendingError = false;
    updateReviewButtonState('normal');

    Object.keys(blankState).forEach(id => {
      if (currentMode === 'drag') {
        fillBlankWithValue(id, '');
      } else {
        clearBlankCanvas(parseInt(id, 10));
      }
    });

    // Entferne alle Satz-Highlights
    const rows = sentencesContainer.querySelectorAll('.cloze-sentence-row');
    rows.forEach(r => r.classList.remove('reading-active', 'error-active'));

    setLunaBanner('Lücken zurückgesetzt. Auf ein Neues!', 'info');
  }

  /**
   * =========================================================================
   * GEMEINSAM DURCHGEHEN: AUDIO-VORLESE-SCHLEIFE & INTERAKTIVE KORREKTUR
   * =========================================================================
   */
  async function onReviewButtonClick() {
    if (isReviewing && hasPendingError) {
      // Thea hat die Korrektur eingetragen und will diesen Satz erneut prüfen!
      await reevaluateAndResume();
      return;
    }

    if (isReviewing) {
      // Wenn bereits aktiv, stoppen
      stopCurrentAudio();
      isReviewing = false;
      updateReviewButtonState('normal');
      setLunaSpeaking(false);
      return;
    }

    // Starte gemeinsamen Durchlauf
    await startGuidedReview();
  }

  async function startGuidedReview() {
    if (!currentExercise || !currentExercise.content) return;
    const sentences = currentExercise.content.sentences || [];
    if (sentences.length === 0) return;

    isReviewing = true;
    reviewSentenceIndex = 0;
    hasPendingError = false;
    updateReviewButtonState('playing');

    // Prüfe etwaige noch ungeprüfte Handschrift-Lücken schnell vorab
    if (currentMode === 'handwrite') {
      for (const bId of Object.keys(blankState)) {
        const b = blankState[bId];
        if (b && b.dirty && !b.evalResult) {
          await performSilentBlankCheck(parseInt(bId, 10));
        }
      }
    }

    setLunaBanner('Luna liest den Text Satz für Satz vor...', 'speaking');
    playSentenceLoop();
  }

  /**
   * Spielt die Sätze nacheinander ab und stoppt bei Fehlern
   */
  async function playSentenceLoop() {
    if (!isReviewing) return;
    const sentences = currentExercise.content.sentences || [];

    if (reviewSentenceIndex >= sentences.length) {
      // ALLE SÄTZE ERFOLGREICH BEENDET! 🎉
      await onAllSentencesCompleted();
      return;
    }

    const currentSentence = sentences[reviewSentenceIndex];
    highlightSentence(reviewSentenceIndex, 'reading');

    // 1. Prüfe, ob die Lücken in diesem Satz korrekt sind
    const blankIds = currentSentence.blank_ids || [];
    let sentenceHasError = false;
    let failingBlankDef = null;

    for (const bId of blankIds) {
      const isCorrect = evaluateBlankCorrectness(bId);
      if (!isCorrect) {
        sentenceHasError = true;
        failingBlankDef = blankState[bId] ? blankState[bId].def : null;
        markBlankVisual(bId, false);
      } else {
        markBlankVisual(bId, true);
      }
    }

    // 2. Spiele Satz-Audio ab (falls vorhanden)
    if (currentSentence.audio_base64) {
      setLunaSpeaking(true);
      await playAudioFromBase64(currentSentence.audio_base64);
      setLunaSpeaking(false);
    } else {
      // Fallback Pause
      await sleep(1800);
    }

    if (!isReviewing) return;

    // 3. Wenn ein Fehler aufgetreten ist -> ANHALTEN!
    if (sentenceHasError) {
      hasPendingError = true;
      highlightSentence(reviewSentenceIndex, 'error');
      updateReviewButtonState('error');

      // Sofortige Audio-Interjektion aus Phrasen-Pool abspielen (0 ms Latency!)
      await playInstantPhrase('error_interjections');

      // Hinweis in Banner einblenden
      const hint = failingBlankDef && failingBlankDef.hint ? `Tipp: ${failingBlankDef.hint}` : 'Schau dir diesen Satz noch einmal an!';
      setLunaBanner(`Ups, nicht ganz! ${hint}`, 'error');
      return; // Vorlesen hält hier an!
    }

    // Nächster Satz
    reviewSentenceIndex++;
    playSentenceLoop();
  }

  function evaluateBlankCorrectness(blankId) {
    const b = blankState[blankId];
    if (!b) return false;

    if (currentMode === 'drag') {
      const userVal = (b.value || '').trim().toLowerCase();
      const correctVal = ((b.def && (b.def.expected_answer || b.def.correct_answer)) || '').trim().toLowerCase();
      const alts = ((b.def && b.def.alternatives) || []).map(a => a.trim().toLowerCase());
      return userVal === correctVal || alts.includes(userVal);
    } else {
      // Handschrift
      if (b.evalResult) {
        return !!b.evalResult.is_correct;
      }
      return false;
    }
  }

  function markBlankVisual(blankId, isCorrect) {
    if (currentMode === 'drag') {
      const el = document.getElementById(`cloze-blank-slot-${blankId}`);
      if (el) {
        el.classList.remove('is-correct', 'is-wrong');
        el.classList.add(isCorrect ? 'is-correct' : 'is-wrong');
      }
    } else {
      const b = blankState[blankId];
      if (b && b.canvas) {
        const wrap = b.canvas.closest('.cloze-blank-canvas-wrap');
        if (wrap) {
          wrap.classList.remove('is-correct', 'is-wrong');
          wrap.classList.add(isCorrect ? 'is-correct' : 'is-wrong');
        }
      }
    }
  }

  /**
   * Re-Evaluation nach einer Korrektur:
   * Thea korrigiert den fehlerhaften Satz und klickt "Nochmal prüfen & weiter"
   */
  async function reevaluateAndResume() {
    const currentSentence = currentExercise.content.sentences[reviewSentenceIndex];
    const blankIds = currentSentence.blank_ids || [];

    // Im Schreibmodus neu prüfen
    if (currentMode === 'handwrite') {
      for (const bId of blankIds) {
        const b = blankState[bId];
        if (b && b.dirty) {
          await performSilentBlankCheck(bId);
        }
      }
    }

    // Prüfen
    let allFixed = true;
    for (const bId of blankIds) {
      const ok = evaluateBlankCorrectness(bId);
      markBlankVisual(bId, ok);
      if (!ok) allFixed = false;
    }

    if (allFixed) {
      hasPendingError = false;
      highlightSentence(reviewSentenceIndex, 'reading');
      updateReviewButtonState('playing');

      // Erfolgs-Interjektion aus Phrasen-Pool ("Perfekt korrigiert!")
      await playInstantPhrase('correction_success');
      setLunaBanner('Perfekt korrigiert! Weiter geht\'s...', 'speaking');

      // Satz wiederholen & weitermachen
      reviewSentenceIndex++;
      playSentenceLoop();
    } else {
      // Immer noch Fehler
      await playInstantPhrase('error_interjections');
      setLunaBanner('Noch nicht ganz. Versuch es noch einmal!', 'error');
    }
  }

  async function onAllSentencesCompleted() {
    isReviewing = false;
    hasPendingError = false;
    updateReviewButtonState('done');
    setLunaSpeaking(false);

    // Entferne Highlights
    const rows = sentencesContainer.querySelectorAll('.cloze-sentence-row');
    rows.forEach(r => r.classList.remove('reading-active', 'error-active'));

    // Lob-Phrase abspielen ("Klasse!", "Genau richtig!")
    await playInstantPhrase('praise');
    setLunaBanner('🎉 Fantastisch gelöst! Du hast alle Lücken meisterhaft ausgefüllt.', 'info');
  }

  /**
   * Holt sofort eine Audio-Phrase aus dem vorkalkulierten Pool und spielt sie ab
   */
  async function playInstantPhrase(category) {
    try {
      const res = await fetch(`/api/v1/exercises/phrases/${category}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.audio_base64) {
        setLunaSpeaking(true);
        await playAudioFromBase64(data.audio_base64);
        setLunaSpeaking(false);
      }
    } catch (e) {
      console.warn('Fehler beim Abrufen der Phrasen-Audio:', e);
    }
  }

  function highlightSentence(index, state) {
    const rows = sentencesContainer.querySelectorAll('.cloze-sentence-row');
    rows.forEach((r, idx) => {
      r.classList.remove('reading-active', 'error-active');
      if (idx === index) {
        if (state === 'reading') r.classList.add('reading-active');
        if (state === 'error') r.classList.add('error-active');
        r.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    });
  }

  function updateReviewButtonState(state) {
    if (state === 'playing') {
      btnReview.classList.remove('btn-danger');
      btnReview.classList.add('btn-primary');
      reviewBtnIcon.textContent = '⏸️';
      reviewBtnLabel.textContent = 'Vorlesen anhalten';
    } else if (state === 'error') {
      btnReview.classList.remove('btn-primary');
      btnReview.classList.add('btn-danger');
      reviewBtnIcon.textContent = '✏️';
      reviewBtnLabel.textContent = 'Korrektur prüfen & weiter';
    } else if (state === 'done') {
      btnReview.classList.remove('btn-danger');
      btnReview.classList.add('btn-primary');
      reviewBtnIcon.textContent = '🎉';
      reviewBtnLabel.textContent = 'Geschafft! Fertig';
    } else {
      btnReview.classList.remove('btn-danger');
      btnReview.classList.add('btn-primary');
      reviewBtnIcon.textContent = '🚀';
      reviewBtnLabel.textContent = 'Gemeinsam durchgehen';
    }
  }

  function setLunaSpeaking(isSpeaking) {
    if (lunaAvatar) {
      if (isSpeaking) lunaAvatar.classList.add('speaking');
      else lunaAvatar.classList.remove('speaking');
    }
    if (lunaBanner) {
      if (isSpeaking) lunaBanner.classList.add('speaking-active');
      else lunaBanner.classList.remove('speaking-active');
    }
  }

  function setLunaBanner(text, type) {
    if (!lunaBannerText) return;
    lunaBannerText.textContent = text;
    lunaBanner.classList.remove('error-alert');
    if (type === 'error') lunaBanner.classList.add('error-alert');
  }

  function playAudioFromBase64(base64Data) {
    return new Promise((resolve) => {
      stopCurrentAudio();
      try {
        const audio = new Audio(`data:audio/mp3;base64,${base64Data}`);
        activeAudio = audio;
        audio.onended = () => {
          activeAudio = null;
          resolve();
        };
        audio.onerror = () => {
          activeAudio = null;
          resolve();
        };
        audio.play().catch(() => resolve());
      } catch (err) {
        resolve();
      }
    });
  }

  function stopCurrentAudio() {
    if (activeAudio) {
      try {
        activeAudio.pause();
        activeAudio.currentTime = 0;
      } catch (e) {}
      activeAudio = null;
    }
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Global Export
  window.openClozeTrainer = openClozeTrainer;
  window.closeClozeTrainer = closeClozeTrainer;

  // DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
