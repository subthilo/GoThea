// Höhe der (sticky) Kopfzeile für darunter klebende Leisten bereitstellen
(function trackHeaderHeight() {
  const header = document.querySelector(".header");
  if (!header || typeof ResizeObserver === "undefined") return;
  new ResizeObserver(() => {
    document.documentElement.style.setProperty("--app-header-height", `${header.offsetHeight}px`);
  }).observe(header);
})();

// Vollbild-Modi (fixierte Seite ohne Scrollen) gelten nur für Stundenplan und Tafel.
// Jede Ansicht, die einen Tab aktiviert, muss diese Funktion aufrufen.
function applyTabViewModes(tabName) {
  const modes = { timetable: "timetable-zen-mode", whiteboard: "whiteboard-zen-mode" };
  Object.entries(modes).forEach(([tab, cls]) => {
    const on = tabName === tab;
    document.documentElement.classList.toggle(cls, on);
    document.body.classList.toggle(cls, on);
  });
}

// Tab Navigation
document.querySelectorAll(".nav-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));

    btn.classList.add("active");
    const target = document.getElementById(`tab-${btn.dataset.tab}`);
    if (target) target.classList.add("active");

    const readerView = document.getElementById("book-reader-view");
    if (btn.dataset.tab !== "books" || !readerView || readerView.style.display === "none") {
      document.body.classList.remove("reader-zen-mode");
    }

    if (btn.dataset.tab === "uploads") {
      checkInboxStatus();
      loadUploadsHistory();
    }
    applyTabViewModes(btn.dataset.tab);
    if (btn.dataset.tab === "timetable") {
      loadTimetable();
    }
    if (btn.dataset.tab === "whiteboard") {
      window.dispatchEvent(new Event("resize"));
    }
    if (btn.dataset.tab === "books") {
      // Immer neu laden (neue Uploads, fertige Segmentierungen), aber einen offenen Reader nicht stören
      if (!document.body.classList.contains("reader-zen-mode")) {
        loadBooks();
      }
      setTimeout(syncBookAnnotationCanvasSize, 100);
    }
  });
});

