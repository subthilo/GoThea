# 02.6 Sokratischer KI-Tutor & Audio-Streaming

## 1. Sokratischer Prompt-Governor

Die Leitphilosophie von GoThea ist: **Keine fertigen Lösungen vorgeben, sondern durch gezielte Fragen zum eigenen Denken anregen.**

### Pädagogische Kernregeln
1. **Lösungsverbot:** Die KI gibt niemals das finale Ergebnis oder den nächsten Zwischenschritt direkt vor.
2. **Positives Feedback zuerst:** Immer zuerst würdigen, welcher Teil des Lösungswegs bereits stimmt.
3. **Konkreter Whiteboard-Bezug:** Die Frage verweist auf die visuelle Stelle auf der Tafel (z. B. *„Schau dir in der 2. Zeile links das Vorzeichen vor der Klammer an“*).
4. **Altersstufen-Sprache:**
   * Klasse 1–4: Bildhaft, spielerisch, 1–2 kurze Sätze.
   * Klasse 5–9: Klare Leitfragen, exakte mathematische Fachbegriffe der Sekundarstufe I.
   * Klasse 10–13: Wissenschaftspropädeutisch, Beweisführung, Quellendiskussion.

---

## 2. Audio-Pipeline (Streaming TTS & Barge-In)

* **Streaming Text-to-Speech:** Antworten werden in kurzen Audio-Chunks (Opus / WebM) via WebSocket zum iPad gestreamt.
* **Web Audio API:** Unterbrechungsfreie, latenzarme Wiedergabe direkt im Browser.
* **Barge-In (Unterbrechungserkennung):** Setzt der Schüler den Apple Pencil an oder fängt an zu sprechen, stoppt die Audioausgabe der KI sofort (`user_interrupt`), damit der Schüler ungestört denken und schreiben kann.

---

## 3. Die Interaktive Whiteboard-Schleife (Sense → Diagnose → Guide)

Die Interaktion zwischen Schüler und KI findet direkt auf der gemeinsamen Arbeitsfläche statt:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. SENSE (Handschrift & Tafelzustand)                                   │
│ - Schüler schreibt mit Apple Pencil auf leerer Tafel oder Arbeitsblatt │
│ - Snapshot-Extraktion bei Schreibpausen (Debounce) oder "Hilf mir"     │
├────────────────────────────────────────────────────────────────────────┤
│ 2. DIAGNOSE (Schritt-für-Schritt Fehleranalyse)                        │
│ - Vision-LLM liest den Rechen- oder Denkansatz Zeile für Zeile        │
│ - Identifiziert den ersten logischen Fehler oder unklaren Term         │
├────────────────────────────────────────────────────────────────────────┤
│ 3. GUIDE (Sokratisches Scaffolding auf dem Overlay)                    │
│ - Ebene 3 (#wb-overlay): Gelbe/Blaue Markierungsbox um den Term        │
│ - Audio / Text: Sanfte Leitfrage (z. B. Vorzeichen oder Formelbezug)   │
│ - Schüler korrigiert selbstständig mit dem Stift auf Ebene 2 (#canvas) │
└────────────────────────────────────────────────────────────────────────┘
```

### Gestufte Hilfestellungs-Hierarchie (Scaffolding):
Um Frustration zu vermeiden und gleichzeitig maximales Eigenlernen zu fördern, reagiert die KI in 3 gestuften Phasen:
1. **Impuls 1 (Orientierung):** Weist auf den Fehlerort hin, ohne den Fehler zu benennen (*„Schau dir in der 2. Zeile links den Term vor dem Gleichheitszeichen an.“*).
2. **Impuls 2 (Konzept & Regel):** Erinnert an die mathematische/fachliche Regel (*„Welche Regel gilt für das Minuszeichen vor einer Klammer?“*).
3. **Impuls 3 (Konkreter Zwischenschritt):** Hilft beim elementaren Teilschritt (*„Berechne zunächst nur $(-2) \cdot (-3)$. Was ergibt das?“*).

---

## 4. Knowledge Tracing & Gezieltes Adressieren von Schwachstellen

Die KI fungiert nicht nur als Soforthelfer auf der Tafel, sondern baut ein kontinuierliches diagnostisches Modell des Lernenden auf:

* **Automatisches Fehler-Profiling (`competency_records`):**
  * Nach jeder Tafel-Sitzung kategorisiert die KI beobachtete Fehlermuster (z. B. *„Vorzeichenfehler bei Distributivgesetz“*, *„Verwechslung Vakuole / Chloroplast“*).
  * Persistierung in der Tabelle `competency_records`:
    * `mastery_score`: Gleitender Kompetenzwert (0.0 bis 1.0) pro Thema.
    * `frequent_errors`: Liste der identifizierten, wiederkehrenden Denkfehler.
* **Gezielte Schwächen-Adressierung im Lernplan:**
  * Die Lernplan-Engine (`planner.py`) prüft die `competency_records`:
    * Themen mit niedrigem `mastery_score` oder akkumulierten `frequent_errors` erhalten vor Prüfungen eine höhere Priorität und zusätzliche Übungsblöcke.
    * Das System generiert bzw. wählt Übungsaufgaben aus den hinterlegten Schulbüchern und OER-Materialien, die exakt diese Schwachstelle isoliert trainieren.
* **Erfolgstracking:**
  * Sobald der Schüler ähnliche Aufgaben fehlerfrei auf dem Whiteboard meistert, aktualisiert die KI den `mastery_score` nach oben.
