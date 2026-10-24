# Typ „schubladen“ – Begriffe in Gruppen sortieren (alle Fächer)

Code: `backend/app/services/exercise_types/schubladen.py`, Ansicht `frontend/js/practice_schubladen.js`.
Datei: `backend/app/exercise_sets/schubladen_<fach>.json`. Beispiel: `ch-reinstoffe-gemische` in `schubladen_chemie.json`.

Passt für: Reinstoff/Stoffgemisch, löslich/unlöslich, Leiter/Nichtleiter, Pflanzen-/Tierzelle, Pro/Contra,
Wortarten … Jeder Begriff gehört in genau eine Schublade.

## Stufen

-1 Anschauen (Schublade antippen, ihr Inhalt erscheint) · 1 sortieren, in jeder Schublade liegt schon ein
Beispiel (der erste Begriff der Gruppe) · 2 alles sortieren · 3 Fehler finden: alles liegt schon, zwei Kärtchen
aus verschiedenen Gruppen sind vertauscht (fest je Übung). Keine Tafel; der Browser prüft.

## Felder nach dem Kopf

| Feld | Inhalt |
|---|---|
| `gruppen` | `[{name, begriffe}]` – ≥ 2 Gruppen, zusammen ≥ 4 Begriffe; Namen und Begriffe wortgleich wie in der Aufgabe; der erste Begriff jeder Gruppe ist das Beispiel in Stufe 1 |
| `buch` | optional: Bild des Buchausschnitts (`figure_tool.py buch …`, als `<id>_buch.jpg`) |
| `hilfen` | `{denkanstoss}` – nach dem ersten Fehlversuch |

## Stolperfallen

- Lösung nur aus Buch oder Schullösung. Fehlt sie (Arbeitsheft S. 9/10: Lösungsheft Cornelsen 155590), nicht
  bauen, sondern auf der Merkliste vermerken.
- Begriffe, die in mehrere Gruppen passen (z. B. „Lösung“ im Raster der Stoffgemische), kann der Typ nicht.
- Raster mit Zeilen- und Spaltenköpfen (Arbeitsheft S. 9) gibt es noch nicht – erst bauen, wenn eine Übung mit
  gesicherter Lösung es braucht.
