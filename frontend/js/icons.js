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
// Die Farben sind für den dunklen Hintergrund abgestimmt und paarweise gut unterscheidbar
// (CIEDE2000 ≥ 17,9 unter Theas Fächern, Kontrast ≥ 3,6:1). Emojis und Farben, die das
// Backend pro Fach mitliefert (icon, color_code), werden bewusst nicht angezeigt.
const SUBJECTS = [
  { match: (n) => n.includes("math"), icon: "Mathematik", color: "#3b82f6" },
  { match: (n) => n.includes("deutsch"), icon: "Deutsch", color: "#f87171" },
  { match: (n) => n.includes("eng"), icon: "Englisch", color: "#fde047" },
  { match: (n) => n.includes("franz") || n.includes("franç"), icon: "Französisch", color: "#8b5cf6" },
  { match: (n) => n.includes("bio"), icon: "Biologie", color: "#16a34a" },
  { match: (n) => n.includes("phys"), icon: "Physik", color: "#f97316" },
  { match: (n) => n.includes("chem"), icon: "Chemie", color: "#67e8f9" },
  { match: (n) => n.includes("gesch"), icon: "Geschichte", color: "#d6b88a" },
  { match: (n) => n.includes("geo"), icon: "Geografie", color: "#14b8a6" },
  { match: (n) => n.includes("politi") || n === "pb", icon: "Politische Bildung", color: "#db2777" },
  { match: (n) => n.includes("wat") || n.includes("wirtsch"), icon: "WAT", color: "#a1a1aa" },
  { match: (n) => n.includes("ler") || n.includes("ethik"), icon: "LER", color: "#a5b4fc" },
  { match: (n) => n.includes("relig"), icon: "Religion", color: "#c4b5fd" },
  { match: (n) => n.includes("mus"), icon: "Musik", color: "#e879f9" },
  { match: (n) => n.includes("sport") || n.includes("*sp"), icon: "Sport", color: "#a3e635" },
  { match: (n) => n.includes("kunst"), icon: "Kunst", color: "#fecdd3" },
  { match: (n) => n.includes("info"), icon: "Informatik", color: "#0ea5e9" },
  { match: (n) => n.includes("orga"), icon: "Bücher", color: "#e2e8f0" },
  { match: (n) => n.includes("mittag") || n.includes("mensa"), icon: "Mittagspause", color: "#94a3b8" },
  { match: (n) => n.includes("pause"), icon: "Pause", color: "#94a3b8" },
  { match: (n) => n.includes("frei"), icon: "Freistunde", color: "#94a3b8" }
];
const SUBJECT_FALLBACK = { icon: "Bücher", color: "#94a3b8" };

function subjectInfo(subjectNameOrCode) {
  const norm = String(subjectNameOrCode || "").toLowerCase().trim();
  return SUBJECTS.find((s) => s.match(norm)) || SUBJECT_FALLBACK;
}

function subjectIconName(subjectNameOrCode) {
  if (!subjectNameOrCode) return "Dokumente";
  return subjectInfo(subjectNameOrCode).icon;
}

function subjectColor(subjectNameOrCode) {
  return subjectInfo(subjectNameOrCode).color;
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
