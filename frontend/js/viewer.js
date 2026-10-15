// ==========================================
// 8. Dokumenten-Viewer (Popup) & Tafel-Verbindung
// ==========================================
let activeViewerMaterial = null;
let currentViewerPage = 1;

const modalMaterialViewer = document.getElementById("modal-material-viewer");
const btnCloseViewerModal = document.getElementById("btn-close-viewer-modal");
const btnViewerOpenWb = document.getElementById("btn-viewer-open-wb");
const btnViewerPrevPage = document.getElementById("btn-viewer-prev-page");
const btnViewerNextPage = document.getElementById("btn-viewer-next-page");
const btnViewerZoomOut = document.getElementById("btn-viewer-zoom-out");
const btnViewerZoomIn = document.getElementById("btn-viewer-zoom-in");
const btnViewerZoomLabel = document.getElementById("viewer-zoom-label");
const btnViewerFitPage = document.getElementById("btn-viewer-fit-page");
const btnViewerFitWidth = document.getElementById("btn-viewer-fit-width");

let currentViewerZoomPercent = 100;

function setViewerZoomPercent(percent) {
  // Maximal 100% (volle Breite), minimal 30% (weit herausgezoomt)
  currentViewerZoomPercent = Math.min(100, Math.max(30, Math.round(percent)));
  const viewerImg = document.getElementById("viewer-img");
  const label = document.getElementById("viewer-zoom-label");
  const btnIn = document.getElementById("btn-viewer-zoom-in");
  const btnOut = document.getElementById("btn-viewer-zoom-out");

  if (viewerImg) {
    viewerImg.classList.remove("viewer-img-fitpage");
    viewerImg.classList.add("viewer-img-fullwidth");
    viewerImg.style.width = `${currentViewerZoomPercent}%`;
    viewerImg.style.maxWidth = "100%";
    viewerImg.style.height = "auto";
  }
  if (label) {
    label.textContent = `${currentViewerZoomPercent}%`;
  }
  if (btnIn) {
    btnIn.disabled = currentViewerZoomPercent >= 100;
  }
  if (btnOut) {
    btnOut.disabled = currentViewerZoomPercent <= 30;
  }
}

function fitViewerToPage() {
  const viewerImg = document.getElementById("viewer-img");
  const container = document.getElementById("viewer-content-container");
  if (!viewerImg || !container) return;

  const availHeight = container.clientHeight - 32;
  const availWidth = container.clientWidth - 32;
  if (availHeight <= 0 || availWidth <= 0) return;

  const natWidth = viewerImg.naturalWidth || 1000;
  const natHeight = viewerImg.naturalHeight || 1414;

  const targetImgWidth = availHeight * (natWidth / natHeight);
  const targetPercent = Math.round((targetImgWidth / availWidth) * 100);

  setViewerZoomPercent(targetPercent);
  container.scrollTop = 0;
}

function openDocumentViewerModal(material) {
  activeViewerMaterial = material;
  currentViewerPage = 1;
  setViewerZoomPercent(100); // Standardmäßig maximal in voller Breite!

  const titleEl = document.getElementById("viewer-doc-title");
  const badgeEl = document.getElementById("viewer-doc-badge");
  const dlBtn = document.getElementById("btn-viewer-download");
  const pagerBar = document.getElementById("viewer-pager-bar");
  const container = document.getElementById("viewer-content-container");

  if (container) container.scrollTop = 0;
  if (titleEl) titleEl.textContent = material.title;
  if (badgeEl) {
    badgeEl.textContent = `${material.subject_name || "Fach"} • ${material.kind || "Material"}${material.topic_name ? " • " + material.topic_name : ""}`;
  }
  if (dlBtn) {
    dlBtn.href = `/api/v1/materials/${material.id}/file`;
  }

  const pageCount = material.page_count || 1;
  if (pagerBar) {
    pagerBar.style.display = pageCount > 1 ? "flex" : "none";
  }

  const reorderBtn = document.getElementById("btn-viewer-reorder-pages");
  if (reorderBtn) {
    const isPdf = (material.mime_type || "").includes("pdf");
    reorderBtn.style.display = (pageCount > 1 || isPdf) ? "flex" : "none";
    reorderBtn.onclick = () => {
      closeDocumentViewerModal();
      openReorderPagesModal(material);
    };
  }

  renderViewerPage();
  if (modalMaterialViewer) modalMaterialViewer.style.display = "flex";
}

function renderViewerPage() {
  if (!activeViewerMaterial) return;
  const pageLabel = document.getElementById("viewer-page-label");
  const viewerImg = document.getElementById("viewer-img");
  const spinner = document.getElementById("viewer-loading-spinner");
  const container = document.getElementById("viewer-content-container");
  const pageCount = activeViewerMaterial.page_count || 1;

  if (container) container.scrollTop = 0;
  if (pageLabel) {
    pageLabel.textContent = `Seite ${currentViewerPage} / ${pageCount}`;
  }
  if (viewerImg) {
    if (spinner) spinner.style.display = "block";
    viewerImg.style.opacity = "0.2";

    viewerImg.onload = () => {
      if (spinner) spinner.style.display = "none";
      viewerImg.style.opacity = "1";
    };
    viewerImg.onerror = () => {
      if (spinner) spinner.style.display = "none";
      viewerImg.style.opacity = "1";
    };

    viewerImg.src = `/api/v1/materials/${activeViewerMaterial.id}/preview?page=${currentViewerPage}`;

    // Nächste Seite im Hintergrund vorladen
    if (currentViewerPage < pageCount) {
      const nextPreload = new Image();
      nextPreload.src = `/api/v1/materials/${activeViewerMaterial.id}/preview?page=${currentViewerPage + 1}`;
    }
  }
}

function closeDocumentViewerModal() {
  if (modalMaterialViewer) modalMaterialViewer.style.display = "none";
  const viewerImg = document.getElementById("viewer-img");
  if (viewerImg) {
    viewerImg.src = "";
    viewerImg.onload = null;
    viewerImg.onerror = null;
  }
  const spinner = document.getElementById("viewer-loading-spinner");
  if (spinner) spinner.style.display = "none";
  activeViewerMaterial = null;
}

function openMaterialInReader(material, page = 1) {
  switchToTab("books");
  const ch = {
    id: material.id,
    title: material.title,
    page_count: material.page_count || 1,
    start_page: material.start_page || 1,
    end_page: material.end_page || material.page_count || 1,
    topic_name: material.topic_name || "Material",
    focus: material.summary || "Dokumentansicht mit handschriftlichen Notizen"
  };
  openChapter(ch, page);
}

if (btnCloseViewerModal) {
  btnCloseViewerModal.addEventListener("click", closeDocumentViewerModal);
}

if (modalMaterialViewer) {
  modalMaterialViewer.addEventListener("click", (e) => {
    if (e.target === modalMaterialViewer) {
      closeDocumentViewerModal();
    }
  });
}

if (btnViewerPrevPage) {
  btnViewerPrevPage.addEventListener("click", () => {
    if (activeViewerMaterial && currentViewerPage > 1) {
      currentViewerPage--;
      renderViewerPage();
    }
  });
}

if (btnViewerNextPage) {
  btnViewerNextPage.addEventListener("click", () => {
    if (activeViewerMaterial && currentViewerPage < (activeViewerMaterial.page_count || 1)) {
      currentViewerPage++;
      renderViewerPage();
    }
  });
}

if (btnViewerOpenWb) {
  btnViewerOpenWb.addEventListener("click", () => {
    if (activeViewerMaterial) {
      const mat = activeViewerMaterial;
      closeDocumentViewerModal();
      openMaterialInReader(mat);
    }
  });
}

if (btnViewerZoomOut) {
  btnViewerZoomOut.addEventListener("click", () => {
    setViewerZoomPercent(currentViewerZoomPercent - 15);
  });
}

if (btnViewerZoomIn) {
  btnViewerZoomIn.addEventListener("click", () => {
    setViewerZoomPercent(currentViewerZoomPercent + 15);
  });
}

if (btnViewerZoomLabel) {
  btnViewerZoomLabel.addEventListener("click", () => {
    setViewerZoomPercent(100);
  });
}

if (btnViewerFitWidth) {
  btnViewerFitWidth.addEventListener("click", () => {
    setViewerZoomPercent(100);
    const container = document.getElementById("viewer-content-container");
    if (container) container.scrollTop = 0;
  });
}

if (btnViewerFitPage) {
  btnViewerFitPage.addEventListener("click", () => {
    fitViewerToPage();
  });
}

// Doppelklick auf Bild wechselt zwischen Ganze Seite und 100% Volle Breite
const viewerImgEl = document.getElementById("viewer-img");
if (viewerImgEl) {
  viewerImgEl.addEventListener("dblclick", () => {
    if (activeViewerMaterial) {
      if (currentViewerZoomPercent >= 90) {
        fitViewerToPage();
      } else {
        setViewerZoomPercent(100);
      }
    }
  });
}

// Mausrad mit Strg/Cmd oder Trackpad-Pinch zum stufenlosen Zoomen
const viewerContainerEl = document.getElementById("viewer-content-container");
if (viewerContainerEl) {
  viewerContainerEl.addEventListener("wheel", (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 5 : -5;
      setViewerZoomPercent(currentViewerZoomPercent + delta);
    }
  }, { passive: false });
}

