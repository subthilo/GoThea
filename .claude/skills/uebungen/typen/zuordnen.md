# Typ „zuordnen“ – Begriffe an die Ziffern eines Schaubilds (alle Fächer)

Code: `backend/app/services/exercise_types/zuordnen.py`, Ansicht `frontend/js/practice_zuordnen.js`.
Datei: `backend/app/exercise_sets/zuordnen_<fach>.json`, Bilder in `backend/app/exercise_sets/bilder/`.
Beispiel: `ch-brenner` in `zuordnen_chemie.json`.

## Stufen

-1 Anschauen (Ziffer antippen, Begriff erscheint) · 1 Wortbank mit genau den Begriffen · 2 Wortbank mit
Ablenkern. „Im Buch“ zeigt jederzeit den Buchausschnitt. (Selbst schreiben auf der Tafel kommt später.)

## Felder nach dem Kopf

| Feld | Inhalt |
|---|---|
| `bild` | `{datei, original, breite, hoehe}` – von `figure_tool.py export` |
| `felder` | `[{nr, x, y, begriff, auch?}]` – `x`, `y` = Mitte des Ziffernkreises (Anteil 0–1), `begriff` wortgleich wie im Buch, `auch` = weitere gültige Schreibweisen |
| `ablenker` | ≥ 2 plausible Begriffe **aus demselben Kapitel**, die hier nicht passen (Brenner: Gashahn, Leuchtflamme, Drahtnetz, Dreifuß) – nie ein Synonym eines richtigen Begriffs |
| `hilfen` | `{denkanstoss}` – Luna sagt ihn nach dem ersten Fehlversuch |

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

Die Seite wird auf dem Pi gerendert (dort gibt es `pdftoppm`); die Texterkennung ist die von macOS – das Skript
läuft deshalb nur am Mac. Bild-Aufrufe landen im Kostenprotokoll (`data/staging/logs/llm_usage.jsonl` lokal).

## Stolperfallen

- Hat das Buch zu einem Gegenstand keine Abbildung, keine erfinden: Nutzer fragen.
- Genormte Zeichen (z. B. GHS-Piktogramme) nicht nachzeichnen lassen – offizielle Vorlage verwenden (Merkliste).
- Zu viele Ziffern (> 12) machen Liste und Bild eng; dann lieber zwei Übungen.
