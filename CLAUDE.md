# GoThea – Arbeitsgrundlage für Claude

Lernplattform für Thea (7. Klasse Gymnasium, Brandenburg). Thea nutzt sie im iPad-Safari (Apple Pencil), der Nutzer (Elternteil) administriert im **Eltern-Modus** (PIN). Backend: FastAPI + SQLite auf einem Raspberry Pi 4. Frontend: Vanilla-JS ohne Build. KI: OpenAI (`gpt-6-luna`).

**Kommunikation mit dem Nutzer auf Deutsch.** Code-Kommentare deutsch, Commit-Nachrichten englisch (Conventional Commits, wie in der Historie).

## Arbeitsweise (vereinbart)

- **Nach jedem abgeschlossenen Schritt: Tests → Commit → Deploy.** Commit nur, wenn pytest selbst grün ist – den Exit-Code von pytest prüfen, nicht den von `grep`/`tail`:
  ```bash
  .venv/bin/pytest -q > /tmp/out.txt 2>&1; rc=$?; tail -1 /tmp/out.txt; [ $rc -eq 0 ] && git commit ...
  ```
- Deploy: `./deploy.sh` = **Staging** (Standard; Tests, rsync, Neustart, wartet auf `/api/health`). Zu Thea erst mit `./deploy.sh prod` bzw. `all`, nachdem es auf Staging lief. Reine Frontend-Änderungen: `-f` (ohne Neustart, gilt fürs gewählte Ziel). Kein `git push`, solange nicht ausdrücklich gewünscht.
- Thematisch getrennte Commits; die Commit-Nachricht erklärt das **Warum**.
- Riskante oder unumkehrbare Aktionen auf dem Pi (Daten löschen, Prod anfassen) vorher bestätigen lassen. Neues erst auf **Staging** erproben.
- Größere KI-Umbauten **messen statt raten**: `scripts/eval_document_classification.py` (Soll-Daten liegen außerhalb des Repos).
- Frontend: Syntax-Check ohne Node per `osascript -l JavaScript -e '…new Function(src)…'`; dazu Browser-Smoke-Tests in `tests/e2e/` (Playwright/WebKit, iPad-Querformat, eigener Testserver; schlagen bei JS-Fehlern, Konsolen-Fehlern und API-Fehlern fehl). Einrichtung: `.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m playwright install webkit`. Bedienung mit Pencil/Touch testet weiterhin der Nutzer – das ehrlich sagen.
- Python-Lint: `.venv/bin/ruff check` (nur Pyflakes-Regeln, `ruff.toml`) muss sauber bleiben. Absichtliche Nur-Import-Zeilen mit `# noqa: F401` und Begründung markieren.
- Nach Frontend-Änderungen den Cache-Buster in `index.html` erhöhen (`app.js?v=…`, `style.css?v=…`).

## Umgebungen

| | Port | Code auf dem Pi | Daten | Dienst |
|---|---|---|---|---|
| Produktion | 8000 | `~/GoThea` | `~/GoThea/data/prod/` | `gothea.service` |
| Staging | 8001 | `~/GoThea-staging` (eigene `.venv`) | `~/GoThea/data/staging/` (Pfade in `~/GoThea-staging/.env`) | `gothea-staging.service` |

- Pi: `pi@192.168.1.135`, Logs: `sudo journalctl -u gothea-staging -f`.
- `data/`, `inbox/`, `experiments/` werden beim Deploy nicht synchronisiert. `.env` (API-Key, `OPENAI_MODEL`) liegt nur auf dem Pi bzw. lokal in `experiments/openai_study/.env`.
- `data/shared/` gehört beiden Umgebungen (inhaltsadressierter Cache der Seiten-Erschließung).
- **Hintergrund-Worker:** Seiten-Erschließung und Renderer müssen immer laufen (sie füllen die Datenbank, Grundlage für den Tutor) – `GOTHEA_BACKGROUND_WORKERS` nie dafür abschalten. Der Übungs-Vorrat hat einen eigenen Schalter `GOTHEA_EXERCISE_POOL` (Standard aus, bis Tutor/Übungen neu gebaut sind).
- Backups vor größeren Eingriffen: `~/GoThea-backups/` auf dem Pi.
- Skripte auf dem Pi: Staging `cd ~/GoThea-staging && .venv/bin/python scripts/<name>.py` (die `.env` dort setzt Umgebung und Datenpfade); Produktion `cd ~/GoThea && APP_ENV=production .venv/bin/python scripts/<name>.py`.

## Architektur

- `backend/main.py` – App, Lifespan (Tabellen, Migrationen, Seeder, Hintergrund-Worker).
- `backend/app/config.py` – alle Pfade/Schalter aus der Umgebung. `database.py` – Engine + schlanke Spalten-Migrationen (`ensure_schema_migrations`).
- `backend/app/prompts/` – **alle** KI-Prompts. `services/llm.py: chat_params()` setzt `temperature` nur für Modelle, die es unterstützen (nicht GPT-6/o-Modelle).
- `backend/app/services/` – Fachlogik. Wichtige Dienste:
  - `document_kinds.py` – einzige Quelle der Dokumentarten (inkl. Altnamen-Abbildung).
  - `document_analyzer.py` – Upload-Analyse (Seitenbilder: ≤6 Seiten alle, sonst 3), liefert Art, Fach, Thema, Titel, Signale (Lösungsseiten, auf Papier bearbeitet, von Lehrkraft bewertet).
  - `book_segmentation.py` – Bücher → Kapitel (bekannte Tabellen, PDF-Outline, KI-Inhaltsverzeichnis); pro Buch nur eine Segmentierung gleichzeitig.
  - `page_extraction.py` – **Seiteninhalt-Erschließung** in `material_pages` («S: …» = Theas Handschrift, «L: …» = Lehrkraft). Dokumente sofort, Buchkapitel gedrosselt (`GOTHEA_BOOK_EXTRACTION_INTERVAL`).
  - `topic_catalog.py`, `book_topic_catalog.py`, `topic_consolidation.py`, `topic_plans.py` – Themenkatalog.
  - `page_renderer.py` – Seitenbilder (pdftoppm, Priorität, Cache-Aufräumen).
  - `timetable_slots.py` / `timetable_analyzer.py` – Stundenplan-Import (Untis-Zeilen → Slots).
  - `tutor_service.py` – Tutor „Luna“ (Tafel-Feedback, Übungen, Lückenprüfung, TTS).
- `frontend/` – `index.html`, `app.js` (fast alles), `whiteboard.js`, `cloze_trainer.js`, `style.css`.
- `scripts/` – Pflege-Skripte (Neu-Einordnung, Themenkatalog, Zusammenführung, Klassifizierungs-Messung).

## Fachliche Konzepte (mit dem Nutzer abgestimmt)

- **Dokumentarten:** Arbeitsblatt, Mitschrift (handschriftlich), Buch (auch Arbeitsheft; Kapitel = Buchauszug), **Test = jede von der Lehrkraft bewertete Leistung** (auch Diktat, bewertetes Protokoll), Klassenarbeit, Vokabelliste (Beispielsätze nur aus echten Materialien, mit Quelle), Sonstiges, Stundenplan. Hefte = automatisch geführte Sammlung pro Fach **und Schuljahr** mit Inhaltsverzeichnis und PDF-Export (noch nicht gebaut).
- **Bearbeitungs-Ablauf** (noch nicht gebaut), gemeinsam für Arbeitsblatt, Arbeitsheft-Seiten und Tests: offen → abgegeben (gesperrt) → ausgewertet → besprochen. Viele Blätter sind schon auf Papier ausgefüllt → direkt auswerten. Lösungen bleiben für Thea **serverseitig** verborgen, bis abgegeben ist. Getrennte Ebenen: Original, Theas Antworten, Lösungen, Auswertung, Besprechungsnotizen. **XP:** voll, wenn alle Fehler besprochen sind; anteilig, wenn Thea vorher beendet.
- **Themen:** mittlere Ebene (Unterrichtseinheit) mit **Bereich** darüber (z. B. Mechanik › Hookesches Gesetz). Katalog aus den Inhaltsverzeichnissen der Bücher (`topic_book_refs` = Thema → Kapitel + Seiten); Bio 7/8 gemeinsam. Themen aus Theas Dokumenten nie zusammenlegen, Buchthemen nie umbenennen/zusammenlegen. Bücher/Kapitel tragen kein Thema. Pflege-Skripte: erst Vorschau (wird gespeichert), dann `--apply` wendet **genau** diese an.
- **Tutor braucht vollen Zugriff auf Theas Unterlagen** (harte Anforderung). Grundlage ist die Seiten-Erschließung; Tutor-Anbindung (Seite mitschicken, Werkzeuge: Unterlagen durchsuchen, Lernstand, Tests, frühere Sitzungen) steht noch aus.

## Stolperfallen

- SQLAlchemy-Sessions laufen mit `autoflush=False`: vor Abfragen auf eben hinzugefügte Objekte `db.flush()`.
- Daten, die eine Voranalyse anlegt und ein späterer Request nutzt, müssen **committet** werden (sonst 404 beim Bestätigen).
- Der Seeder legt Start-Themen nur für **neu angelegte** Fächer an (gelöschte Platzhalter kommen nicht zurück).
- **Pencil/Zeichenkern (`whiteboard.js`, auch vom Buch-Leser für Anmerkungen genutzt) ist fragil und mühsam erarbeitet:** darf besser, auf keinen Fall schlechter werden. Nur unverändert verschieben; Änderungen am Schreibverhalten als eigene, einzeln getestete Commits, vom Nutzer auf dem iPad geprüft. Dazu gehören auch die iOS-relevanten CSS-Regeln (`touch-action`, `user-select`, `-webkit-touch-callout`).
- Stundenplan und Tafel nutzen Zen-Modi (fixierte Seite ohne Scrollen). Jede Ansicht, die einen Tab aktiviert, muss `applyTabViewModes()` aufrufen.
- Endpunkte, die Inhalte inkl. Lösungen liefern, bleiben im Eltern-Modus, bis Lösungen serverseitig verborgen werden.
- Tests (`tests/conftest.py`): temporäres `DATA_DIR`/`SHARED_DATA_DIR`, leerer API-Key, keine Hintergrund-Worker, frische In-Memory-DB pro Test. `client` und `strict_client` nie im selben Test (teilen sich die Dependency-Overrides). Suite läuft in ~15 s (davon ~9 s Browser-Tests; ohne Playwright werden sie übersprungen).

## Stand & nächste Schritte

Erledigt (Okt 2026): Dokumentarten + Neu-Einordnung, Themenkatalog aus Büchern, Seiten-Erschließung (läuft auf Staging; Bücher werden über Nacht nachgeholt), Stundenplan-Import, Test-Isolation, Renderer-Aufräumen.

Vereinbarte Reihenfolge:
1. **Aufräumen** (vor neuer Oberfläche): `frontend/app.js` (~5.100 Z.) und `style.css` (~8.200 Z.) in Module aufteilen, Dialoge aus `index.html` lösen; dafür zuerst einen einfachen automatischen Browser-Test (z. B. Playwright) für die Hauptansichten aufsetzen. Kapiteltabellen aus `book_segmentation.py` in Datendateien. README (Testanzahl, Modellnamen) aktualisieren.
2. **Arbeitsblatt-Ablauf** komplett (siehe Konzepte), danach Arbeitsheft-Seiten, Tests & Arbeiten (inkl. Stärken/Schwächen), Mitschriften, Hefte mit PDF-Export, Vokabellisten.
3. **Tutor** an die Seiten-Erschließung anbinden (voller Materialzugriff).
4. Übernahme Staging → Produktion per Skript mit Sicherung (Erschließungen werden über `data/shared/` ohnehin wiederverwendet).

**Tutor & Übungen werden neu gedacht** (eigene Session, „muss sauber sein und Spaß machen“). Der bisherige Code (`tutor_service.py`, Übungs-/Phrasen-Pool, Übungslogik in den Routern) ist ein früher Schnellschuss: beim Aufräumen einfrieren, nicht polieren. Das Aufräumen schafft stattdessen die Basis (zentrale KI-Schicht, modulares Frontend) und endet mit einer Bestandsaufnahme als Startpunkt.

Bekannte offene Punkte: Tutor-WebSocket `/ws/tutor/…` ist eine Attrappe (`/ws` dagegen speist die Online-Anzeige); „Städte den Ländern zuordnen“ steht in Mathe, Fach unklar.
