# 02.10 Didaktisches Score-Tracking & Gamification (`gamification_and_scores`)

## 1. Übersicht & Pädagogische Zielsetzung

GoThea setzt auf ein motivierendes, psychologisch fundiertes **Erfolgs- und Feedback-System** (`score_service.py`):
* **Fokus auf Erfolgserlebnisse:** Der Algorithmus strebt einen kontinuierlichen Wohlfühlbereich von **75 % bis 85 % richtiger Antworten** an. Das Kind erlebt stetigen Fortschritt, ohne durch übermäßige Frustration das Interesse zu verlieren.
* **Dynamische Schwierigkeitsanpassung (Adaptives Lernen):** Das System erkennt selbstständig, ob die Schülerin gerade kämpft oder unterfordert ist, und passt das Niveau vollautomatisch an.
* **Positive Verstärkung:** Vergabe von Erfahrungspunkten (XP), Sternen (1–3 ⭐), Tages-Lernserien (Streaks 🔥) und Level-Aufstiegen.
* **Transparente Fächer- & Methoden-Statistiken:** Übersichtliche Kacheln auf den Fach-Detailseiten zeigen genaue Werte nach Methodentyp (Lückentext, Rechenaufgabe, Diagramm etc.).

---

## 2. Datenmodell: `exercise_scores`

Jede abgeschlossene Übung wird persistent in der SQLite-Datenbank protokolliert:

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | TEXT (PK) | Primärschlüssel (`scr_...`) |
| `user_id` | TEXT (FK) | Schüler-Zuordnung (`usr_thea`) |
| `subject_id` | TEXT (FK) | Schulfach (`sub_math`, `sub_english`, etc.) |
| `exercise_type` | TEXT | Aufgabentyp (`cloze`, `math_problem`, `physics_diagram`, etc.) |
| `difficulty_level` | TEXT | Stufe zum Zeitpunkt der Übung (`leicht`, `mittel`, `schwer`) |
| `total_items` | INTEGER | Gesamtzahl der Aufgaben/Lücken |
| `correct_items` | INTEGER | Auf Anhieb richtig gelöste Aufgaben |
| `mistakes_count` | INTEGER | Anzahl der Fehlversuche |
| `revealed_count` | INTEGER | Aufgedeckte Lücken (nach 3 Fehlern) |
| `accuracy_percent` | FLOAT | Trefferquote in Prozent ($0.0 - 100.0$) |
| `xp_earned` | INTEGER | Erhaltene Erfahrungspunkte |
| `stars_earned` | INTEGER | Erhaltene Sterne (1, 2 oder 3) |
| `time_spent_seconds` | INTEGER | Bearbeitungsdauer in Sekunden |
| `completed_at` | TIMESTAMP | Abschlusszeitpunkt |

---

## 3. Der adaptive Schwierigkeits-Algorithmus

Die Funktion `calculate_adaptive_difficulty(records)` analysiert die Historie der letzten Übungen:

```
┌─────────────────────────────────────────────────────────┐
│              HISTORIE DER LETZTEN ÜBUNGEN               │
└────────────────────────────┬────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│ Akute Schutz-Regel (Letzte):  │ │ 3-Übungen-Trend (Durchschnitt)│
│ • Trefferquote < 60% ODER     │ │ • Durchschnitt < 70%:         │
│ • >= 2 Aufdeckungen (Reveals) │ │   --> Stufe LEICHT            │
│ --> Sofortige Erleichterung   │ │ • Alle >= 85% & 0 Aufdeckung: │
│     (schwer -> mittel -> le.) │ │   --> Stufe SCHWER            │
└───────────────────────────────┘ └───────────────────────────────┘
```

### Stufen-Definitionen:
* **Stufe 1 (Grundwissen & Leicht) 🌱:** Fokus auf Festigung der Grundlagen, mehr Hinweise, vorgegebene Antwortoptionen (Wortbank).
* **Stufe 2 (Mittel – Ausgewogen) 🎯:** Ausgewogener Gymnasial-Standard der 7. Klasse Brandenburg.
* **Stufe 3 (Anspruchsvoll & Vertiefung) 🚀:** Höhere kognitive Transferleistung, reine Freitext- und Stifteingabe ohne Hilfestellung.

---

## 4. Belohnungs- & Level-System

### 1. XP-Berechnung (`calculate_exercise_rewards`)
$$\text{XP} = (\text{Richtige Aufgaben} \times 10) + \text{Genauigkeits-Bonus}$$
* Genauigkeit $\ge 80\,\% \implies +25\text{ Bonus-XP}$ (3 Sterne ⭐⭐⭐)
* Genauigkeit $\ge 50\,\% \implies +15\text{ Bonus-XP}$ (2 Sterne ⭐⭐)
* Genauigkeit $< 50\,\% \implies +10\text{ Bonus-XP}$ (1 Stern ⭐)

### 2. Level-Progression
Die Schülerin steigt durch fleißiges Üben in Stufen auf:
* **Level 1:** *Wissens-Entdeckerin 🌱* ($0 - 250\text{ XP}$)
* **Level 2:** *Rätsel-Meisterin 🔍* ($250 - 600\text{ XP}$)
* **Level 3:** *Gymnasial-Profi 🎯* ($600 - 1.200\text{ XP}$)
* **Level 4:** *Olympia-Denkerin ⚡* ($1.200 - 2.500\text{ XP}$)
* **Level 5:** *GoThea-Meisterin ✨* ($> 2.500\text{ XP}$)

### 3. Tages-Lernserien (Streaks 🔥)
* Ein Streak zählt die lückenlos aufeinanderfolgenden Tage mit mindestens einer absolvierten Lerneinheit (`calculate_streak_days`).
* Der Streak bleibt aktiv, wenn heute oder gestern geübt wurde.

---

## 5. REST-API Schnittstellen

* `POST /api/v1/exercises/scores`: Speichert das Resultat einer abgeschlossenen Übung (`ExerciseScoreCreate`) und gibt die aktualisierte XP-, Level- und Streak-Zusammenfassung zurück.
* `GET /api/v1/exercises/scores/summary`: Liefert globale und fächerspezifische Kennzahlen (Gesamt-XP, Level, Streak, Trefferquote, Methoden-Aufschlüsselung) für das Dashboard und die Fach-Seiten.
