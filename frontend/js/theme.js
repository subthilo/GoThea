// ============================================================================
// Farbschema – Thea wählt per Farbtupfer im Profil, ohne PIN.
// Liste und Wahl kommen vom Server (/api/v1/design), die Farben aus css/theme_colors.css
// (erzeugt aus backend/app/design_themes.json). Der Eltern-Modus bleibt neutral (Indigo).
// ============================================================================
const THEME_STORAGE_KEY = "gothea_theme";
const NEUTRAL_THEME = "indigo";
const LEGACY_THEMES = { space: "indigo", sunset: "beere", nature: "gruen", candy: "lila" };

let theaTheme = NEUTRAL_THEME;
let themeChoices = [];

function readStoredTheme() {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    return LEGACY_THEMES[saved] || saved || NEUTRAL_THEME;
  } catch (e) {
    return NEUTRAL_THEME;
  }
}

function storeTheme(themeId) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, themeId);
  } catch (e) {}
}

// Zeigt Theas Schema im Thea-Modus, das neutrale im Eltern-Modus.
function applyThemeForMode() {
  const parent = document.body.classList.contains("parent-mode-active");
  document.documentElement.setAttribute("data-theme", parent ? NEUTRAL_THEME : theaTheme);
  const meta = document.querySelector('meta[name="theme-color"]');
  const bg = getComputedStyle(document.documentElement).getPropertyValue("--bg-primary").trim();
  if (meta && bg) meta.setAttribute("content", bg);
  document.querySelectorAll(".theme-dot").forEach((dot) => {
    dot.setAttribute("aria-pressed", String(dot.dataset.theme === theaTheme));
  });
}

function setTheaTheme(themeId) {
  theaTheme = themeId;
  storeTheme(themeId);
  applyThemeForMode();
}

function renderThemePicker() {
  const box = document.getElementById("theme-dots");
  if (!box) return;
  box.innerHTML = "";
  themeChoices.forEach((t) => {
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "theme-dot";
    dot.dataset.theme = t.id;
    dot.title = t.name;
    dot.setAttribute("aria-label", t.name);
    dot.style.setProperty("--dot-bg", t.bg);
    dot.style.setProperty("--dot-accent", t.accent);
    dot.addEventListener("click", () => chooseTheme(t.id));
    box.appendChild(dot);
  });
  applyThemeForMode();
}

async function chooseTheme(themeId) {
  const before = theaTheme;
  setTheaTheme(themeId);
  try {
    await apiJson("/api/v1/design/theme", { method: "PUT", json: { theme: themeId } });
  } catch (err) {
    console.error("Farbschema nicht gespeichert:", err);
    setTheaTheme(before);
  }
}

async function initThemeManager() {
  // Sofort die zuletzt bekannte Wahl zeigen (kein Aufblitzen), dann den Server fragen.
  setTheaTheme(readStoredTheme());
  const data = await apiJson("/api/v1/design");
  themeChoices = data.themes || [];
  if (themeChoices.some((t) => t.id === data.theme)) setTheaTheme(data.theme);
  renderThemePicker();
}
