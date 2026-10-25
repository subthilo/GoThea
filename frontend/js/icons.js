// ==========================================================================
// Icons: einziger Weg zu den Vektorgrafiken in /static/Icons
// --------------------------------------------------------------------------
// icon("Name") liefert ein <span> mit der Grafik als CSS-Maske (css/icons.css,
// erzeugt von scripts/build_icon_css.py). Es übernimmt die Textfarbe, passt
// also zu Hover-, Aktiv- und Farbschema-Farben. Emojis nicht mehr verwenden;
// fehlt ein Icon, ein neues SVG im selben Stil nach frontend/Icons legen.
// ==========================================================================

function iconSlug(name) {
  return String(name)
    .toLowerCase()
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .replace(/ /g, "-");
}

function icon(name, extraClass = "", style = "") {
  const cls = extraClass ? ` ${extraClass}` : "";
  const st = style ? ` style="${style}"` : "";
  return `<span class="ui-icon i-${iconSlug(name)}${cls}"${st} aria-hidden="true"></span>`;
}

// Icon + Text als HTML (Text wird maskiert) – für Statusmeldungen und Beschriftungen
function iconText(name, text) {
  return `${icon(name)} ${escapeHtml(text)}`;
}

// Fächer: Icon und Farbe an einer Stelle (Name oder Kürzel, erste passende Regel gilt).
// color = für dunkle Farbschemen, light = derselbe Farbton dunkler für helle Schemen; beide Sätze
// paarweise gut unterscheidbar (CIEDE2000 ≥ 17,9 unter Theas Fächern) und auf jeder Karte ≥ 3:1. Emojis und Farben, die das
// Backend pro Fach mitliefert (icon, color_code), werden bewusst nicht angezeigt.
const SUBJECTS = [
  { match: (n) => n.includes("math"), icon: "Mathematik", color: "#3b82f6", light: "#1e60d5" },
  { match: (n) => n.includes("deutsch"), icon: "Deutsch", color: "#f87171", light: "#d42b2b" },
  { match: (n) => n.includes("eng"), icon: "Englisch", color: "#fde047", light: "#9c6f00" },
  { match: (n) => n.includes("franz") || n.includes("franç"), icon: "Französisch", color: "#8b5cf6", light: "#5f00ff" },
  { match: (n) => n.includes("bio"), icon: "Biologie", color: "#16a34a", light: "#1e6c2b" },
  { match: (n) => n.includes("phys"), icon: "Physik", color: "#f97316", light: "#d86102" },
  { match: (n) => n.includes("chem"), icon: "Chemie", color: "#67e8f9", light: "#00839c" },
  { match: (n) => n.includes("gesch"), icon: "Geschichte", color: "#d6b88a", light: "#874920" },
  { match: (n) => n.includes("geo"), icon: "Geografie", color: "#14b8a6", light: "#178e79" },
  { match: (n) => n.includes("politi") || n === "pb", icon: "Politische Bildung", color: "#db2777", light: "#9f025e" },
  { match: (n) => n.includes("wat") || n.includes("wirtsch"), icon: "WAT", color: "#a1a1aa", light: "#60666f" },
  { match: (n) => n.includes("ler") || n.includes("ethik"), icon: "LER", color: "#a5b4fc", light: "#2b3a67" },
  { match: (n) => n.includes("relig"), icon: "Religion", color: "#c4b5fd", light: "#7a4f9a" },
  { match: (n) => n.includes("mus"), icon: "Musik", color: "#e879f9", light: "#bb38c0" },
  { match: (n) => n.includes("sport") || n.includes("*sp"), icon: "Sport", color: "#a3e635", light: "#659009" },
  { match: (n) => n.includes("kunst"), icon: "Kunst", color: "#fecdd3", light: "#e0457a" },
  { match: (n) => n.includes("info"), icon: "Informatik", color: "#0ea5e9", light: "#0369a1" },
  { match: (n) => n.includes("orga"), icon: "Bücher", color: "#e2e8f0", light: "#475569" },
  { match: (n) => n.includes("mittag") || n.includes("mensa"), icon: "Mittagspause", color: "#94a3b8", light: "#64748b" },
  { match: (n) => n.includes("pause"), icon: "Pause", color: "#94a3b8", light: "#64748b" },
  { match: (n) => n.includes("frei"), icon: "Freistunde", color: "#94a3b8", light: "#64748b" }
];
const SUBJECT_FALLBACK = { icon: "Bücher", color: "#94a3b8", light: "#64748b" };

function subjectInfo(subjectNameOrCode) {
  const norm = String(subjectNameOrCode || "").toLowerCase().trim();
  return SUBJECTS.find((s) => s.match(norm)) || SUBJECT_FALLBACK;
}

function subjectIconName(subjectNameOrCode) {
  if (!subjectNameOrCode) return "Dokumente";
  return subjectInfo(subjectNameOrCode).icon;
}

// Helles Farbschema aktiv? (theme.js setzt data-theme-kind auf <html>)
function isLightTheme() {
  return document.documentElement.getAttribute("data-theme-kind") === "light";
}

function subjectColor(subjectNameOrCode) {
  const info = subjectInfo(subjectNameOrCode);
  return isLightTheme() ? info.light : info.color;
}

// CSS-Variablen für Elemente, die ein Fach tragen: Farbe, zarte Fläche, Rand
function subjectStyle(subjectNameOrCode) {
  const c = subjectColor(subjectNameOrCode);
  return `--subject-color: ${c}; --subject-tint: ${c}1f; --subject-edge: ${c}59;`;
}

// Dokumentart → Icon-Name (Arten wie in backend/app/services/document_kinds.py;
// "Lösungsheft" setzt die Kapiteltabelle fundamente_mathe_7.json für den Lösungsteil)
const DOCUMENT_KIND_ICONS = {
  Arbeitsblatt: "Arbeitsblätter",
  Mitschrift: "Mitschriften",
  Buch: "Bücher",
  Buchauszug: "Bücher",
  Lösungsheft: "Arbeitshefte",
  Test: "Tests",
  Klassenarbeit: "Arbeiten",
  Vokabelliste: "Inhaltsverzeichnis",
  Stundenplan: "Stundenplan"
};

function documentIconName(docKind) {
  return DOCUMENT_KIND_ICONS[docKind] || "Dokumente";
}

// Fach-Icon in Fachfarbe
function subjectIcon(subjectNameOrCode, extraClass = "") {
  return icon(subjectIconName(subjectNameOrCode), extraClass, `color: ${subjectColor(subjectNameOrCode)}`);
}

// Fach-Icon + Fachname (maskiert)
function subjectLabel(subjectName, fallback = "Fach") {
  return `${subjectIcon(subjectName)} ${escapeHtml(subjectName || fallback)}`;
}
