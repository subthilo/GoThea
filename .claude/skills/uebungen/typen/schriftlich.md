# Typ „schriftlich“ – schriftliche Grundrechenarten (Mathe)

Code: `backend/app/services/exercise_types/schriftlich.py` (rechnet Gitter, Schritte, Fehlerbild), Ansicht
`frontend/js/practice_schriftlich.js`. Datei: `backend/app/exercise_sets/schriftlich_mathe.json`.
Rechenwege und Regelsätze nach dem Merkblatt der Eltern „Die schriftlichen Grundrechenarten“ (`mat_7cc9d80e`):
Addition (Übertrag zwischen Aufgabe und Strich), Subtraktion im **Ergänzungsverfahren**, Multiplikation mit der
größten Stelle beginnend (Komma erst am Ende: Nachkommastellen zählen), Division von links nach rechts (Komma im
Ergebnis beim Überschreiten; durch Kommazahl: erst verschieben).

Schreibregeln der Eltern (25.10.): jede Ziffer in einem Kästchen; das Komma verschiebt keine Ziffer, es sitzt auf
der senkrechten Linie rechts neben der Einerziffer, unten; der Strich liegt auf der Linie direkt unter der
Zahlenzeile; ein Übertrag steht klein unten rechts im Kästchen der Zahl, zu der er gehört. Kästchen 48 px, das Blatt
scrollt, zoomt nicht. Keine Nebenrechnung – die schriftliche Rechnung ist selbst das, was geübt wird.

## Stufen

-2 Zuschauen · -1 Antippen (Frage mit drei Antworten je Schritt) · 1 Ergebnis eintragen · 2 Zwischenzeilen,
Überträge, Ergebnis · 3 Aufgabe selbst stellengerecht aufschreiben und rechnen (verschoben erlaubt, ohne Striche) ·
4 Fehler finden und verbessern · 5 Tafel: alles frei mit dem Stift auf einem Kästchenblatt, Luna liest, der Code
rechnet (`services/practice_check_schriftlich.py`; Lesegenauigkeit noch ungemessen). Stufen 1–4: Ziffern über
Zahlentasten, Komma-Taste setzt das Komma am gewählten Kästchen, gleiches Kästchen gleich noch einmal antippen =
Übertrag.

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
