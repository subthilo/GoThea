// 1. Profil laden
async function loadProfile() {
  try {
    const res = await apiFetch("/api/v1/profile");
    if (res.ok) {
      currentProfile = await res.json();
      if (badgeGrade) badgeGrade.textContent = `${currentProfile.grade_level}. Klasse`;
      if (userGreeting) userGreeting.textContent = `Hallo, ${currentProfile.name}! 👋`;
      if (userSubtitle) userSubtitle.textContent = `${currentProfile.grade_level}. Klasse ${currentProfile.school_type} • Land ${currentProfile.federal_state} (Niveaustufe E)`;

      // Profil-Formular initialisieren
      const profNameInput = document.getElementById("prof-name");
      const profGradeInput = document.getElementById("prof-grade");
      const profSchoolInput = document.getElementById("prof-school");
      if (profNameInput) profNameInput.value = currentProfile.name;
      if (profGradeInput) profGradeInput.value = currentProfile.grade_level;
      if (profSchoolInput) profSchoolInput.value = currentProfile.school_type;
    }
  } catch (err) {
    console.error("Fehler beim Laden des Profils:", err);
  }
}

// 2. Fächer und Themen laden
async function loadTaxonomy() {
  try {
    const [subRes, topRes] = await Promise.all([
      apiFetch("/api/v1/taxonomy/subjects"),
      apiFetch("/api/v1/taxonomy/topics")
    ]);

    if (subRes.ok && topRes.ok) {
      currentSubjects = await subRes.json();
      const allTopics = await topRes.json();
      allTopicsCache = allTopics;

      if (statSubjectsCount) statSubjectsCount.textContent = currentSubjects.length;
      if (statTopicsCount) statTopicsCount.textContent = allTopics.length;

      // Group topics by subject
      const topicsBySubject = {};
      allTopics.forEach((t) => {
        if (!topicsBySubject[t.subject_id]) topicsBySubject[t.subject_id] = [];
        topicsBySubject[t.subject_id].push(t);
      });

      renderDashboardSubjects(currentSubjects, topicsBySubject);
      if (currentDetailSubjectId) {
        openSubjectDetail(currentDetailSubjectId);
      }
    }
  } catch (err) {
    console.error("Fehler beim Laden der Fächer:", err);
  }
}

let cachedSubjects = [];
let cachedTopicsMap = {};
let currentDetailSubjectId = null;
let currentSubjectMaterials = [];
let activeSubjectKindFilter = "all";

// ==========================================================================
// Icon Resolver Helpers (Konzept 1: 55 Vektorgrafiken)
// ==========================================================================
function getSubjectIconUrl(subjectNameOrCode) {
  if (!subjectNameOrCode) return "/static/Icons/Dokumente.svg";
  const norm = String(subjectNameOrCode).toLowerCase().trim();
  if (norm.includes("math")) return "/static/Icons/Mathematik.svg";
  if (norm.includes("deutsch")) return "/static/Icons/Deutsch.svg";
  if (norm.includes("eng")) return "/static/Icons/Englisch.svg";
  if (norm.includes("franz") || norm.includes("franç")) return "/static/Icons/Französisch.svg";
  if (norm.includes("bio")) return "/static/Icons/Biologie.svg";
  if (norm.includes("phys")) return "/static/Icons/Physik.svg";
  if (norm.includes("chem")) return "/static/Icons/Chemie.svg";
  if (norm.includes("gesch")) return "/static/Icons/Geschichte.svg";
  if (norm.includes("geo")) return "/static/Icons/Geografie.svg";
  if (norm.includes("politi") || norm === "pb") return "/static/Icons/Politische Bildung.svg";
  if (norm.includes("wat") || norm.includes("wirtsch")) return "/static/Icons/WAT.svg";
  if (norm.includes("ler")) return "/static/Icons/LER.svg";
  if (norm.includes("relig")) return "/static/Icons/Religion.svg";
  if (norm.includes("mus")) return "/static/Icons/Musik.svg";
  if (norm.includes("sport") || norm.includes("*sp")) return "/static/Icons/Sport.svg";
  if (norm.includes("kunst")) return "/static/Icons/Kunst.svg";
  if (norm.includes("info")) return "/static/Icons/Informatik.svg";
  if (norm.includes("mittag") || norm.includes("mensa")) return "/static/Icons/Mittagspause.svg";
  if (norm.includes("pause")) return "/static/Icons/Pause.svg";
  if (norm.includes("frei")) return "/static/Icons/Freistunde.svg";
  return "/static/Icons/Bücher.svg";
}

function getDocumentIconUrl(docKind) {
  if (!docKind) return "/static/Icons/Dokumente.svg";
  const norm = String(docKind).toLowerCase().trim();
  if (norm.includes("vokabel")) return "/static/Icons/Inhaltsverzeichnis.svg";
  if (norm.includes("blatt") || norm.includes("arbeitsblatt")) return "/static/Icons/Arbeitsblätter.svg";
  if (norm.includes("heft") || norm.includes("arbeitsheft")) return "/static/Icons/Arbeitshefte.svg";
  if (norm.includes("mitschrift") || norm.includes("notiz")) return "/static/Icons/Mitschriften.svg";
  if (norm.includes("übung") || norm.includes("uebung")) return "/static/Icons/Übungen.svg";
  if (norm.includes("test")) return "/static/Icons/Tests.svg";
  if (norm.includes("arbeit") || norm.includes("klausur")) return "/static/Icons/Arbeiten.svg";
  if (norm.includes("berichtigung")) return "/static/Icons/Berichtigungen.svg";
  if (norm.includes("hausaufgabe")) return "/static/Icons/Hausaufgaben.svg";
  if (norm.includes("buch")) return "/static/Icons/Bücher.svg";
  return "/static/Icons/Dokumente.svg";
}

