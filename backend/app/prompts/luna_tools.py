"""Beschreibungen der Werkzeuge, die Luna (KI) während einer Antwort aufrufen kann."""

SEARCH_TOOL_DESCRIPTION = """Durchsucht Theas Unterlagen: ihre Mitschriften, Arbeitsblätter, Tests, Klassenarbeiten,
Vokabellisten und die Seiten ihrer Schulbücher und Arbeitshefte (auch deren Inhaltsverzeichnis).
Nutze das Werkzeug, bevor du etwas aus dem Unterricht erklärst, damit du dich auf das beziehst, was Thea
wirklich gelernt hat, und die Fundstelle nennen kannst (z. B. „steht in deinem Mathebuch auf S. 84“).

Die Suche ist eine reine Wortsuche (keine Bedeutungssuche): Suche mit 1–3 kennzeichnenden Fachbegriffen,
so wie sie im Heft oder Buch stehen („Dreisatz“, „Hookesches Gesetz“, „passé composé“), nicht mit ganzen
Fragen. Findet sie nichts, versuche andere Wörter (Synonym, Oberbegriff, andere Sprache) oder lass die
Filter weg. Im Ausschnitt stehen die gefundenen Wörter zwischen ⟦ und ⟧; «S: …» ist Theas Handschrift,
«L: …» die der Lehrkraft. Lösungen sind nicht enthalten."""

SEARCH_QUERY_DESCRIPTION = "1–3 Suchwörter, z. B. 'Dreisatz' oder 'Hookesches Gesetz'"
SEARCH_SUBJECT_DESCRIPTION = "Nur in diesem Fach suchen (weglassen, wenn unklar)"
SEARCH_KIND_DESCRIPTION = "Nur diese Art von Unterlagen (Buchauszug = Seiten aus Schulbüchern und Arbeitsheften)"

# Nur für scripts/try_llm_tools.py – der echte Tutor-Prompt entsteht mit dem Tutor-Umbau
PROBE_SYSTEM_PROMPT = """Du bist Luna, Lernbegleiterin von Thea (7. Klasse Gymnasium, Brandenburg).
Antworte auf Deutsch, kurz und freundlich. Schau zuerst in Theas Unterlagen nach und nenne die Fundstellen,
auf die du dich stützt. Steht nichts in den Unterlagen, sag das ehrlich."""
