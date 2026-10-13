# 02.9 Übungs-Arena & Hintergrund-Vorratsspeicher (`exercise_arena_and_pools`)

## 1. Übersicht & Zielsetzung

Mit der **Übungs-Arena** (`#fullscreen-exercise-arena`) und dem **Hintergrund-Vorratsspeicher** (`ExercisePoolManager`) verfügt GoThea über eine hochperformante, ablenkungsfreie Lernumgebung für das aktive Üben auf dem iPad:

* **Zero-Wait Latenz ($< 10\text{ ms}$):** Wenn die Schülerin auf *„Üben“* oder *„Lückentext“* klickt, muss sie **niemals 5–8 Sekunden** auf einen OpenAI-LLM-Aufruf warten. Die Übung öffnet sich instantan aus einem vorbereiteten Vorrat.
* **Vollflächige, ablenkungsfreie Arena:** Sämtliche Navigationselemente, Menüleisten und störenden Overlays werden ausgeblendet. Der gesamte Bildschirm des iPads wird dem Lerninhalt gewidmet.
* **Duales Eingabekonzept:** Nahtlose Wahl zwischen **Handschrift mit Apple Pencil** (Standard) und **Wortbank (Drag-&-Drop / Tap-Pills)**.
* **Didaktische Fehlerkultur:** Unleserliche Handschrift wird erkannt und führt zu einer freundlichen Bitte um Wiederholung – niemals zu einer ungerechtfertigten Fehlwertung.

---

## 2. Der kontinuierliche Hintergrund-Vorratsspeicher (`exercise_pool_service.py`)

Das Backend hält pro Fach und Aufgabentyp einen kontinuierlich gepflegten Pool von vorab generierten Übungen vor:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   HINTERGRUND-GENERATOR (LIFESPAN)                     │
│               backend/app/services/exercise_pool_service.py            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Ziel-Poolgröße: TARGET_POOL_SIZE = 2 je Fach und Typ    │
       ├─────────────────────────────────────────────────────────┤
       │ • sub_math:    math_problem, math_example, fill_in_...  │
       │ • sub_physics: physics_diagram, formula_derivation      │
       │ • sub_english: fill_in_the_blank, text_question         │
       │ • sub_german:  fill_in_the_blank, text_question         │
       │ • sub_bio:     fill_in_the_blank, text_question         │
       └────────────────────────────┬────────────────────────────┘
                                    │
                 ┌──────────────────┴──────────────────┐
                 ▼                                     ▼
┌──────────────────────────────────┐  ┌──────────────────────────────────┐
│ 1. Didaktischer Aufgaben-Text    │  │ 2. Parallele TTS-Audiosynthese   │
│ - Basierend auf Lehrplan / RAG   │  │ - Phonetisch gereinigte Sätze    │
│ - Lücken, Regeln, Erklärungen    │  │ - Vorgerendertes Base64 MP3      │
└──────────────────────────────────┘  └──────────────────────────────────┘
                 │                                     │
                 └──────────────────┬──────────────────┘
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Persistenter Pool: data/<env>/exercise_pool/pool_*.json │
       └────────────────────────────┬────────────────────────────┘
                                    │
                 ┌──────────────────┴──────────────────┐
                 │ Client klickt auf "Üben"            │
                 ▼                                     ▼
┌──────────────────────────────────┐  ┌──────────────────────────────────┐
│ Sofortige Auslieferung (< 10 ms) │  │ Asynchroner Nachfüll-Trigger     │
│ - Aufgabe & Audio sofort bereit  │  │ - Neuer Eintrag im Hintergrund   │
└──────────────────────────────────┘  └──────────────────────────────────┘
```

### 1. Zero-Wait Bereitstellung & Parallele Audiosynthese
Ein entscheidender Vorteil: Der Worker generiert nicht nur das Aufgaben-JSON, sondern synthetisiert **parallel bereits das hochwertige TTS-Sprachaudio** (mittels der OpenAI Nova-Stimme und phonetischer Formelbereinigung). Beim Öffnen der Arena kann Thea den Satz sofort per Klick auf *„🔊 Satz anhören“* abspielen, ohne dass das System nachladen muss.

### 2. Automatisches Nachfüllen (`_replenish_pool`)
Sobald eine Übung entnommen wird (`get_exercise_from_pool`), sinkt der Vorrat unter `TARGET_POOL_SIZE = 2`. Der Worker startet sofort asynchron im Hintergrund die Generierung eines Ersatzes, basierend auf den aktuell hochgeladenen Materialien des Fachs.

---

## 3. Die Vollbild-Übungs-Arena (`cloze_trainer.js`)

Die Benutzeroberfläche (`#fullscreen-exercise-arena`) wurde speziell für das 11- und 13-Zoll iPad Pro & iPad Air optimiert:

### 1. Dualer Eingabemodus
* **Modus 1: Stift (Handschrift – Standard)**:
  * Jede Lücke besitzt ein eigenes, berührungsempfindliches Canvas-Schreibfeld (`.cloze-blank-canvas`).
  * Die Schülerin schreibt das gesuchte Wort direkt mit dem Apple Pencil hinein.
  * Automatische Palm Rejection und Fineliner-Vektorglättung.
* **Modus 2: Wortbank (Tippen / Drag-&-Drop)**:
  * Unter dem Text werden die Antwort-Wörter als farbige Pillen dargestellt (`.cloze-word-bank`).
  * Durch Antippen oder Ziehen springt das Wort in die aktive Lücke.
  * Ein Klick auf ein eingesetztes Wort entfernt es wieder zurück in die Wortbank.
* **Automatischer Stift-Wechsel**: Berührt der Apple Pencil das iPad-Display, während die Wortbank aktiv ist, schaltet das System sofort automatisch auf den Stift-Modus um.

### 2. Dynamische Lückenskalierung & Überlauf-Bleed
* Lücken passen ihre visuelle Mindestbreite dynamisch an die Länge des Zielworts an:
  $$\text{Breite} = \max(80\text{ px}, \text{Wortlänge} \times 16\text{ px} + 24\text{ px})$$
* **Überlauf-Puffer (Bleed):** Schreibt das Kind über die Lücke hinaus, schneidet das Canvas den Strich nicht hart ab, sondern erfasst handschriftliche Zeichen auch in einer 20-Pixel-Toleranzzone außerhalb der Lücke.

### 3. KI-Handschrifterkennung & Wiederholungsbitte
* Beim Prüfen (`check-blanks`) schneidet das Frontend die Handschrift pro Lücke aus und sendet sie an das Vision-Modell.
* Ist die Schrift unleserlich oder verwischt, antwortet das Backend mit `status: "unclear"`.
* **Didaktisches Verhalten:** Das Feld wird gelb umrandet mit der Meldung *„✍️ Konnte ich leider nicht genau lesen – bitte schreibe es noch einmal etwas deutlicher.“* Die Schülerin verliert dadurch keinen Versuch und wird nicht frustriert.

### 4. Hilfen & Lösungs-Aufdeckung
* **Satz erneut vorlesen:** Liest den Satz mit natürlicher Sprachbetonung vor, ersetzt die Lücke dabei durch ein kurzes Summen (*„Hmpf“* oder Pause), um die Lösung nicht vorwegzunehmen.
* **Auto-Reveal nach 3 Versuchen:** Wurde eine Lücke dreimal falsch ausgefüllt, deckt GoThea die Lösung auf, erklärt die Grammatik- oder Rechenregel und verbucht die Punkte fair.

---

## 4. REST-API Schnittstellen

* `POST /api/v1/exercises/generate`: Ruft eine Übung für das gewünschte Fach und Thema ab (primär aus dem Pool, Fallback auf Live-Generierung).
* `POST /api/v1/exercises/{id}/check-blanks`: Prüft eingesendete Handschrift-Crops oder getippte Wörter aller Lücken.
* `POST /api/v1/exercises/check-single-blank`: Schnelle Einzelprüfung einer einzelnen Lücke für interaktives Sofort-Feedback.
* `POST /api/v1/exercises/tts`: Synthetisiert Audio für Sätze und Erklärungen mit mathematisch-phonetischer Normalisierung.
