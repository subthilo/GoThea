// ============================================================================
// Theme Manager (Farbschemata & Personalisierung)
// ============================================================================
const THEMES = {
  space: { name: "Weltall", icon: "🚀" },
  sunset: { name: "Sonnenuntergang", icon: "🌅" },
  nature: { name: "Zauberwald", icon: "🌲" },
  candy: { name: "Zauberwelt", icon: "🦄" }
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

  // Header pill aktualisieren
  const pillIcon = document.getElementById("theme-pill-icon");
  const pillText = document.getElementById("theme-pill-text");
  if (pillIcon) pillIcon.textContent = THEMES[themeKey].icon;
  if (pillText) pillText.textContent = THEMES[themeKey].name;

  // Active state in Dropdown & Profil
  document.querySelectorAll(".theme-opt-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.theme === themeKey);
  });
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

  const toggleBtn = document.getElementById("btn-theme-toggle");
  const dropdown = document.getElementById("theme-dropdown-menu");

  if (toggleBtn && dropdown) {
    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isVisible = dropdown.style.display === "flex";
      dropdown.style.display = isVisible ? "none" : "flex";
    });

    document.addEventListener("click", (e) => {
      if (!toggleBtn.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.style.display = "none";
      }
    });
  }

  // Clicks in Header Dropdown
  document.querySelectorAll(".theme-opt-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const th = btn.dataset.theme;
      if (th) {
        applyTheme(th);
        if (dropdown) dropdown.style.display = "none";
      }
    });
  });

  // Clicks in Profile Tab Cards
  document.querySelectorAll(".theme-card-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const th = btn.dataset.theme;
      if (th) applyTheme(th);
    });
  });
}

