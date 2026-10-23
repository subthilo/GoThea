# Typ „zuordnen“ – Begriffe an die Ziffern eines Schaubilds (alle Fächer)

Code: `backend/app/services/exercise_types/zuordnen.py`, Ansicht und Tafelblatt `frontend/js/practice_zuordnen.js`,
Tafel-Prüfung `backend/app/services/practice_check_zuordnen.py`.
Datei: `backend/app/exercise_sets/zuordnen_<fach>.json`, Bilder in `backend/app/exercise_sets/bilder/`.
Beispiele in `zuordnen_chemie.json`: `ch-brenner` (nachgezeichnet), `ch-laborgeraete-1` (Original mit Ziffern), `ch-grundregeln` (Regeln als Karten, ohne Stufe 3).

## Stufen

-1 Anschauen (Ziffer antippen, Begriff erscheint) · 1 Wortbank mit genau den Begriffen · 2 Wortbank mit
Ablenkern · 3 Tafel: Blatt mit Schaubild und Schreiblinien „1 ___“, Thea schreibt die Begriffe selbst; Luna liest
ab, der Code vergleicht (Groß-/Kleinschreibung egal; ab 6 Buchstaben zählt ein Buchstabe daneben noch, mit Hinweis
auf die Schreibweise). „Im Buch“ zeigt in den Stufen im Tab jederzeit den Buchausschnitt.

## Felder nach dem Kopf

| Feld | Inhalt |
|---|---|
| `bild` | `{datei, original, breite, hoehe}` – von `figure_tool.py export` |
| `felder` | `[{nr, x, y, begriff, auch?}]` – `x`, `y` = Mitte des Ziffernkreises (Anteil 0–1), `begriff` wortgleich wie im Buch, `auch` = weitere gültige Schreibweisen |
| `ablenker` | ≥ 2 plausible Begriffe **aus demselben Kapitel**, die hier nicht passen (Brenner: Gashahn, Leuchtflamme, Drahtnetz, Dreifuß) – nie ein Synonym eines richtigen Begriffs |
| `hilfen` | `{denkanstoss}` – Luna sagt ihn nach dem ersten Fehlversuch |
| `stufen` | optional, Teilmenge von −1, 1, 2, 3 – z. B. `[-1, 1, 2]`, wenn die Begriffe ganze Sätze sind (Stufe 3 vergleicht buchstabengenau) |

## Bild erstellen (am Mac)

```bash
# 1. Ausschnitt der Buchseite (Seite in der Datei, Rechteck in Prozent: links,oben,rechts,unten)
.venv/bin/python scripts/figure_tool.py prepare <name> --material <material_id> --seite <n> --ausschnitt 11,60.5,52.5,88
#    → data/figures/<name>/original.png ansehen (Read), Ausschnitt ggf. anpassen und wiederholen
# 2. data/figures/<name>/key.json bereinigen: "beschreibung" (was die Abbildung zeigt), je Ziffer
#    "original" = Beschriftung genau wie im Bild (für den Zeichenauftrag), "begriff" = was Thea zuordnen soll
#    (ohne Temperaturen o. Ä., wenn die nicht gefragt sind). Die Texterkennung trennt manchmal Zeilen einer
#    Beschriftung („Außenkegel“ / „(bis 1200 °C)“) – zusammenführen.
# 3. Nachzeichnen + Prüfung (Vision-Modell + Pixeltest), bis zu 3 Versuche, ~60 s je Versuch
.venv/bin/python scripts/figure_tool.py redraw <name>
#    → versuch_N.png SELBST ansehen und Ziffer für Ziffer mit original.png vergleichen; versuch_N.json lesen
# 4. Ablegen; gibt bild + felder als JSON aus
.venv/bin/python scripts/figure_tool.py export <name> <N> <übungs-id>
```

**Abbildung ohne Beschriftungen** (Arbeitsheft-Zeichnungen mit leeren Linien, z. B. `ch-laborgeraete-1`): nicht
nachzeichnen lassen, sondern den Original-Ausschnitt nehmen. Nach `prepare` in key.json je Ziffer `x`, `y` (Pixel in
original.png, Kreis neben das Gerät) und `begriff` eintragen; Schreiblinien vorher aus original.png schneiden (Reihen
zusammenrücken, `Image.paste`). Dann:

```bash
.venv/bin/python scripts/figure_tool.py mark <name> --weiss 210      # hellt den Scan auf (durchscheinende Rückseite), setzt Kreise
.venv/bin/python scripts/figure_tool.py buch <name> --material <mat> --seite <n> --ausschnitt …   # Lösungsstelle für „Im Buch“
.venv/bin/python scripts/figure_tool.py export <name> 1 <übungs-id>
```

Die Seite wird auf dem Pi gerendert (dort gibt es `pdftoppm`); die Texterkennung ist die von macOS – das Skript
läuft deshalb nur am Mac. Bild-Aufrufe landen im Kostenprotokoll (`data/staging/logs/llm_usage.jsonl` lokal).

## Stolperfallen

- Hat das Buch zu einem Gegenstand keine Abbildung, keine erfinden: Nutzer fragen.
- Genormte Zeichen (z. B. GHS-Piktogramme) nicht nachzeichnen lassen – offizielle Vorlage verwenden (Merkliste).
- Zu viele Ziffern (> 12) machen Liste, Bild und Tafelblatt eng (Zeilen dort 40–56 px); dann lieber zwei Übungen.
- `auch`: gängige gleichwertige Schreibweisen, die die Lehrkraft gelten lässt – sonst zählt nur der Buchbegriff.
