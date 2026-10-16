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

function icon(name, extraClass = "") {
  const cls = extraClass ? ` ${extraClass}` : "";
  return `<span class="ui-icon i-${iconSlug(name)}${cls}" aria-hidden="true"></span>`;
}

// Icon + Text als HTML (Text wird maskiert) – für Statusmeldungen und Beschriftungen
function iconText(name, text) {
  return `${icon(name)} ${escapeHtml(text)}`;
}

function iconUrl(name) {
  return `/static/Icons/${name}.svg`;
}

// Fach (Name oder Kürzel) → Icon-Name. Die Emojis, die das Backend als Fach-Icon
// mitliefert, werden bewusst nicht angezeigt.
function subjectIconName(subjectNameOrCode) {
  if (!subjectNameOrCode) return "Dokumente";
  const norm = String(subjectNameOrCode).toLowerCase().trim();
  if (norm.includes("math")) return "Mathematik";
  if (norm.includes("deutsch")) return "Deutsch";
  if (norm.includes("eng")) return "Englisch";
  if (norm.includes("franz") || norm.includes("franç")) return "Französisch";
  if (norm.includes("bio")) return "Biologie";
  if (norm.includes("phys")) return "Physik";
  if (norm.includes("chem")) return "Chemie";
  if (norm.includes("gesch")) return "Geschichte";
  if (norm.includes("geo")) return "Geografie";
  if (norm.includes("politi") || norm === "pb") return "Politische Bildung";
  if (norm.includes("wat") || norm.includes("wirtsch")) return "WAT";
  if (norm.includes("ler")) return "LER";
  if (norm.includes("relig")) return "Religion";
  if (norm.includes("mus")) return "Musik";
  if (norm.includes("sport") || norm.includes("*sp")) return "Sport";
  if (norm.includes("kunst")) return "Kunst";
  if (norm.includes("info")) return "Informatik";
  if (norm.includes("mittag") || norm.includes("mensa")) return "Mittagspause";
  if (norm.includes("pause")) return "Pause";
  if (norm.includes("frei")) return "Freistunde";
  return "Bücher";
}

// Dokumentart → Icon-Name
function documentIconName(docKind) {
  if (!docKind) return "Dokumente";
  const norm = String(docKind).toLowerCase().trim();
  if (norm.includes("stundenplan")) return "Stundenplan";
  if (norm.includes("vokabel")) return "Inhaltsverzeichnis";
  if (norm.includes("blatt") || norm.includes("arbeitsblatt")) return "Arbeitsblätter";
  if (norm.includes("heft") || norm.includes("arbeitsheft")) return "Arbeitshefte";
  if (norm.includes("mitschrift") || norm.includes("notiz")) return "Mitschriften";
  if (norm.includes("übung") || norm.includes("uebung")) return "Übungen";
  if (norm.includes("test")) return "Tests";
  if (norm.includes("arbeit") || norm.includes("klausur")) return "Arbeiten";
  if (norm.includes("berichtigung")) return "Berichtigungen";
  if (norm.includes("hausaufgabe")) return "Hausaufgaben";
  if (norm.includes("buch")) return "Bücher";
  return "Dokumente";
}

function getSubjectIconUrl(subjectNameOrCode) {
  return iconUrl(subjectIconName(subjectNameOrCode));
}

function getDocumentIconUrl(docKind) {
  return iconUrl(documentIconName(docKind));
}

function subjectIcon(subjectNameOrCode, extraClass = "") {
  return icon(subjectIconName(subjectNameOrCode), extraClass);
}

// Fach-Icon + Fachname (maskiert)
function subjectLabel(subjectName, fallback = "Fach") {
  return `${subjectIcon(subjectName)} ${escapeHtml(subjectName || fallback)}`;
}
