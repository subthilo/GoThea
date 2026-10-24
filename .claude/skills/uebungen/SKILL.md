---
name: uebungen
description: Übungs-Session für GoThea – zu einem Fach und Thema aus Theas echten Unterlagen Übungen erstellen, vom Nutzer (Eltern) in der Session begutachten lassen und freigeben. Für alle Fächer und Übungstypen. Aufruf mit Fach und optional Thema, z. B. /uebungen Chemie "Sicherheit im Chemieraum".
argument-hint: <Fach> ["Thema"]
---

# Übungen erstellen und begutachten

Eine Session erstellt Übungen zu **einem Thema** und endet mit freigegebenen Übungen auf Staging. Der Nutzer
(Elternteil) begutachtet in der Session; eine Freigabe in der App gibt es bewusst nicht. An jedem ⏸ anhalten und
auf den Nutzer warten. Deutsch, knapp, Tabellen statt Fließtext.

## Grundsätze (mit dem Nutzer abgestimmt, nicht verhandelbar)

- **Nie frei erdacht.** Jede Übung geht auf eine echte Aufgabe zurück: A Original, B Zwilling (gleiche Struktur,
  andere Zahlen oder anderer Kontext), C umgeformt (gleicher Inhalt, andere Übungsform – z. B. ein Ablauf aus einem
  Fließtext wird zu „Ordnen“). Lösungen aus der Schullösung oder dem Buch; Mathe rechnet der Code nach („Luna liest,
  der Code rechnet“).
  Einzige Ausnahme **„Grundwissen“** (Nutzer, 24.10.): Einmaleins, Mal/Geteilt mit 10/100/1000 und
  Umrechnungszahlen der Einheiten darf der Code erzeugen – geschlossene Menge, vom Code geprüft, keine KI.
- **Wie im Buch.** Begriffe, Schreibweisen und Abbildungen genau wie in Theas Buch. Schaubilder sind die
  Originalabbildung (nachgezeichnet mit `scripts/figure_tool.py`), nie eine nachempfundene Zeichnung – ein
  KI-Brenner mit anderer Bauart und anderen Begriffen hat den Nutzer verwirrt.
- **Theas Fehler zuerst.** Bearbeitete Arbeitsheftseiten, Tests und Arbeiten zeigen, wo es hakt. Mitschriften
  sind keine Quelle, zeigen aber, was dran war.
- **Entwurf, bis der Nutzer „passt“ sagt.** Entwürfe sieht nur der Eltern-Modus; Probeklicks werden nicht gespeichert.
- **Alles auf einen Bildschirm**, quer und hoch, ohne Scrollen (Übungstypen sind so gebaut; neue Typen auch).
- Lieber 3–6 gute Übungen pro Session als viele.

## Ablauf

### 1. Bestand

Ohne Thema zuerst die Themen des Fachs zeigen und ⏸ wählen lassen:

```bash
PI=$(scripts/pi_host.sh)
ssh pi@$PI 'cd ~/GoThea-staging && .venv/bin/python scripts/exercise_sources.py <Fach>'
ssh pi@$PI 'cd ~/GoThea-staging && .venv/bin/python scripts/exercise_sources.py <Fach> "<Thema>"'
ssh pi@$PI 'cd ~/GoThea-staging && .venv/bin/python scripts/exercise_sources.py text <material_id> <seite>[-<bis>]'
```

Das liefert Buchabschnitte mit Seiten, Seiten mit Theas Handschrift, ihre Unterlagen zum Thema und vorhandene
Übungen, jeweils mit den IDs für den Kopf. Die Seitentexte der Quellen lesen. Wo Abbildungen oder Handschrift
zählen, das Seitenbild ansehen:
`curl -s -o <scratchpad>/seite.png "http://$PI:8001/api/v1/materials/<material_id>/preview?page=<n>"` (dann Read;
nicht ins Repo legen).
Seiten sind immer Seiten **in der Datei** (bei Buchkapiteln im Kapitel-PDF); die gedruckte Buchseite steht dabei.
Die Skripte müssen auf Staging aktuell sein (sonst erst `./deploy.sh`).

### 2. Plan ⏸

Tabelle zum Abstimmen, eine Zeile je geplanter Übung:

| # | Quelle (Material, S., Nr.) | Aufgabe kurz | Typ | A/B/C | Anforderung I/II/III | Bild | Warum (z. B. Theas Fehler) |

- Typen und ihre Datenformate: `typen/<typ>.md` in diesem Ordner (vorhanden: `sachaufgabe`, `zuordnen`, `ordnen`, `schubladen`, `schriftlich`).
  Liste der Typen: `backend/app/services/exercise_types/__init__.py`.
- Passt kein Typ: in `merkliste.md` eintragen und dem Nutzer einen neuen Typ vorschlagen – **nicht in dieser
  Session bauen**; neue Typen entstehen in einem eigenen Schritt nach `neuer-typ.md`.
- Vorhandene Übungen nicht doppeln; Zwillinge eher dort, wo Thea Fehler gemacht hat.
- Erst nach dem OK des Nutzers weiter.

### 3. Erstellen

Je Übung den Steckbrief des Typs lesen. Datei: die vorhandene des Typs fürs Fach weiterführen (Mathe-Sachaufgaben:
`sachaufgabe_pilot.json`, Chemie-Zuordnen: `zuordnen_chemie.json`), sonst neu `backend/app/exercise_sets/<typ>_<fach>.json`
mit `typ`, `version`, `stand`, `hinweis` und `uebungen`. Kopf jeder Übung:

```jsonc
{
  "id": "ch-laborgeraete",              // <Präfix>-<Stichwort>, Zwillinge -z1, -z2 (Präfix siehe unten)
  "ableitung": "A",                     // nur B zusätzlich: "zwilling_von": "<id des Originals>"
  "fach": "sub_chemie",
  "thema": "top_dfbb0dd9",
  "status": "entwurf",
  "quelle": {"art": "Arbeitsheft", "material": "<Buchtitel bzw. Dokumenttitel>", "material_id": "mat_…",
             "material_seite": 1, "seite": 1, "nummer": "1"},
  "nachschlagen": {"material": "<Buchtitel>", "material_id": "mat_…", "material_seite": 19, "seite": 196,
                   "stelle": "Einfache Laborgeräte"},
  "abschnitt": "<Buchabschnitt, gruppiert die Liste>",
  "aufgabentext": "<Wortlaut der Quelle, höchstens gekürzt>"
}
```

- `material` ist bei Buchkapiteln der **Buchtitel**, sonst der Dokumenttitel (die Prüfung vergleicht ihn).
- **Ableitung:** A und C stehen als eigene Zeile in Theas Liste, B hängt am Original (gleicher Typ, Original muss
  vorher oder zugleich freigegeben werden). C nennt in `quelle` die Originalaufgabe und darf einen anderen Typ haben
  als eine A-Übung derselben Quelle; ein C kann eigene Zwillinge (B) bekommen.
- **ID-Präfix:** wie die übrigen Übungen der Datei (Mathe-Sachaufgaben `sa-`, Chemie `ch-`); neues Fach → kurzes
  Kürzel (`bio-`, `ph-`, `geo-` …). IDs nie umbenennen: Versuche und Übungstafeln hängen an ihnen.

Bilder (Typ `zuordnen`): `scripts/figure_tool.py` (Ablauf im Steckbrief). Jedes erzeugte Bild selbst ansehen und
mit dem Original vergleichen, auch wenn die automatische Prüfung bestanden hat.

Prüfen, bevor der Nutzer etwas sieht:

```bash
.venv/bin/pytest -q tests/unit/test_practice_exercises.py   # Kopf, IDs, Zwillinge, Regeln des Typs; alle Übungen inkl. Entwürfe
.venv/bin/ruff check
```

### 4. Begutachten ⏸

1. Ganze Testsuite (Exit-Code von pytest prüfen), Commit `feat(exercises): …` (Status Entwurf), `./deploy.sh`
   (normaler Deploy: Übungsdaten liegen im Backend und werden beim Start geladen; `-f` reicht nicht).
2. Auf dem Pi gegen die Datenbank prüfen – 0 Fehler nötig:
   `ssh pi@$PI 'cd ~/GoThea-staging && .venv/bin/python scripts/check_exercises.py'`
3. Dem Nutzer sagen: Staging auf dem iPad, **Eltern-Modus einschalten**, Tab „Üben“, Entwürfe mit gestricheltem
   Rahmen; welche Übungen neu sind; worauf achten (Bild/Begriffe, Lösungsweg, Ablenker, Bedienung mit Pencil).
   Ehrlich sagen, was nur im Browser getestet ist.
4. Rückmeldungen sofort umsetzen, erneut prüfen und einspielen, bis der Nutzer „passt“ sagt – je Übung.

### 5. Freigeben

Für jede abgesegnete Übung `"status": "freigegeben"` und `"freigegeben_am": "<JJJJ-MM-TT>"` setzen (ohne Datum
scheitern die Tests). Tests → Commit
`feat(exercises): release …` → `./deploy.sh` → `check_exercises.py`. Produktion nur auf ausdrückliches OK des
Nutzers – und erst nach der Datenübernahme Staging → Produktion (vorher fehlen dort die Materialien und IDs).

### 6. Abschluss

- `merkliste.md` aktualisieren (neue Wünsche, Erledigtes streichen).
- In CLAUDE.md unter „Stand & nächste Schritte“ knapp festhalten, welche Themen jetzt Übungen haben.
- Kurze Zusammenfassung an den Nutzer: was freigegeben ist, was offen bleibt.
