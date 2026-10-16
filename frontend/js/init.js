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

  safeRun(setupParentModeEvents, "setupParentModeEvents");
  safeRun(initThemeManager, "initThemeManager");
  await safeRun(checkParentAuthStatus, "checkParentAuthStatus");
  await safeRun(checkEnvironment, "checkEnvironment");
  await safeRun(loadGamificationOverview, "loadGamificationOverview");
  await safeRun(loadProfile, "loadProfile");
  await safeRun(loadTaxonomy, "loadTaxonomy");
  await safeRun(loadPlan, "loadPlan");
  await safeRun(loadMaterials, "loadMaterials");
  await safeRun(checkInboxStatus, "checkInboxStatus");
  await safeRun(loadTodayDashboardWidget, "loadTodayDashboardWidget");
  await safeRun(loadTimetable, "loadTimetable");
  await safeRun(loadBooks, "loadBooks");
  safeRun(setupBookBrowserEvents, "setupBookBrowserEvents");
  safeRun(setupSubjectDetailEvents, "setupSubjectDetailEvents");
  safeRun(setupUploadsPageEvents, "setupUploadsPageEvents");
  safeRun(applyInitialZenMode, "applyInitialZenMode");
  safeRun(setupSearchEvents, "setupSearchEvents");
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

