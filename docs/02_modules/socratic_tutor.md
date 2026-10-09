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
