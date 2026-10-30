// Init
async function initApp() {
  document.body.classList.remove("reader-zen-mode");
  document.body.classList.remove("timetable-zen-mode");
  document.documentElement.classList.remove("timetable-zen-mode");
  document.body.classList.remove("whiteboard-zen-mode");
  document.documentElement.classList.remove("whiteboard-zen-mode");
  const safeRun = async (fn, name) => {
    try {
      await fn();
    } catch (err) {
      console.error(`Init error in ${name}:`, err);
    }
  };

  // Knöpfe sofort verdrahten (brauchen keine Daten) – sonst reagiert die Seite erst nach dem Laden
  safeRun(setupParentModeEvents, "setupParentModeEvents");
  safeRun(initThemeManager, "initThemeManager");
  safeRun(setupBookBrowserEvents, "setupBookBrowserEvents");
  safeRun(setupSubjectDetailEvents, "setupSubjectDetailEvents");
  safeRun(setupUploadsPageEvents, "setupUploadsPageEvents");
  safeRun(applyInitialZenMode, "applyInitialZenMode");
  safeRun(setupSearchEvents, "setupSearchEvents");

  // Daten gleichzeitig holen statt nacheinander (jede Anfrage kostet auf dem iPad einen WLAN-Weg).
  // Lernplan und Materialliste zeigen Fachnamen und hängen deshalb an den Fächern.
  const taxonomy = safeRun(loadTaxonomy, "loadTaxonomy");
  await Promise.all([
    safeRun(checkParentAuthStatus, "checkParentAuthStatus"),
    safeRun(checkEnvironment, "checkEnvironment"),
    safeRun(loadGamificationOverview, "loadGamificationOverview"),
    safeRun(loadProfile, "loadProfile"),
    safeRun(checkInboxStatus, "checkInboxStatus"),
    safeRun(loadTodayDashboardWidget, "loadTodayDashboardWidget"),
    safeRun(loadTimetable, "loadTimetable"),
    safeRun(loadBooks, "loadBooks"),
    taxonomy.then(() => Promise.all([
      safeRun(loadPlan, "loadPlan"),
      safeRun(loadMaterials, "loadMaterials"),
    ])),
  ]);
  safeRun(connectWebSocket, "connectWebSocket");
}

function applyInitialZenMode() {
  const initialTab = document.querySelector(".nav-tab.active");
  if (initialTab && initialTab.dataset.tab === "whiteboard") {
    document.documentElement.classList.add("whiteboard-zen-mode");
    document.body.classList.add("whiteboard-zen-mode");
  } else if (initialTab && initialTab.dataset.tab === "timetable") {
    document.documentElement.classList.add("timetable-zen-mode");
    document.body.classList.add("timetable-zen-mode");
  }
}

initApp();

