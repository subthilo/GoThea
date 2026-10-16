// ============================================================================
// Theme Manager (Farbschemata & Personalisierung)
// ============================================================================
const THEMES = {
  space: { name: "Weltall" },
  sunset: { name: "Sonnenuntergang" },
  nature: { name: "Zauberwald" },
  candy: { name: "Zauberwelt" }
};

let currentAppTheme = "space";

function applyTheme(themeKey) {
  if (!THEMES[themeKey]) themeKey = "space";
  currentAppTheme = themeKey;
  try {
    localStorage.setItem("gothea_theme", themeKey);
  } catch (e) {}

  document.body.setAttribute("data-theme", themeKey);
  document.documentElement.setAttribute("data-theme", themeKey);

  // Aktive Karte im Profil markieren
  document.querySelectorAll(".theme-card-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.theme === themeKey);
  });
}

function initThemeManager() {
  let saved = "space";
  try {
    saved = localStorage.getItem("gothea_theme") || "space";
  } catch (e) {}
  applyTheme(saved);

  // Clicks in Profile Tab Cards
  document.querySelectorAll(".theme-card-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const th = btn.dataset.theme;
      if (th) applyTheme(th);
    });
  });
}

