/**
 * GoThea Cloze Trainer (Lückentext-Übungsfenster)
 * 
 * Features:
 * - Eigenes fokussiertes Übungsfenster (Modal) für Lückentexte
 * - Geerdet auf Unterrichtsmaterialien & Schulfächer
 * - Zwei Eingabemodi: Ziehen (Drag & Drop) & Schreiben (Handschrift / Apple Pencil)
 * - Stille 3-Sekunden Hintergrund-Auswertung beim Schreiben (Debounce)
 * - Synchrones "Gemeinsam durchgehen" mit Satz-TTS, Pause bei Fehlern,
 *   sofortigen Luna-Audio-Interjektionen (Phrasen-Pool) und Korrekturschleife.
 */

(function () {
  'use strict';

  // State
  let currentExercise = null;
  // Modus: 'handwrite' (Handschrift mit Apple Pencil) oder 'drag' (Drag & Drop)
  let currentMode = 'handwrite'; // Standardmäßig Schreiben mit dem Stift
  try {
    const savedMode = localStorage.getItem('gothea_cloze_mode');
    if (savedMode === 'drag' || savedMode === 'handwrite') {
      currentMode = savedMode;
    }
  } catch (_) {}
  let currentDifficulty = 'with_words'; // 'with_words' | 'without_words'
  let currentSubjectId = null;
  let currentSubjectName = 'Allgemein';
  let currentMaterialId = null;
  let activeAudio = null;
  let currentAdaptiveDifficulty = 'mittel';
  let currentAdaptiveLevelLabel = 'Stufe 2 (Mittel)';

  // Blanks & Evaluation state
  // blankState[blankId] = { value: '', canvas: null, ctx: null, lastDraw: 0, timer: null, evalResult: null, dirty: false, attempts: 0, isAutoRevealed: false }
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
  const modalAdaptiveBadge = document.getElementById('cloze-adaptive-level-badge');
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
  const btnBackSubject = document.getElementById('btn-exercise-back-to-subject');
  const backSubjectName = document.getElementById('cloze-back-subject-name');
  const btnNext = document.getElementById('btn-cloze-next');
  const btnModeDrag = document.getElementById('btn-mode-drag');
  const btnModeHandwrite = document.getElementById('btn-mode-handwrite');
  const difficultyToggle = document.getElementById('cloze-difficulty-toggle');
  const btnDiffWithWords = document.getElementById('btn-diff-with-words');
  const btnDiffWithoutWords = document.getElementById('btn-diff-without-words');
  const btnClear = document.getElementById('btn-cloze-clear');
  const btnReview = document.getElementById('btn-cloze-review');
  const reviewBtnIcon = document.getElementById('cloze-review-btn-icon');
  const reviewBtnLabel = document.getElementById('cloze-review-btn-label');

  // Trigger from Subject Detail Page
  const btnSubjectStart = document.getElementById('btn-subject-start-exercise');

  // Zoom & Layout Controls
  const clozeTrainerBody = document.getElementById('cloze-trainer-body');
  const btnZoomIn = document.getElementById('btn-cloze-zoom-in');
  const btnZoomOut = document.getElementById('btn-cloze-zoom-out');
  const zoomLabel = document.getElementById('cloze-zoom-label');

  const ZOOM_LEVELS = [0.85, 1.0, 1.15, 1.3, 1.5];
  let currentZoomIndex = 1; // 1.0 = 100%
  let focusedBlankId = null;

  function applyZoom(index) {
    currentZoomIndex = Math.max(0, Math.min(ZOOM_LEVELS.length - 1, index));
    const factor = ZOOM_LEVELS[currentZoomIndex];
    if (clozeTrainerBody) {
      clozeTrainerBody.style.setProperty('--cloze-zoom', factor);
    }
    if (zoomLabel) {
      zoomLabel.textContent = `${Math.round(factor * 100)}%`;
    }
  }

  function setFocusedBlank(bId) {
    focusedBlankId = bId;
    document.querySelectorAll('.cloze-blank-drop').forEach(slot => {
      const slotId = parseInt(slot.dataset.blankId, 10);
      if (bId !== null && slotId === bId) {
        slot.classList.add('focused-blank');
      } else {
        slot.classList.remove('focused-blank');
      }
    });
  }

  function init() {
    if (!modal) return;

    // Zoom Buttons
    if (btnZoomIn) {
      btnZoomIn.addEventListener('click', () => applyZoom(currentZoomIndex + 1));
    }
    if (btnZoomOut) {
      btnZoomOut.addEventListener('click', () => applyZoom(currentZoomIndex - 1));
    }

    // Modal Close / Back to Subject
    if (btnClose) {
      btnClose.addEventListener('click', closeClozeTrainer);
    }
    if (btnBackSubject) {
      btnBackSubject.addEventListener('click', closeClozeTrainer);
    }

    // Nächste Übung Button
    if (btnNext) {
      btnNext.addEventListener('click', onNextExerciseClick);
    }

    // Mode Toggle
    if (btnModeDrag) {
      btnModeDrag.addEventListener('click', () => setMode('drag'));
    }
    if (btnModeHandwrite) {
      btnModeHandwrite.addEventListener('click', () => setMode('handwrite'));
    }

    // Initialisiere Modus-Zustand (Handschrift/Stift als Standard oder gespeicherte Wahl)
    if (currentMode === 'handwrite') {
      if (btnModeHandwrite) btnModeHandwrite.classList.add('active');
      if (btnModeDrag) btnModeDrag.classList.remove('active');
      if (difficultyToggle) difficultyToggle.style.display = 'flex';
    } else {
      if (btnModeDrag) btnModeDrag.classList.add('active');
      if (btnModeHandwrite) btnModeHandwrite.classList.remove('active');
      if (difficultyToggle) difficultyToggle.style.display = 'none';
    }

    // Difficulty Toggle (Wortspeicher beim Schreiben anzeigen oder ausblenden)
    if (btnDiffWithWords) {
      btnDiffWithWords.addEventListener('click', () => setDifficulty('with_words'));
    }
    if (btnDiffWithoutWords) {
      btnDiffWithoutWords.addEventListener('click', () => setDifficulty('without_words'));
    }

    // Actions
    if (btnClear) {
      btnClear.addEventListener('click', resetBlanks);
    }
    if (btnReview) {
      btnReview.addEventListener('click', onReviewButtonClick);
    }

    // Notfall-Taste ESC zum Verlassen der Übung
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && document.body.classList.contains('exercise-fullscreen-mode')) {
        closeClozeTrainer();
      }
    });
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
      modalDocSource.innerHTML = iconText("Dokumente", `${options.sourceMaterialTitle}`);
    } else {
      modalDocSource.style.display = 'none';
    }

    setMode('drag');
    resetState();
    document.body.classList.add('exercise-fullscreen-mode');
    modal.style.display = 'flex';
    if (backSubjectName) backSubjectName.textContent = currentSubjectName;
    if (btnNext) btnNext.style.display = 'none';

    // Aktuelle adaptive Schwierigkeitsstufe ermitteln
    try {
      const adRes = await apiFetch(`/api/v1/exercises/adaptive-difficulty/${encodeURIComponent(currentSubjectId)}?exercise_type=cloze`);
      if (adRes.ok) {
        const adData = await adRes.json();
        currentAdaptiveDifficulty = adData.difficulty || 'mittel';
        currentAdaptiveLevelLabel = adData.level_label || 'Stufe 2 (Mittel)';
        if (modalAdaptiveBadge) {
          modalAdaptiveBadge.innerHTML = iconText("Ziel", `${adData.level_label || 'Stufe 2 (Mittel)'}`);
          modalAdaptiveBadge.className = `badge-adaptive-level level-${adData.level_code || 2}`;
        }
      }
    } catch (e) {
      console.warn('Fehler beim Abruf der adaptiven Stufe:', e);
    }

    // Übung laden
    await fetchOrGenerateExercise();
  }

  function closeClozeTrainer() {
    stopCurrentAudio();
    document.body.classList.remove('exercise-fullscreen-mode');
    modal.style.display = 'none';
    if (btnNext) btnNext.style.display = 'none';
    resetState();
    if (typeof window.openSubjectDetail === 'function' && currentSubjectId) {
      window.openSubjectDetail(currentSubjectId);
    } else if (typeof window.showTab === 'function') {
      window.showTab('dashboard');
    }
  }

  async function onNextExerciseClick() {
    if (btnNext) btnNext.style.display = 'none';
    stopCurrentAudio();
    resetState();
    await fetchOrGenerateExercise();
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
    try {
      localStorage.setItem('gothea_cloze_mode', mode);
    } catch (_) {}
    if (mode === 'drag') {
      if (btnModeDrag) btnModeDrag.classList.add('active');
      if (btnModeHandwrite) btnModeHandwrite.classList.remove('active');
      if (difficultyToggle) difficultyToggle.style.display = 'none';
    } else {
      if (btnModeHandwrite) btnModeHandwrite.classList.add('active');
      if (btnModeDrag) btnModeDrag.classList.remove('active');
      if (difficultyToggle) difficultyToggle.style.display = 'flex';
    }
    setFocusedBlank(null);
    updateLayoutModeAndDifficulty();
    renderExerciseContent();
  }

  function setDifficulty(diff) {
    currentDifficulty = diff;
    if (btnDiffWithWords && btnDiffWithoutWords) {
      if (diff === 'with_words') {
        btnDiffWithWords.classList.add('active');
        btnDiffWithoutWords.classList.remove('active');
      } else {
        btnDiffWithoutWords.classList.add('active');
        btnDiffWithWords.classList.remove('active');
      }
    }
    updateLayoutModeAndDifficulty();
  }

  function updateLayoutModeAndDifficulty() {
    if (!clozeTrainerBody) return;
    if (currentMode === 'drag') {
      clozeTrainerBody.classList.add('mode-drag');
      clozeTrainerBody.classList.remove('mode-handwrite', 'show-wordbank');
      if (wordbankContainer) {
        wordbankContainer.style.display = 'block';
        const header = wordbankContainer.querySelector('.cloze-wordbank-header span');
        if (header) header.innerHTML = iconText("Kiste", 'Wortspeicher (Wort antippen oder in die Lücke ziehen):');
      }
    } else {
      clozeTrainerBody.classList.add('mode-handwrite');
      clozeTrainerBody.classList.remove('mode-drag');
      if (currentDifficulty === 'with_words') {
        clozeTrainerBody.classList.add('show-wordbank');
        if (wordbankContainer) {
          wordbankContainer.style.display = 'block';
          const header = wordbankContainer.querySelector('.cloze-wordbank-header span');
          if (header) header.innerHTML = iconText("Tipp", 'Wortspeicher zur Orientierung:');
        }
      } else {
        clozeTrainerBody.classList.remove('show-wordbank');
        if (wordbankContainer) {
          wordbankContainer.style.display = 'none';
        }
      }
    }
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
        difficulty: currentAdaptiveDifficulty || 'mittel',
        audio_enabled: true
      };

      const res = await apiFetch('/api/v1/exercises/cloze/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error(`Fehler beim Laden (${res.status})`);
      }

      const data = await res.json();
      currentExercise = data;

      // Sicherstellen, dass content als Objekt vorliegt (falls als JSON-String geliefert)
      if (typeof currentExercise.content === 'string') {
        try {
          currentExercise.content = JSON.parse(currentExercise.content);
        } catch (e) {
          console.warn('Fehler beim Parsen von exercise.content:', e);
        }
      } else if (!currentExercise.content && currentExercise.content_json) {
        try {
          currentExercise.content = typeof currentExercise.content_json === 'string'
            ? JSON.parse(currentExercise.content_json)
            : currentExercise.content_json;
        } catch (e) {}
      }

      if (data.title && modalTitle) modalTitle.textContent = data.title;
      if (data.topic && modalTopic) modalTopic.textContent = data.topic;
      if (data.source_material_title && modalDocSource) {
        modalDocSource.style.display = 'inline-block';
        modalDocSource.innerHTML = iconText("Dokumente", `${data.source_material_title}`);
      }

      // Initialisiere blank states
      const blanks = (currentExercise.content && currentExercise.content.blanks) || [];
      blanks.forEach(b => {
        blankState[b.id] = {
          value: '',
          canvas: null,
          ctx: null,
          lastDraw: 0,
          timer: null,
          evalResult: null,
          dirty: false,
          attempts: 0,
          isAutoRevealed: false,
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
      if (loadingState) loadingState.style.display = 'flex';
      if (exerciseContent) exerciseContent.style.display = 'none';
      if (msg && loadingText) loadingText.textContent = msg;
    } else {
      if (loadingState) loadingState.style.display = 'none';
      if (exerciseContent) exerciseContent.style.display = 'flex';
    }
  }

  /**
   * Rendert die Sätze und Wortkarten
   */
  function renderExerciseContent() {
    if (!currentExercise) return;
    let content = currentExercise.content;
    if (typeof content === 'string') {
      try { content = JSON.parse(content); } catch (e) { content = {}; }
      currentExercise.content = content;
    }
    if (!content) return;

    let sentences = content.sentences || [];
    let blanks = content.blanks || [];
    let wordBank = content.word_bank || [];

    if (sentences.length === 0 && content.text) {
      sentences = [{
        index: 1,
        text: content.text,
        text_with_blanks: content.text,
        blank_ids: blanks.map(b => b.id)
      }];
    }

    if (wordBank.length === 0 && blanks.length > 0) {
      wordBank = blanks.map(b => b.expected_answer || b.correct_answer || '').filter(Boolean);
    }

    wordBank = ensureCompleteWordBank(wordBank, blanks);
    content.word_bank = wordBank;

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

  /**
   * Stellt sicher, dass der Wortspeicher jedes Lösungswort mindestens so oft enthält,
   * wie es in den Lücken des Übungstextes vorkommt (z. B. wenn ein Wort in 2 Lücken gebraucht wird).
   */
  function ensureCompleteWordBank(rawBank, blanksList) {
    const bank = Array.isArray(rawBank) ? [...rawBank] : [];
    const blanks = blanksList || (currentExercise && currentExercise.content && currentExercise.content.blanks) || [];

    const genericPlaceholders = ['fachbegriff', 'begriff', 'wort', 'lücke', 'luecke', 'lösung', 'loesung'];

    const required = {};
    blanks.forEach(b => {
      const ans = (b.expected_answer || b.correct_answer || '').trim();
      if (ans && !genericPlaceholders.includes(ans.toLowerCase())) {
        const lower = ans.toLowerCase();
        if (!required[lower]) {
          required[lower] = { count: 0, text: ans };
        }
        required[lower].count += 1;
      }
    });

    const inBank = {};
    bank.forEach(w => {
      const lower = String(w).trim().toLowerCase();
      inBank[lower] = (inBank[lower] || 0) + 1;
    });

    Object.entries(required).forEach(([lower, info]) => {
      const currentCount = inBank[lower] || 0;
      if (currentCount < info.count) {
        for (let i = 0; i < (info.count - currentCount); i++) {
          bank.push(info.text);
          inBank[lower] = (inBank[lower] || 0) + 1;
        }
      }
    });

    return bank;
  }

  function renderWordBank(wordBank) {
    wordbankChips.innerHTML = '';
    const safeBank = ensureCompleteWordBank(wordBank || []);
    if (currentExercise && currentExercise.content) {
      currentExercise.content.word_bank = safeBank;
    }

    // Zähle, wie oft jedes Wort aktuell in den Lücken eingetragen ist
    const wordUsageInBlanks = {};
    Object.values(blankState).forEach(b => {
      const val = (b.value || '').trim().toLowerCase();
      if (val) {
        wordUsageInBlanks[val] = (wordUsageInBlanks[val] || 0) + 1;
      }
    });

    // Zähle, das wievielte Mal dieses Wort im Wortspeicher auftaucht
    const occurrenceTracker = {};

    safeBank.forEach((word, chipIdx) => {
      const chip = document.createElement('div');
      chip.className = 'cloze-word-chip';
      chip.textContent = word;
      chip.dataset.word = word;
      chip.dataset.chipIndex = chipIdx;

      const lower = String(word).trim().toLowerCase();
      const currentOccurrence = (occurrenceTracker[lower] || 0) + 1;
      occurrenceTracker[lower] = currentOccurrence;

      const timesUsed = wordUsageInBlanks[lower] || 0;
      // Dieser Chip gilt nur dann als verwendet, wenn das Wort mindestens so oft
      // in Lücken eingetragen wurde, wie diese Chip-Instanz repräsentiert!
      const isUsed = timesUsed >= currentOccurrence;
      if (isUsed) chip.classList.add('used');

      // 1. HTML5 Drag für Desktop-Maus
      chip.draggable = !isUsed;
      chip.addEventListener('dragstart', (e) => {
        if (chip.classList.contains('used')) return;
        e.dataTransfer.setData('text/plain', word);
        e.dataTransfer.effectAllowed = 'copy';
      });

      // 2. Touch- & Pointer-Drag für iPad / Apple Pencil & Touchscreens
      chip.addEventListener('pointerdown', (e) => {
        if (chip.classList.contains('used')) return;
        if (e.button !== 0 && e.pointerType === 'mouse') return;

        const startX = e.clientX;
        const startY = e.clientY;
        let isDragging = false;
        let ghostEl = null;

        const onPointerMove = (moveEv) => {
          const dist = Math.hypot(moveEv.clientX - startX, moveEv.clientY - startY);
          if (!isDragging && dist > 6) {
            isDragging = true;
            ghostEl = document.createElement('div');
            ghostEl.className = 'cloze-drag-ghost';
            ghostEl.textContent = word;
            document.body.appendChild(ghostEl);
          }

          if (isDragging && ghostEl) {
            ghostEl.style.left = `${moveEv.clientX}px`;
            ghostEl.style.top = `${moveEv.clientY}px`;

            const elUnder = document.elementFromPoint(moveEv.clientX, moveEv.clientY);
            const targetSlot = elUnder ? elUnder.closest('.cloze-blank-drop') : null;

            document.querySelectorAll('.cloze-blank-drop').forEach(slot => {
              if (slot === targetSlot) {
                slot.classList.add('drag-over');
              } else {
                slot.classList.remove('drag-over');
              }
            });
          }
        };

        const onPointerUp = (upEv) => {
          window.removeEventListener('pointermove', onPointerMove);
          window.removeEventListener('pointerup', onPointerUp);
          window.removeEventListener('pointercancel', onPointerUp);

          if (isDragging) {
            if (ghostEl) {
              ghostEl.remove();
              ghostEl = null;
            }

            const elUnder = document.elementFromPoint(upEv.clientX, upEv.clientY);
            const targetSlot = elUnder ? elUnder.closest('.cloze-blank-drop') : null;
            document.querySelectorAll('.cloze-blank-drop').forEach(s => s.classList.remove('drag-over'));

            if (targetSlot) {
              const targetId = parseInt(targetSlot.dataset.blankId, 10);
              fillBlankWithValue(targetId, word);
            }
          } else {
            // Einfacher Tap / Klick: Tap-to-Place!
            if (focusedBlankId) {
              fillBlankWithValue(focusedBlankId, word);
              setFocusedBlank(null);
            } else {
              const firstEmptyId = Object.keys(blankState).find(id => !blankState[id].value);
              if (firstEmptyId) {
                fillBlankWithValue(parseInt(firstEmptyId, 10), word);
              }
            }
          }
        };

        window.addEventListener('pointermove', onPointerMove, { passive: false });
        window.addEventListener('pointerup', onPointerUp);
        window.addEventListener('pointercancel', onPointerUp);
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

      const expWord = (blankDef.expected_answer || blankDef.correct_answer || '');
      const dynWidth = Math.max(180, Math.min(600, 180 + Math.max(0, expWord.length - 5) * 26));
      dropEl.style.minWidth = `${dynWidth}px`;

      if (bState.value) {
        dropEl.textContent = bState.value;
        dropEl.classList.add('is-filled');
      } else {
        dropEl.textContent = '______';
      }

      // Drag Events (Maus)
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

      // Pointerdown: Wenn Thea mit dem Stift (Apple Pencil) auf einen Slot tippt, automatisch auf Stift umschalten!
      dropEl.addEventListener('pointerdown', (e) => {
        if (e.pointerType === 'pen') {
          setMode('handwrite');
        }
      });

      // Klick / Tap auf eine Lücke: Fokussieren oder Leeren
      dropEl.addEventListener('click', (e) => {
        e.stopPropagation();
        if (bState.value) {
          fillBlankWithValue(bId, '');
          setFocusedBlank(bId);
        } else {
          setFocusedBlank(focusedBlankId === bId ? null : bId);
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

      const expWord = (blankDef.expected_answer || blankDef.correct_answer || '');
      // Basisgröße: 220px (für kurze Wörter). Für längere Wörter deutlich breiter skaliert.
      const boxWidth = Math.max(220, Math.min(680, 220 + Math.max(0, expWord.length - 5) * 28));
      const BLEED_X = 26; // Überhang links & rechts über die gestrichelte Kante
      const BLEED_Y = 16; // Überhang oben & unten
      const canvasW = boxWidth + BLEED_X * 2;
      const canvasH = 62 + BLEED_Y * 2;

      canvasWrap.style.width = `${boxWidth}px`;
      canvasWrap.style.height = '62px';

      canvas.style.width = `${canvasW}px`;
      canvas.style.height = `${canvasH}px`;
      canvas.style.left = `-${BLEED_X}px`;
      canvas.style.top = `-${BLEED_Y}px`;

      const clearBtn = document.createElement('button');
      clearBtn.type = 'button';
      clearBtn.className = 'cloze-blank-clear-btn';
      clearBtn.title = 'Lücke löschen';
      clearBtn.innerHTML = icon('Radierer');
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
    blankState[blankId].isAutoRevealed = false;

    if (focusedBlankId === blankId) {
      setFocusedBlank(null);
    }

    const el = document.getElementById(`cloze-blank-slot-${blankId}`);
    if (el) {
      if (word) {
        el.textContent = word;
        el.classList.add('is-filled');
        el.classList.remove('is-wrong', 'is-correct', 'is-auto-revealed');
      } else {
        el.textContent = '______';
        el.classList.remove('is-filled', 'is-wrong', 'is-correct', 'is-auto-revealed');
      }
    }

    // Aktualisiere Wortspeicher Chips
    if (currentExercise && currentExercise.content) {
      renderWordBank(currentExercise.content.word_bank || []);
    }
    updateProgress();
  }

  /**
   * Trägt die richtige Lösung nach 3 Fehlversuchen automatisch ein
   */
  function revealSolutionForBlank(blankId) {
    const b = blankState[blankId];
    if (!b) return;
    const solutionWord = (b.def && (b.def.expected_answer || b.def.correct_answer)) || '';
    b.value = solutionWord;
    b.evalResult = { is_correct: true, recognized_text: solutionWord };
    b.isAutoRevealed = true;

    if (currentMode === 'drag') {
      fillBlankWithValue(blankId, solutionWord);
      b.isAutoRevealed = true;
      const el = document.getElementById(`cloze-blank-slot-${blankId}`);
      if (el) {
        el.classList.add('is-correct', 'is-auto-revealed');
        el.title = 'Automatisch nach 3 Versuchen eingetragen';
      }
    } else {
      if (b.canvas) {
        clearBlankCanvas(blankId);
        b.value = solutionWord;
        b.evalResult = { is_correct: true, recognized_text: solutionWord };
        b.isAutoRevealed = true;
        const wrap = b.canvas.closest('.cloze-blank-canvas-wrap');
        if (wrap) {
          wrap.classList.add('is-correct', 'is-auto-revealed');
          let overlay = wrap.querySelector('.cloze-solution-overlay');
          if (!overlay) {
            overlay = document.createElement('span');
            overlay.className = 'cloze-solution-overlay';
            wrap.appendChild(overlay);
          }
          overlay.textContent = solutionWord;
          overlay.style.display = 'flex';
        }
      }
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
      const width = rect.width || 230;
      const height = rect.height || 58;

      canvas.width = width * dpr;
      canvas.height = height * dpr;

      const ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 3.2;

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
    b.value = '';
    b.isAutoRevealed = false;
    if (b.timer) {
      clearTimeout(b.timer);
      b.timer = null;
    }

    const wrap = b.canvas.closest('.cloze-blank-canvas-wrap');
    if (wrap) {
      wrap.classList.remove('is-correct', 'is-wrong', 'is-auto-revealed');
      const overlay = wrap.querySelector('.cloze-solution-overlay');
      if (overlay) overlay.remove();
    }

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
    if (badge) badge.innerHTML = icon('Sanduhr');

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

      const res = await apiFetch('/api/v1/exercises/cloze/check-single-blank', {
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
        if (data.is_correct) {
          badge.innerHTML = icon('Haken');
          badge.title = `Erkannt: "${data.recognized_text || ''}"`;
        } else if (data.unclear_handwriting) {
          badge.innerHTML = icon('Schreibwerkzeuge');
          badge.title = 'Schrift schwer lesbar – bitte deutlicher schreiben';
        } else {
          badge.textContent = '●';
          badge.title = `Erkannt: "${data.recognized_text || ''}"`;
        }
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
      statusHint.innerHTML = iconText("Luna", 'Alle Lücken gefüllt! Bereit zum Durchgehen.');
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
   * Spielt die Sätze nacheinander ab und stoppt bei Fehlern (ohne das Lösungswort zu verraten!)
   */
  async function playSentenceLoop() {
    if (!isReviewing) return;
    const sentences = currentExercise.content.sentences || [];

    if (reviewSentenceIndex >= sentences.length) {
      // ALLE SÄTZE ERFOLGREICH BEENDET!
      await onAllSentencesCompleted();
      return;
    }

    const currentSentence = sentences[reviewSentenceIndex];
    highlightSentence(reviewSentenceIndex, 'reading');

    // 1. Prüfe, ob die Lücken in diesem Satz korrekt sind
    const blankIds = currentSentence.blank_ids || [];
    let sentenceHasError = false;
    let sentenceHasUnclear = false;
    let failingBlankDef = null;

    for (const bId of blankIds) {
      const bState = blankState[bId];
      const isUnclear = currentMode === 'handwrite' && bState && bState.evalResult && !!bState.evalResult.unclear_handwriting;
      const isCorrect = evaluateBlankCorrectness(bId);

      if (isCorrect) {
        markBlankVisual(bId, true);
      } else if (isUnclear) {
        sentenceHasError = true;
        sentenceHasUnclear = true;
        failingBlankDef = bState ? bState.def : null;
        markBlankVisual(bId, 'unclear');
      } else {
        sentenceHasError = true;
        failingBlankDef = bState ? bState.def : null;
        markBlankVisual(bId, false);
      }
    }

    // WICHTIG: Wenn ein Fehler oder unklare Schrift vorliegt, darf Luna das Lösungs-Audio NICHT abspielen!
    if (sentenceHasError) {
      hasPendingError = true;
      highlightSentence(reviewSentenceIndex, 'error');
      updateReviewButtonState('error');

      // Falls die Schrift unklar/unleserlich war, KEINEN Fehlversuch werten!
      if (sentenceHasUnclear) {
        setLunaSpeaking(true);
        let played = false;
        try {
          const phraseRes = await apiFetch('/api/v1/exercises/phrases/unclear_handwriting');
          if (phraseRes.ok) {
            const pData = await phraseRes.json();
            if (pData.audio_base64) {
              await playAudioFromBase64(pData.audio_base64);
              played = true;
            }
          }
        } catch (e) {}

        if (!played) {
          const speechPrompt = (currentExercise && currentExercise.title && currentExercise.title.toLowerCase().includes("engl"))
            ? "I couldn't quite read your handwriting. Could you please write the word again a bit more clearly?"
            : "Ich konnte deine Handschrift leider nicht ganz entziffern. Schreibst du mir das Wort bitte noch einmal etwas deutlicher auf?";
          await speakLuna(speechPrompt);
        }
        setLunaSpeaking(false);
        setLunaBanner("Handschrift nicht eindeutig lesbar. Bitte schreibe das Wort noch einmal etwas deutlicher!", 'warning');
        return; // Hält hier an, ohne Versuch zu verbrennen!
      }

      // Echtes inhaltlich falsches Wort:
      let maxAttemptsForSentence = 0;
      for (const bId of blankIds) {
        if (!evaluateBlankCorrectness(bId)) {
          const bState = blankState[bId];
          bState.attempts = (bState.attempts || 0) + 1;
          if (bState.attempts > maxAttemptsForSentence) {
            maxAttemptsForSentence = bState.attempts;
          }

          // Nach 3 falschen Versuchen: Lösung automatisch eintragen!
          if (bState.attempts >= 3) {
            revealSolutionForBlank(bId);
          }
        }
      }

      // Prüfen, ob durch automatisches Eintragen jetzt alle Lücken gelöst sind
      const nowAllFixed = blankIds.every(bId => evaluateBlankCorrectness(bId));
      if (nowAllFixed) {
        hasPendingError = false;
        highlightSentence(reviewSentenceIndex, 'reading');
        updateReviewButtonState('playing');
        setLunaBanner('Lösung nach 3 Versuchen eingetragen! Ich lese dir den Satz jetzt komplett vor...', 'speaking');

        // Satz JETZT von vorne vorlesen:
        if (currentSentence.audio_base64) {
          setLunaSpeaking(true);
          await playAudioFromBase64(currentSentence.audio_base64);
          setLunaSpeaking(false);
        } else {
          await sleep(1500);
        }

        if (!isReviewing) return;
        reviewSentenceIndex++;
        playSentenceLoop();
        return;
      }

      // Noch nicht gelöst (< 3 Versuche): Anhalten & interaktive Korrektur ermöglichen
      await playInstantPhrase('error_interjections');
      const hint = failingBlankDef && failingBlankDef.hint ? `Tipp: ${failingBlankDef.hint}` : 'Schau dir diesen Satz noch einmal an!';
      setLunaBanner(`Ups, nicht ganz! (Versuch ${maxAttemptsForSentence}/3) ${hint}`, 'error');
      return; // Vorlesen hält hier an! Lösungswort wurde NICHT verraten.
    }

    // 2. Keine Fehler in diesem Satz -> JETZT Satz-Audio vollständig abspielen
    if (currentSentence.audio_base64) {
      setLunaSpeaking(true);
      await playAudioFromBase64(currentSentence.audio_base64);
      setLunaSpeaking(false);
    } else {
      setLunaSpeaking(true);
      await speakLuna(currentSentence.full_text_solved || currentSentence.text);
      setLunaSpeaking(false);
    }

    if (!isReviewing) return;

    // Nächster Satz
    reviewSentenceIndex++;
    playSentenceLoop();
  }

  function evaluateBlankCorrectness(blankId) {
    const b = blankState[blankId];
    if (!b) return false;
    if (b.isAutoRevealed) return true;

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

  function markBlankVisual(blankId, status) {
    if (currentMode === 'drag') {
      const el = document.getElementById(`cloze-blank-slot-${blankId}`);
      if (el) {
        el.classList.remove('is-correct', 'is-wrong');
        el.classList.add(status === true ? 'is-correct' : 'is-wrong');
      }
    } else {
      const b = blankState[blankId];
      if (b && b.canvas) {
        const wrap = b.canvas.closest('.cloze-blank-canvas-wrap');
        if (wrap) {
          wrap.classList.remove('is-correct', 'is-wrong', 'is-unclear');
          if (status === true) {
            wrap.classList.add('is-correct');
          } else if (status === 'unclear') {
            wrap.classList.add('is-unclear');
          } else {
            wrap.classList.add('is-wrong');
          }
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

    // Prüfen & Fehlversuche hochzählen falls noch falsch
    let allFixed = true;
    let maxAttempts = 0;
    for (const bId of blankIds) {
      const ok = evaluateBlankCorrectness(bId);
      markBlankVisual(bId, ok);
      if (!ok) {
        allFixed = false;
        const bState = blankState[bId];
        bState.attempts = (bState.attempts || 0) + 1;
        if (bState.attempts > maxAttempts) maxAttempts = bState.attempts;
        if (bState.attempts >= 3) {
          revealSolutionForBlank(bId);
        }
      }
    }

    // Nochmal prüfen, ob durch Auto-Reveal jetzt alle erledigt sind
    const nowAllFixed = blankIds.every(bId => evaluateBlankCorrectness(bId));

    if (nowAllFixed) {
      hasPendingError = false;
      highlightSentence(reviewSentenceIndex, 'reading');
      updateReviewButtonState('playing');

      if (allFixed) {
        setLunaBanner('Perfekt korrigiert! Ich lese dir den Satz jetzt nochmal vor...', 'speaking');
      } else {
        setLunaBanner('Lösung eingetragen! Ich lese dir den Satz jetzt komplett vor...', 'speaking');
      }

      // WICHTIG: Den korrigierten Satz JETZT SOFORT OHNE VERZÖGERUNG VON VORNE VORLESEN!
      if (currentSentence.audio_base64) {
        setLunaSpeaking(true);
        await playAudioFromBase64(currentSentence.audio_base64);
        setLunaSpeaking(false);
      } else {
        setLunaSpeaking(true);
        await speakLuna(currentSentence.full_text_solved || currentSentence.text);
        setLunaSpeaking(false);
      }

      if (!isReviewing) return;

      // Danach zum nächsten Satz
      reviewSentenceIndex++;
      playSentenceLoop();
    } else {
      // Immer noch Fehler (< 3 Versuche)
      await playInstantPhrase('error_interjections');
      setLunaBanner(`Noch nicht ganz. Versuch es noch einmal! (${maxAttempts}/3)`, 'error');
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

    // Score erfassen und an Backend übermitteln
    const blankIds = Object.keys(blankState);
    const totalItems = blankIds.length;
    let correctItems = 0;
    let mistakesCount = 0;
    let revealedCount = 0;

    blankIds.forEach(id => {
      const b = blankState[id];
      if (b) {
        if (b.isAutoRevealed) {
          revealedCount++;
        } else if (evaluateBlankCorrectness(id)) {
          correctItems++;
        }
        if (b.attempts > 1) {
          mistakesCount += (b.attempts - 1);
        }
      }
    });

    try {
      const subRes = await apiFetch('/api/v1/exercises/results', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          subject_id: currentSubjectId,
          exercise_type: 'cloze',
          total_items: totalItems,
          correct_items: correctItems,
          mistakes_count: mistakesCount,
          revealed_count: revealedCount,
          difficulty_level: currentAdaptiveDifficulty || 'mittel'
        })
      });

      if (subRes.ok) {
        const scoreData = await subRes.json();
        if (scoreData.adaptive_difficulty) {
          currentAdaptiveDifficulty = scoreData.adaptive_difficulty;
          currentAdaptiveLevelLabel = scoreData.adaptive_level_label;
          if (modalAdaptiveBadge) {
            modalAdaptiveBadge.innerHTML = iconText("Ziel", `${scoreData.adaptive_level_label}`);
            modalAdaptiveBadge.className = `badge-adaptive-level level-${scoreData.adaptive_level_code || 2}`;
          }
        }
        const msg = scoreData.feedback_message || `Klasse! Du hast ${correctItems} von ${totalItems} Lücken gemeistert.`;
        let bannerText = msg;
        if (scoreData.xp_earned) {
          bannerText += ` • +${scoreData.xp_earned} XP`;
        }
        if (scoreData.stars_earned) {
          bannerText += ` • ${scoreData.stars_earned} ${scoreData.stars_earned === 1 ? 'Stern' : 'Sterne'}`;
        }
        if (scoreData.leveled_up && scoreData.level) {
          bannerText = `LEVEL-UP! Du hast ${scoreData.level.title} erreicht! • +${scoreData.xp_earned} XP`;
        }
        setLunaBanner(bannerText, 'info');
        if (btnNext) btnNext.style.display = 'inline-flex';
        window.dispatchEvent(new CustomEvent('gothea:exercise-completed', { detail: scoreData }));
        return;
      }
    } catch (err) {
      console.warn('Fehler beim Übermitteln des Übungsergebnisses:', err);
    }

    setLunaBanner('Fantastisch gelöst! Du hast alle Lücken meisterhaft ausgefüllt.', 'info');
    if (btnNext) btnNext.style.display = 'inline-flex';
  }

  /**
   * Holt sofort eine Audio-Phrase aus dem vorkalkulierten Pool und spielt sie ab
   */
  async function playInstantPhrase(category) {
    try {
      const res = await apiFetch(`/api/v1/exercises/phrases/${category}`);
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
      reviewBtnIcon.innerHTML = icon('Anhalten');
      reviewBtnLabel.textContent = 'Vorlesen anhalten';
    } else if (state === 'error') {
      btnReview.classList.remove('btn-primary');
      btnReview.classList.add('btn-danger');
      reviewBtnIcon.innerHTML = icon('Schreibwerkzeuge');
      reviewBtnLabel.textContent = 'Korrektur prüfen & weiter';
    } else if (state === 'done') {
      btnReview.classList.remove('btn-danger');
      btnReview.classList.add('btn-primary');
      reviewBtnIcon.innerHTML = icon('Feier');
      reviewBtnLabel.textContent = 'Geschafft! Fertig';
    } else {
      btnReview.classList.remove('btn-danger');
      btnReview.classList.add('btn-primary');
      reviewBtnIcon.innerHTML = icon('Rakete');
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
        audio.playbackRate = 0.90; // Angenehme, ruhigere Sprechgeschwindigkeit
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

  function cleanMathForSpeech(text, isEnglish) {
    if (!text) return '';
    let s = String(text);
    if (isEnglish) {
      s = s.replace(/\\sqrt\{([^{}]+)\}/g, 'square root of $1')
           .replace(/√/g, 'square root of ')
           .replace(/\\cdot|\\times|[·×]/g, ' times ')
           .replace(/\s*=\s*/g, ' equals ');
    } else {
      s = s.replace(/\\sqrt\[3\]\{([^{}]+)\}/g, 'dritte Wurzel aus $1')
           .replace(/\\sqrt\{([^{}]+)\}/g, 'Wurzel aus $1')
           .replace(/\\sqrt\b/g, 'Wurzel')
           .replace(/√\s*([0-9a-zA-Z]+)/g, 'Wurzel aus $1')
           .replace(/√/g, 'Wurzel')
           .replace(/\bsqrt\s*\(([^)]+)\)/gi, 'Wurzel aus $1')
           .replace(/\bsqrt\b/gi, 'Wurzel')
           .replace(/\broot\s+aus\b/gi, 'Wurzel aus')
           .replace(/\broot\b/gi, 'Wurzel')
           .replace(/\\frac\{1\}\{2\}/g, 'ein Halb')
           .replace(/\\frac\{1\}\{4\}/g, 'ein Viertel')
           .replace(/\\frac\{3\}\{4\}/g, 'drei Viertel')
           .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, '$1 geteilt durch $2')
           .replace(/\\cdot|\\times|[·×]/g, ' mal ')
           .replace(/([0-9a-zA-Z])\s*\*\s*([0-9a-zA-Z])/g, '$1 mal $2')
           .replace(/\\div|÷/g, ' geteilt durch ')
           .replace(/(\b\d+)\s*:\s*(\d+\b)/g, '$1 geteilt durch $2')
           .replace(/([0-9a-zA-Z])\s+\/\s+([0-9a-zA-Z])/g, '$1 geteilt durch $2')
           .replace(/\bcm[²2]\b|cm\^2/g, 'Quadratzentimeter')
           .replace(/\bm[²2]\b|m\^2/g, 'Quadratmeter')
           .replace(/\bkm\/h\b/g, 'Kilometer pro Stunde')
           .replace(/\bm\/s\b/g, 'Meter pro Sekunde')
           .replace(/([0-9a-zA-Z])(?:\^2|²)/g, '$1 hoch zwei')
           .replace(/([0-9a-zA-Z])(?:\^3|³)/g, '$1 hoch drei')
           .replace(/\s*=\s*/g, ' ist gleich ')
           .replace(/\\approx|≈/g, ' ungefähr gleich ')
           .replace(/\\neq|≠/g, ' ungleich ');
    }
    s = s.replace(/\$+/g, '').replace(/\\[a-zA-Z]+\{([^{}]+)\}/g, '$1').replace(/\\[a-zA-Z]+/g, '').replace(/\*+/g, '');
    return s.replace(/\s+/g, ' ').trim();
  }

  async function speakLuna(text) {
    if (!text) return;
    stopCurrentAudio();

    const isEnglish = (currentSubjectName && currentSubjectName.toLowerCase().includes('eng')) ||
                      (currentExercise && currentExercise.title && currentExercise.title.toLowerCase().includes('eng'));

    // 1. Primär: Authentische OpenAI Nova Stimme via Backend on-demand anfordern (speed=0.90)
    try {
      const res = await apiFetch('/api/v1/exercises/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text,
          speed: 0.90,
          lang: isEnglish ? 'en' : 'de'
        })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.audio_base64) {
          setLunaSpeaking(true);
          await playAudioFromBase64(data.audio_base64);
          setLunaSpeaking(false);
          return;
        }
      }
    } catch (e) {
      console.warn('Backend TTS nicht verfügbar, nutze Browser-Fallback:', e);
    }

    // 2. Notfall-Fallback bei Offline-Zustand: Browser SpeechSynthesis mit verlangsamter Rate
    return new Promise((resolve) => {
      if (!('speechSynthesis' in window)) {
        setTimeout(resolve, 1200);
        return;
      }
      try {
        window.speechSynthesis.cancel();
        const cleanedText = cleanMathForSpeech(text, isEnglish);
        const utt = new SpeechSynthesisUtterance(cleanedText);
        utt.lang = isEnglish ? 'en-US' : 'de-DE';
        utt.rate = 0.82; // Ruhiger und verständlicher
        utt.onend = () => resolve();
        utt.onerror = () => resolve();
        window.speechSynthesis.speak(utt);
      } catch (e) {
        setTimeout(resolve, 1000);
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
    if ('speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
      } catch (e) {}
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
