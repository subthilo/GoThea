# Typ „kurzrechnung“ – Päckchen kurzer Rechnungen (Mathe)

Code: `backend/app/services/exercise_types/kurzrechnung.py`, Ansicht `frontend/js/practice_kurzrechnung.js`.
Datei: `backend/app/exercise_sets/kurzrechnung_mathe.json`. Beispiele: `km-zehnerzahlen-1` (Dezimalzahl, mit
Überschlag), `km-kuerzen-dividieren` (Brüche), `km-messbecher` (Einheiten), `km-einmaleins-check` (Grundwissen).

Passt für: Aufgaben mit einer Zahl oder einem Bruch als Antwort, die man im Kopf oder mit kurzer Nebenrechnung
löst – Komma bei Mal/Geteilt, Zehnerzahlen, Brüche kürzen/dividieren, Bruch ↔ Dezimal, Einheiten umrechnen.
Nicht für mehrschrittige Rechenwege (→ `sachaufgabe`) oder schriftliches Rechnen (→ `schriftlich`).

## Stufen

-1 Antippen (vier Angebote; die falschen erzeugt der Code als typische Fehler: Komma verschoben, ohne Kehrwert,
nicht fertig gekürzt, vertauscht) · 1 erst den Überschlag antippen (Größenordnung), dann eintippen · 2 gleich
eintippen, nach einem Fehler kommt der Überschlag als Hilfe. Keine Tafel; der Browser prüft. Eingabe über
Zahlentasten, daneben Nebenrechnung mit Kästchen (keine Erkennung). Nach zwei Fehlern „Lösung zeigen“.
Stufe 1 nur, wenn mindestens eine Aufgabe einen Überschlag hat (Mal/Geteilt mit Dezimalzahl-Ergebnis);
sonst `"stufen": [-1, 2]`.

## Felder nach dem Kopf

`aufgaben`: höchstens 20, je Aufgabe genau eine Art, immer mit `ergebnis` (der Code rechnet nach):

| Art | Beispiel | geprüft |
|---|---|---|
| Dezimalzahl | `{"rechnung": "3,2 : 8", "ergebnis": "0,4"}` | Wert; Tausender mit Leerzeichen („2 103,976 · 1 000“) |
| Bruch aus Rechnung | `{"rechnung": "11/18 : 22/6", "antwort": "bruch", "ergebnis": "1/6"}` | genau der vollständig gekürzte Bruch |
| Bruch, jeder gleichwertige | `{"vor": "Dividiere durch 3", "zeige": "15/24", "rechnung": "15/24 : 3", "antwort": "bruch", "gekuerzt": false, "ergebnis": "5/24"}` | Wert; gezeigt wird `ergebnis` |
| Kürzen | `{"kuerzen": "15/24", "mit": 3, "ergebnis": "5/8"}` (`mit`: Zahl oder `"vollständig"`) | genau dieser Bruch |
| Einheiten | `{"umrechnen": "3/4 l", "in": "cm³", "ergebnis": "750"}` | Wert; Länge, Fläche, Volumen (ml, l, hl), Masse, Zeit |

Optional je Aufgabe: `nummer` (wie auf dem Blatt), `fehler` (Theas falsche Antwort im Original – muss falsch
sein), `ueberschlag: false`, `vor` (Wort vor der Aufgabe, dann steht „→“ statt „=“), `zeige` (statt der Rechnung).

**Grundwissen** (vom Code erzeugt, Ausnahme vom Grundsatz „nie frei erdacht“): `erzeugt` statt `aufgaben`,
`stufen: [2]`, `quelle: {"material": "Grundwissen", "grundwissen": "Einmaleins", "nummer": "1"}`, Thema
„Grundwissen: Einmaleins und Zehnerzahlen“ (`top_a78913bc`, nur Staging).
- `einmaleins`: alle 36 Aufgaben 2·2 … 9·9 ohne Tauschaufgaben als Check – keine Rückmeldung, Zeit still gemessen.
  Im Eltern-Modus zeigt die Übung vorher die Auswertung: sicher / langsam (mehr als doppelt so lange wie Theas
  Median, mindestens 4 s) / falsch.
- `einmaleins_wacklig` (`aus`: ID des Checks): nur die wackligen Aufgaben des letzten Checks; eine Aufgabe ist
  wieder sicher, sobald sie in einem Versuch auf Anhieb und schnell gelang. Ohne wacklige Aufgaben ausgeblendet.

## Stolperfallen

- Aufgaben immer am Seitenbild prüfen, nicht am erschlossenen Text: bei Brüchen verliest die Erschließung Zahlen
  (15/24 als 15/45), Theas Kürzungen überschreiben die gedruckten Zahlen. Ausmalbilder mit Lösungsfeldern sind
  eine gute Gegenprobe.
- Tests mit Aufgabenblatt: steht auf Theas Blatt nur ihre Antwort (Matheprobe Nr. 1), fehlt die Aufgabe → nicht bauen.
- Lange Blätter in Übungen zu 6–9 Aufgaben teilen (Runde bleibt kurz).
