# Typ „schriftlich“ – schriftliche Grundrechenarten (Mathe)

Code: `backend/app/services/exercise_types/schriftlich.py` (rechnet Gitter, Schritte, Fehlerbild), Ansicht
`frontend/js/practice_schriftlich.js`. Datei: `backend/app/exercise_sets/schriftlich_mathe.json`.
Rechenwege und Regelsätze nach dem Merkblatt der Eltern „Die schriftlichen Grundrechenarten“ (`mat_7cc9d80e`):
Addition (Übertrag zwischen Aufgabe und Strich), Subtraktion im **Ergänzungsverfahren**, Multiplikation mit der
größten Stelle beginnend (Komma erst am Ende: Nachkommastellen zählen), Division von links nach rechts (Komma im
Ergebnis beim Überschreiten; durch Kommazahl: erst verschieben).

## Stufen

-2 Zuschauen · -1 Antippen (Frage mit drei Antworten je Schritt) · 1 Ergebnis eintragen · 2 Zwischenzeilen,
Überträge, Ergebnis · 3 Aufgabe selbst stellengerecht aufschreiben und rechnen (verschoben erlaubt) · 4 Fehler
finden und verbessern. Ziffern über Zahlentasten, daneben Nebenrechnung mit Stift. Geplant: Stufe 5 komplett
handschriftlich auf der Tafel, Luna liest, der Code rechnet (erst Lesegenauigkeit messen).

## Felder nach dem Kopf

| Feld | Inhalt |
|---|---|
| `verfahren` | `addition`, `subtraktion`, `multiplikation`, `division` |
| `aufgabe` | „34,8 + 2,75“, „73,4 − 2,81“, „2,43 · 1,2“, „5,3405 : 55“ (Addition auch mit mehr Summanden) |
| `ergebnis` | optional: Ergebnis aus der Quelle – die Prüfung vergleicht mit der Rechnung |
| `fehler` | optional für Stufe 4: `uebertrag`, `komma`, `null`, `ziffer` (sonst wählt der Code den typischen) |
| `theas_loesung` | optional: was Thea damals geschrieben hat (nur zur Begutachtung) |

## Stolperfallen

- Höchstens 22 Spalten und 14 Zeilen (sonst passt es nicht auf einen Bildschirm); die Prüfung meldet es.
- Division muss nach höchstens 6 Nachkommastellen aufgehen; zweiter Faktor ohne Ziffer 0 (noch nicht vorgesehen).
- Mehrere Subtrahenden (83,4 − 5,579 − 28,8): in zwei Übungen nacheinander zerlegen.
- Lösung rechnet immer der Code; Zwillinge (B) = gleiche Schwierigkeit (Stellen, Komma, Überträge), andere Zahlen.
