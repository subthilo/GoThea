// ====================================================================
// Notizen-Anzeige & Whiteboard-Handoff im Dokument-/Buch-Reader
// ====================================================================
let bookAnnotationCanvas = null;
let bookAnnotationCtx = null;
let bookAnnotationStrokes = [];
let bookAnnotationLoadedKey = null;
let currentBookAnnotationMaterialId = null;
let currentBookAnnotationPage = null;

function initBookInking() {
  bookAnnotationCanvas = document.getElementById("book-annotation-canvas");
  if (!bookAnnotationCanvas) return;
  bookAnnotationCtx = bookAnnotationCanvas.getContext("2d");

  // Button: Seite auf der interaktiven Tafel öffnen & mit Stift beschreiben
  const btnEditOnWb = document.getElementById("btn-edit-page-on-whiteboard");
  if (btnEditOnWb) {
    btnEditOnWb.addEventListener("click", () => {
      if (!activeChapter) return;
      if (typeof window.openBookPageOnWhiteboard === "function") {
        window.openBookPageOnWhiteboard({
          materialId: activeChapter.id,
          page: currentChapterPage,
          pageCount: activeChapter.page_count,
          title: (activeChapter.chapter_number ? ("Einheit " + activeChapter.chapter_number + ": ") : "") + activeChapter.title,
          subjectId: activeBookDetail ? activeBookDetail.subject_id : null
        });
      }
    });
  }

  // Zwei-Finger-Wischen zum Umblättern auf dem iPad (ohne Canvas-Blockaden)
  const wrapper = document.getElementById("book-page-canvas-wrapper");
  let touchStartX = null;
  let touchStartY = null;
  let pageFlipped = false;

  if (wrapper) {
    wrapper.addEventListener("touchstart", (e) => {
      if (e.touches.length === 2) {
        touchStartX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
        touchStartY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        pageFlipped = false;
      } else {
        touchStartX = null;
        touchStartY = null;
      }
    }, { passive: true });

    wrapper.addEventListener("touchmove", (e) => {
      if (e.touches.length === 2 && touchStartX !== null && touchStartY !== null) {
        const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
        const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        const dx = midX - touchStartX;
        const dy = midY - touchStartY;

        if (!pageFlipped && Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.3) {
          pageFlipped = true;
          flipBookPage(dx < 0 ? 1 : -1);
        }
      }
    }, { passive: true });

    wrapper.addEventListener("touchend", () => {
      touchStartX = null;
      touchStartY = null;
      pageFlipped = false;
    }, { passive: true });
  }

  window.addEventListener("resize", () => {
    syncBookAnnotationCanvasSize();
  });
}

// Rückkehr-Funktion von der Tafel zum Buch
window.returnToBookReader = function(targetPage) {
  switchToTab("books");
  if (activeChapter) {
    openChapter(activeChapter, targetPage || currentChapterPage);
  }
};

function syncBookAnnotationCanvasSize() {
  const imgEl = document.getElementById("book-page-img");
  const canvas = document.getElementById("book-annotation-canvas");
  if (!imgEl || !canvas) return;

  const w = imgEl.clientWidth;
  const h = imgEl.clientHeight;
  if (w === 0 || h === 0) return;

  const dpr = window.devicePixelRatio || 1;
  const targetPixelW = Math.round(w * dpr);
  const targetPixelH = Math.round(h * dpr);

  canvas.style.left = `${imgEl.offsetLeft}px`;
  canvas.style.top = `${imgEl.offsetTop}px`;

  if (canvas.width !== targetPixelW || canvas.height !== targetPixelH) {
    canvas.width = targetPixelW;
    canvas.height = targetPixelH;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    const ctx = bookAnnotationCtx || canvas.getContext("2d");
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  redrawBookAnnotations();
}

function redrawBookAnnotations() {
  const canvas = document.getElementById("book-annotation-canvas");
  if (!canvas) return;
  const ctx = bookAnnotationCtx || canvas.getContext("2d");
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const cssW = canvas.clientWidth || (canvas.width / dpr);
  const cssH = canvas.clientHeight || (canvas.height / dpr);
  if (cssW === 0 || cssH === 0) return;

  for (const stroke of bookAnnotationStrokes) {
    if (!stroke.points || stroke.points.length === 0) continue;

    if (stroke.tool === "highlighter") {
      ctx.globalAlpha = 0.38;
      ctx.globalCompositeOperation = "multiply";
      ctx.strokeStyle = stroke.color || "#facc15";
      ctx.lineWidth = stroke.width || 22;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      if (stroke.points.length === 1) {
        const pt = stroke.points[0];
        ctx.beginPath();
        ctx.arc(pt.x * cssW, pt.y * cssH, (stroke.width || 22) / 2, 0, Math.PI * 2);
        ctx.fillStyle = stroke.color || "#facc15";
        ctx.fill();
      } else if (stroke.points.length === 2) {
        ctx.beginPath();
        ctx.moveTo(stroke.points[0].x * cssW, stroke.points[0].y * cssH);
        ctx.lineTo(stroke.points[1].x * cssW, stroke.points[1].y * cssH);
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.moveTo(stroke.points[0].x * cssW, stroke.points[0].y * cssH);
        for (let i = 1; i < stroke.points.length - 1; i++) {
          const p1 = stroke.points[i];
          const p2 = stroke.points[i + 1];
          const midX = (p1.x + p2.x) * 0.5 * cssW;
          const midY = (p1.y + p2.y) * 0.5 * cssH;
          ctx.quadraticCurveTo(p1.x * cssW, p1.y * cssH, midX, midY);
        }
        const last = stroke.points[stroke.points.length - 1];
        ctx.lineTo(last.x * cssW, last.y * cssH);
        ctx.stroke();
      }
    } else {
      ctx.globalAlpha = 1.0;
      ctx.globalCompositeOperation = "source-over";
      ctx.strokeStyle = stroke.color || "#2563eb";
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      const baseWidth = stroke.width || 2.6;
      ctx.lineWidth = baseWidth;
      if (stroke.points.length === 1) {
        const pt = stroke.points[0];
        const r = Math.max(0.5, baseWidth / 2);
        ctx.fillStyle = stroke.color || "#2563eb";
        ctx.beginPath();
        ctx.arc(pt.x * cssW, pt.y * cssH, r, 0, Math.PI * 2);
        ctx.fill();
      } else if (stroke.points.length === 2) {
        ctx.beginPath();
        ctx.moveTo(stroke.points[0].x * cssW, stroke.points[0].y * cssH);
        ctx.lineTo(stroke.points[1].x * cssW, stroke.points[1].y * cssH);
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.moveTo(stroke.points[0].x * cssW, stroke.points[0].y * cssH);
        for (let i = 1; i < stroke.points.length - 1; i++) {
          const p1 = stroke.points[i];
          const p2 = stroke.points[i + 1];
          const midX = (p1.x + p2.x) * 0.5 * cssW;
          const midY = (p1.y + p2.y) * 0.5 * cssH;
          ctx.quadraticCurveTo(p1.x * cssW, p1.y * cssH, midX, midY);
        }
        const last = stroke.points[stroke.points.length - 1];
        ctx.lineTo(last.x * cssW, last.y * cssH);
        ctx.stroke();
      }
    }
  }
}


async function loadBookAnnotations(materialId, pageNum) {
  currentBookAnnotationMaterialId = materialId;
  currentBookAnnotationPage = pageNum;

  bookAnnotationStrokes = [];
  redrawBookAnnotations();

  const key = `${materialId}_${pageNum}`;
  bookAnnotationLoadedKey = key;

  try {
    const res = await apiFetch(`/api/v1/materials/${materialId}/pages/${pageNum}/annotations`);
    if (res.ok) {
      const data = await res.json();
      if (bookAnnotationLoadedKey === key) {
        let loaded = [];
        if (Array.isArray(data.strokes) && data.strokes.length > 0) {
          loaded = data.strokes;
        } else if (data.strokes_json) {
          try {
            loaded = JSON.parse(data.strokes_json) || [];
          } catch (e) {
            loaded = [];
          }
        }
        bookAnnotationStrokes = loaded;
        redrawBookAnnotations();
      }
    } else {
      console.warn("Laden der Annotationen HTTP Status:", res.status);
    }
  } catch (err) {
    console.error("Fehler beim Laden der Notizen:", err);
  }
}

