# Typ „ordnen“ – Schritte in die richtige Reihenfolge (alle Fächer)

Code: `backend/app/services/exercise_types/ordnen.py`, Ansicht `frontend/js/practice_ordnen.js`.
Datei: `backend/app/exercise_sets/ordnen_<fach>.json`, Buchausschnitt in `backend/app/exercise_sets/bilder/`.
Beispiel: `ch-brenner-entzuenden` in `ordnen_chemie.json`.

Passt für: Anleitungen und Abläufe (Brenner, Methoden-Arbeitsschritte), zeitliche Folgen (Entwicklung,
Ereignisse), Ketten (Nahrungskette), Kreisläufe (`kreis: true`), Dialoge. Zeitleisten mit Jahreszahlen: nicht
hier (später eigener Typ).

## Stufen

-1 Anschauen (Plätze antippen, der Schritt erscheint) · 1 ordnen, erster Schritt (ab 5 Schritten auch der letzte)
steht schon · 2 alle Schritte · 3 dazu Ablenker, die liegen bleiben müssen. Keine Tafel; der Browser prüft.
„Im Buch“ zeigt den Buchausschnitt (`buch`). Geplant: Stufe 4 – Nummern mit dem Stift schreiben (Ziffernerkennung).

## Felder nach dem Kopf

| Feld | Inhalt |
|---|---|
| `titel` | Überschrift des Ablaufs wie im Buch |
| `schritte` | Schritte in richtiger Reihenfolge, Wortlaut des Buchs (≥ 3) |
| `ablenker` | ≥ 1 Schritt **aus derselben Quelle**, der nicht in diesen Ablauf gehört (Brenner entzünden: „Schließe den Gashahn am Tisch.“ aus „Löschen“) |
| `kreis` | optional `true`: Kreislauf, Anfang egal |
| `buch` | optional: Bild des Buchausschnitts (`figure_tool.py buch <name> …`, dann als `<id>_buch.jpg` ablegen) |
| `hilfen` | `{denkanstoss}` – nach dem ersten Fehlversuch |

## Stolperfallen

- Steht im Buch nur Fließtext, ist die Übung eine C-Übung: `quelle` nennt die Aufgabe, aus der sie umgeformt ist.
- Mehr als 10 Schritte: erst den Ein-Bildschirm-Test laufen lassen, sonst teilen.
- Gleichwertige Schritte (Reihenfolge egal) kann der Typ noch nicht – solche Abläufe vorerst meiden.
