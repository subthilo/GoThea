// 1. Profil laden
async function loadProfile() {
  try {
    const res = await apiFetch("/api/v1/profile");
    if (res.ok) {
      currentProfile = await res.json();
      if (badgeGrade) badgeGrade.textContent = `${currentProfile.grade_level}. Klasse`;
      if (userGreeting) userGreeting.innerHTML = `${escapeHtml(`Hallo, ${currentProfile.name}!`)} ${icon("Hand")}`;
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

