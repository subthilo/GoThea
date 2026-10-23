# Neuen Übungstyp anlegen (eigener Schritt, nicht mitten in einer Übungs-Session)

Anlass: Eine Aufgabe auf der `merkliste.md` passt in keinen vorhandenen Typ.

## 1. Konzept mit dem Nutzer ⏸

Kurz vorschlagen und abstimmen, bevor Code entsteht:

- **Was Thea tut**, an einer echten Aufgabe gezeigt (am besten einer mit Theas Fehler).
- **Stufen nach der Schreib-Treppe:** antippen/ziehen → Stift als Werkzeug → einzelne Zeichen → Satz mit Anfang
  → frei. Die leichteste Stufe ohne Schreiben; eine Stufe „Anschauen/Nachlesen“, wo es passt.
- **Wer prüft:** möglichst der Code (eindeutige Antworten). Luna nur zum Lesen von Handschrift oder für Sprache
  nach festem Bewertungsmaßstab; gelesene Werte immer zeigen.
- **Ein Bildschirm, quer und hoch, ohne Scrollen**; Icons statt Text, Fachfarbe aus `js/icons.js`.
- **Hilfen:** Denkanstoß, Nachschlagen im Buch (Seite aus `nachschlagen`), Lösung zeigen erst nach Fehlversuchen.

Ein Bild der geplanten Ansicht (Mockup) hilft bei der Abstimmung.

## 2. Bauen – Checkliste

- [ ] `backend/app/services/exercise_types/<typ>.py`: `TYP`, `STAGES`, `BOARD_STAGES`, `validate(ex)`,
      `prepare(ex)`, `summary(ex)`; in `exercise_types/__init__.py` eintragen. Gemeinsames in `common.py`.
- [ ] `frontend/js/practice_<typ>.js`: `registerPracticeType("<typ>", { stages, open(ex, stage, core), close(), rowNote?, sheet? })`;
      in `index.html` nach `practice.js` laden. Feste Seite: `core.setZen(true)`.
      Versuche: `startPracticeAttempt(ex.id, stage)`, Ereignisse mit `logPracticeEvent(attempt, "check" | "hint" | "solution", data)`
      – `check` braucht `status` (`richtig` / `noch_nicht`); daraus entstehen Einsatz-XP und Wiederholen.
- [ ] Stile als eigener Abschnitt in `frontend/css/practice.css` (Tippflächen ≥ 44 px).
- [ ] Tafel-Stufen nur mit eigener Prüfung (`services/practice_check_<typ>.py`, Vorlage `practice_check_zuordnen.py`;
      Sachaufgabe: `practice_check.py`), in `BOARD_CHECKS` in `routers/practice.py` eintragen; das Tafelblatt
      meldet die Ansicht als `sheet: { prepare, render }` an (Vorlage `practice_zuordnen.js`).
- [ ] Tests: Unit (`validate` findet kaputte Daten), Browser-Test zum Durchspielen und der Ein-Bildschirm-Test
      (iPad Pro 11 und mini, quer und hoch; Vorlage `tests/e2e/test_practice_zuordnen.py`).
- [ ] Steckbrief `typen/<typ>.md` für die Sessions; CLAUDE.md (Architektur/Stand) ergänzen.
- [ ] Eine erste Übung als Entwurf, dann wie in einer Session begutachten lassen.
- [ ] Eigene Commits (Typ, Übung, Doku), Staging, Nutzer prüft auf dem iPad.
