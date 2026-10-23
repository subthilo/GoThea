# Typ „sachaufgabe“ – Sachaufgabe mit Lösungsweg (Mathe, auch Physik/Chemie-Rechnungen)

Code: `backend/app/services/exercise_types/sachaufgabe.py` (Prüfung, Bausteine), Ansicht `frontend/js/practice_sachaufgabe.js`,
Tafel-Blatt `frontend/js/practice_sheet.js`, Tafel-Prüfung `backend/app/services/practice_check.py`.
Datei: `backend/app/exercise_sets/sachaufgabe_*.json`. Vollständiges Beispiel: `sa-gummibaerchen` (Dreisatz),
`sa-apfelsaft-flaschen` (Rechnung mit Überschlag), `sa-flugzeug` (mit Begründung).

## Stufen

-1 Gedankengang (Rechenweg als Sätze, Thea ergänzt nur Zahlen) · 0 Bausteine (Werte und Rechenschritte in die
Tabelle ziehen, Antwortsatz wählen) · 1–4 Tafel (Blatt als Unterlage, von „Tabelle vorgegeben“ bis „leeres Blatt
wie im Test“; Luna liest, der Code rechnet).

## Felder nach dem Kopf

| Feld | Inhalt |
|---|---|
| `schema` | `dreisatz_proportional`, `dreisatz_antiproportional` oder `rechnung` |
| `groessen` | Dreisatz: zwei Spalten `[{name, einheit}, …]` |
| `zeilen`, `schritte` | Dreisatz: drei Zeilen `[[x, y], …]`, Rechenschritte links wie `":3"`, `"·10"` (rechts rechnet der Code; antiproportional umgekehrt) |
| `rechnung` | Rechnung: `ausdruck` („2100 : 0,7“), `umformung` („21000 : 7“), `zahlen` |
| `ergebnis` | `{wert, einheit}` |
| `antwort_anfang`, `antwortsatz` | Satzanfang (Stufe 1) und ganzer Satz; die letzte Zahl im Satz muss das Ergebnis sein |
| `gedankengang` | Sätze mit Lücken `[[Wert]]`, optional `tipp`; jede Gleichung im Satz wird nachgerechnet, die letzte Lücke ist das Ergebnis |
| `schaetzfrage` | `frage`, `optionen`, `antwort`, `vergleichswert`, `ergebnis_ist` (`groesser`/`kleiner`), `aktiv` |
| `ueberschlag` | `null` oder `{verlangt, ausdruck, folgerung}` |
| `begruendung` | optional `{verlangt, erwartung, quelle, optionen: [{text, richtig, grund}]}` – genau eine richtig, falsche mit Grund |
| `fehlerbeispiel` | `{wert, fehler}` – typischer falscher Wert (wird Ablenker), nie das Ergebnis |
| `typische_fehler`, `hilfen` | Liste; `{denkanstoss, hinweis}` |
| `theas_loesung`, `einstieg` | bei Testaufgaben: was Thea damals geschrieben hat; optional Lunas erster Satz dazu |

## Stolperfallen

- Zahlen exakt (Brüche): `validate` rechnet jede Zeile, den Antwortsatz und die Schätzfrage nach – die Tests
  scheitern bei jedem Fehler. Geldbeträge mit Komma („1,50“).
- Zwillinge: andere Zahlen **und** stimmige Sachsituation; alle Felder neu rechnen, nicht nur das Ergebnis.
