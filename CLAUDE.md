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
- Cache-Buster: `index.html` trägt `?v={{v}}`, der Server setzt beim Ausliefern eine Version aus Größe/Änderungszeit aller .js/.css ein (`services/frontend_page.py`) – nichts von Hand hochzählen. Dialoge stehen in `frontend/dialogs/` und werden über `<!-- include: dialogs/….html -->` eingesetzt.

## Umgebungen

| | Port | Code auf dem Pi | Daten | Dienst |
|---|---|---|---|---|
| Produktion | 8000 | `~/GoThea` | `~/GoThea/data/prod/` | `gothea.service` |
| Staging | 8001 | `~/GoThea-staging` (eigene `.venv`) | `~/GoThea/data/staging/` (Pfade in `~/GoThea-staging/.env`) | `gothea-staging.service` |

- Pi: `pi@192.168.1.135`, Logs: `sudo journalctl -u gothea-staging -f`. Hängt per **WLAN** im Netz (eth0 ungesteckt), startet jede Nacht um 03:22 neu (root-Crontab). Der WLAN-Stromsparmodus machte den Pi minutenweise unerreichbar, obwohl er lief (16.10.); seitdem aus per `wifi-powersave-off.service` + `/etc/dhcpcd.exit-hook`. Prüfen: `/usr/sbin/iw dev wlan0 get power_save`. „App geht nicht auf“ → erst Ping/SSH, dann `journalctl -b -1` (läuft das Log bis zum Neustart weiter, war es das Netz, nicht der Pi).
- `data/`, `inbox/`, `experiments/` werden beim Deploy nicht synchronisiert. `.env` (API-Key, `OPENAI_MODEL`) liegt nur auf dem Pi bzw. lokal in `experiments/openai_study/.env`.
- `data/shared/` gehört beiden Umgebungen (inhaltsadressierter Cache der Seiten-Erschließung).
- **Hintergrund-Worker:** Seiten-Erschließung und Renderer müssen immer laufen (sie füllen die Datenbank, Grundlage für den Tutor) – `GOTHEA_BACKGROUND_WORKERS` nie dafür abschalten. Der Übungs-Vorrat hat einen eigenen Schalter `GOTHEA_EXERCISE_POOL` (Standard aus, bis Tutor/Übungen neu gebaut sind).
- Backups vor größeren Eingriffen: `~/GoThea-backups/` auf dem Pi.
- Skripte auf dem Pi: Staging `cd ~/GoThea-staging && .venv/bin/python scripts/<name>.py` (die `.env` dort setzt Umgebung und Datenpfade); Produktion `cd ~/GoThea && APP_ENV=production .venv/bin/python scripts/<name>.py`.

## Architektur

- `backend/main.py` – App, Lifespan (Tabellen, Migrationen, Seeder, Hintergrund-Worker).
- `backend/app/config.py` – alle Pfade/Schalter aus der Umgebung. `database.py` – Engine + schlanke Spalten-Migrationen (`ensure_schema_migrations`).
- `backend/app/prompts/` – **alle** KI-Prompts.
- `services/llm.py` – **einziger Zugang zu OpenAI**: `chat()`, `chat_json()`, `speech()`, gemeinsamer `client()`, `is_available()`. Jeder Aufruf nennt einen `purpose` und landet im Log und in `DATA_DIR/logs/llm_usage.jsonl` (Tokens, Dauer, Fehler). `temperature` nur für Modelle, die es kennen; lehnt die API einen optionalen Parameter ab, ein Versuch ohne. Fehler = `LLMError`, der Dienst entscheidet über den Fallback. Modelle, Stimme, Zeitlimit, Wiederholungen in `config.py`. Tests schalten KI über `backend.app.config.OPENAI_API_KEY` + Ersetzen von `openai.OpenAI` ein; `conftest` setzt den Client pro Test zurück.
  - `chat_stream()` (Streaming + Werkzeuge) läuft über die **Responses API**: `gpt-6-luna` lehnt Werkzeuge in Chat Completions ab, solange es nachdenkt. Liefert Ereignisse `text` / `tool_call` / `tool_result` / `done` (Verlauf im Responses-Format zum Fortsetzen), höchstens `max_rounds` Runden, `store=False` (Nachdenken kommt verschlüsselt zurück und geht mit). Werkzeuge = `llm.Tool`; Kontext (DB, Rolle) beim Anlegen binden, nie von der KI übergeben lassen. Erstes Werkzeug: `services/luna_tools.py` → `unterlagen_durchsuchen` (immer ohne Lösungen). Ausprobieren: `scripts/try_llm_tools.py "Frage"` (Stand 16.10. auf Staging: Dreisatz-Frage → 1 Suche, 1866+407 Tokens, erstes Textstück nach ~14 s, davon ~10 s Nachdenken vor der Suche).
- `backend/app/services/` – Fachlogik. Wichtige Dienste:
  - `document_kinds.py` – einzige Quelle der Dokumentarten (inkl. Altnamen-Abbildung).
  - `material_ingestion.py` – Upload (Voranalyse → Bestätigung) und Bearbeiten (Ändern, Umsortieren, Zusammenführen). **Gemeinsame Bausteine für Upload und Inbox:** `read_document`, `apply_book_rule`, `store_material`, `queue_background_processing` (Rendern + Segmentierung bzw. Erschließung) – neue Wege, die Materialien anlegen, nutzen diese. Notizen und erschlossene Seiten wandern beim Umsortieren mit (`_renumber_page_rows`), beim Zusammenführen werden erschlossene Seiten übernommen.
  - `document_analyzer.py` – KI-Einordnung beim Upload/Inbox (Seitenbilder: ≤6 Seiten alle, sonst 3), liefert Art, Fach, Thema, Titel, Signale (Lösungsseiten, auf Papier bearbeitet, von Lehrkraft bewertet). Rückfall ohne KI: `document_heuristics.py`.
  - `book_segmentation.py` – Bücher → Kapitel (bekannte Tabellen als JSON in `backend/app/book_tables/`, PDF-Outline, KI-Inhaltsverzeichnis); pro Buch nur eine Segmentierung gleichzeitig.
  - `page_extraction.py` – **Seiteninhalt-Erschließung** in `material_pages` («S: …» = Theas Handschrift, «L: …» = Lehrkraft). Dokumente sofort, Buchkapitel gedrosselt (`GOTHEA_BOOK_EXTRACTION_INTERVAL`).
  - `material_search.py` – **Suche** (Lupe, später Lunas Werkzeug): FTS5-Index über erschlossene Seiten (`page_search`) und über das Inhaltsverzeichnis/Themenkatalog (`toc_search`), per Trigger aktuell, beim Start nachgebaut. Lösungen nur mit gültigem Eltern-Token (`parent_auth.is_parent`). Gewichte und Mischung gemessen mit `scripts/eval_search.py` (Fragen: `~/GoThea-eval/search_questions.json` auf dem Pi; Stand 16.10.: Treffer@3 17/19, Buch@3 15/17). Grenzen: reine Wortsuche (keine Bedeutungen), keine Markierung auf dem Seitenbild, Mitschriften ohne echtes Datum.
  - `topic_catalog.py`, `book_topic_catalog.py`, `topic_consolidation.py`, `topic_plans.py` – Themenkatalog.
  - `page_renderer.py` – Seitenbilder (pdftoppm, Priorität, Cache-Aufräumen).
  - `timetable_slots.py` / `timetable_analyzer.py` – Stundenplan-Import (Untis-Zeilen → Slots).
  - `tutor_service.py` – Tutor „Luna“ (Tafel-Feedback, Übungen, Lückenprüfung, TTS).
- `frontend/` – klassische Skripte ohne Build, gemeinsamer globaler Bereich, Ladereihenfolge in `index.html`: `js/api.js` (**einziger Weg zum Backend**: `apiFetch()`/`apiJson()`, Eltern-Token, 403 → PIN-Dialog), `js/*.js` (eine Datei pro Bereich, früher `app.js`), `js/ink_core.js` (Zeichenkern), `whiteboard.js` (Tafel, nutzt den Kern über `surface.…`), `cloze_trainer.js`; Stile in `css/*.css` (Reihenfolge = Kaskade, nicht umsortieren); Dialoge in `dialogs/*.html`.
  - **Icons:** alle aus `frontend/Icons/*.svg` (Linienstil: 100er-Raster, `stroke-width="4"`, runde Enden; Übersicht `Icons/uebersicht.html`). Eingebunden als CSS-Maske (`css/icons.css`, **erzeugt** von `scripts/build_icon_css.py` – nach neuem Icon ausführen), folgen `currentColor`. In JS `icon("Name")`, `iconText()`; Überschrift als Icon: `.icon-heading` + `sr-only`-Text. `js/icons.js` ist die **einzige Quelle für Fach-Icon und Fachfarbe** (`SUBJECTS`: `subjectIcon()`, `subjectColor()`, `subjectStyle()`, `subjectLabel()`) und Dokumentart-Icons; Emojis und `color_code` aus der API werden nicht angezeigt. `tests/unit/test_icons.py`: CSS aktuell, jedes verwendete Icon existiert, keine Emojis, keine zwei Fächer mit gleicher Farbe.
  - **Listen:** Dokumente (Fachseite, Upload) = aufklappbare Zeilen `buildMaterialCard()` in `uploads.js`; Bücher = Inhaltsverzeichnis-Baum in `books.js` (`renderBookNode`, auch eingebettet auf der Fachseite via `buildEmbeddedBookNode`, Abschnitte nach `level` verschachtelt); Tafeln der Fachseite = `buildBoardRow()` in `subject_detail.js`. Der Reader merkt sich, woher er geöffnet wurde (`rememberReaderOrigin`), „Zurück“ führt dorthin.
- `scripts/` – Pflege-Skripte (Neu-Einordnung, Themenkatalog, Zusammenführung, Klassifizierungs-Messung).

## Fachliche Konzepte (mit dem Nutzer abgestimmt)

- **Dokumentarten:** Arbeitsblatt, Mitschrift (handschriftlich), Buch (auch Arbeitsheft; Kapitel = Buchauszug), **Test = jede von der Lehrkraft bewertete Leistung** (auch Diktat, bewertetes Protokoll), Klassenarbeit, Vokabelliste (Beispielsätze nur aus echten Materialien, mit Quelle), Sonstiges, Stundenplan. Hefte = automatisch geführte Sammlung pro Fach **und Schuljahr** mit Inhaltsverzeichnis und PDF-Export (noch nicht gebaut).
- **Bearbeitungs-Ablauf** (noch nicht gebaut), gemeinsam für Arbeitsblatt, Arbeitsheft-Seiten und Tests: offen → abgegeben (gesperrt) → ausgewertet → besprochen. Viele Blätter sind schon auf Papier ausgefüllt → direkt auswerten. Lösungen bleiben für Thea **serverseitig** verborgen, bis abgegeben ist. Getrennte Ebenen: Original, Theas Antworten, Lösungen, Auswertung, Besprechungsnotizen. **XP:** voll, wenn alle Fehler besprochen sind; anteilig, wenn Thea vorher beendet.
- **Themen:** mittlere Ebene (Unterrichtseinheit) mit **Bereich** darüber (z. B. Mechanik › Hookesches Gesetz). Katalog aus den Inhaltsverzeichnissen der Bücher (`topic_book_refs` = Thema → Kapitel + Seiten); Bio 7/8 gemeinsam. Themen aus Theas Dokumenten nie zusammenlegen, Buchthemen nie umbenennen/zusammenlegen. Bücher/Kapitel tragen kein Thema. Pflege-Skripte: erst Vorschau (wird gespeichert), dann `--apply` wendet **genau** diese an.
- **Tutor braucht vollen Zugriff auf Theas Unterlagen** (harte Anforderung). Grundlage ist die Seiten-Erschließung; Tutor-Anbindung (Seite mitschicken, Werkzeuge: Unterlagen durchsuchen, Lernstand, Tests, frühere Sitzungen) steht noch aus.

## Gestaltung der Oberfläche (mit dem Nutzer abgestimmt, 16.10.2026)

- **Icons statt Text**, wo Text nichts hinzufügt: Überschriften als Icon (Text nur als Tooltip/`sr-only`), Zähler als reine Zahl, Knöpfe nur mit Icon + `title`, keine Erklärsätze, keine doppelten Abzeichen. Beschriftungen nur, wo nötig (Formularfelder im Eltern-Bereich, Dokumenttitel). Thea lernt die App durch Benutzen.
- **Personen-Icons geschlechtsneutral** (keine Zöpfe o. Ä.): Thea-Modus `Kind.svg` (eine Figur mit Kinderproportionen), Eltern-Modus `Eltern.svg` (zwei Erwachsene). Keine Icons mit irreführender Nebenbedeutung (Mondsichel für den Tutor las sich als „schlafen gehen“).
- **Fächer konsequent farbcodiert** (Stundenplan, Kacheln, Listen, Bücher …), Farben aus `SUBJECTS` in `js/icons.js`, gemessen unterscheidbar (CIEDE2000 ≥ 17,9 unter Theas 14 Fächern).
- **Listen statt Kartenraster**, aufklappbar für Details (Dokumente, Bücher, Tafeln).
- **Tafel-Kopfleiste** (links → rechts): bei Dokumenten Zurück-zum-Buch + ← 2 / 3 →, Tutor (`Tutor.svg`), Aufgabe, Ton, Fach/Tafel/Unterlage-Dropdowns, rechts „+“, Vollbild, Verbindungspunkt. Nichts liegt über der Seite; Speichern läuft unsichtbar, sichtbar nur bei Fehler. Zu schmal → Leiste scrollt seitlich.
- Kopfzeile der App muss auch auf dem iPad im Hochformat einzeilig bleiben.

## Stolperfallen

- Das Repo liegt in Synology Drive (`~/Library/CloudStorage/…`). Der Ordner muss **dauerhaft angeheftet** sein (lokal behalten): Dateien „auf Abruf“ werden sonst beim Zugriff nachgeladen – Tests hängen, Testserver starten nicht, `ruff` wird abgebrochen, Dateirechte springen um (`core.fileMode` ist deshalb `false`).
- SQLAlchemy-Sessions laufen mit `autoflush=False`: vor Abfragen auf eben hinzugefügte Objekte `db.flush()`.
- Daten, die eine Voranalyse anlegt und ein späterer Request nutzt, müssen **committet** werden (sonst 404 beim Bestätigen).
- Der Seeder legt Start-Themen nur für **neu angelegte** Fächer an (gelöschte Platzhalter kommen nicht zurück).
- **Pencil/Zeichenkern (`frontend/js/ink_core.js`, `createInkSurface()`; Tafel und Dokument-Notizen) ist fragil und mühsam erarbeitet:** darf besser, auf keinen Fall schlechter werden. `tests/unit/test_ink_core_guard.py` schlägt bei jeder Änderung an der Datei an (Prüfsumme bewusst nachziehen). Nur unverändert verschieben; Änderungen am Schreibverhalten als eigene, einzeln getestete Commits, vom Nutzer auf dem iPad geprüft. Dazu gehören auch die iOS-relevanten CSS-Regeln (`touch-action`, `user-select`, `-webkit-touch-callout`).
- Stundenplan und Tafel nutzen Zen-Modi (fixierte Seite ohne Scrollen). Jede Ansicht, die einen Tab aktiviert, muss `applyTabViewModes()` aufrufen.
- Endpunkte, die Inhalte inkl. Lösungen liefern, bleiben im Eltern-Modus, bis Lösungen serverseitig verborgen werden.
- Tests (`tests/conftest.py`): temporäres `DATA_DIR`/`SHARED_DATA_DIR`, leerer API-Key, keine Hintergrund-Worker, frische In-Memory-DB pro Test. `client` und `strict_client` nie im selben Test (teilen sich die Dependency-Overrides). Suite läuft in ~75 s (überwiegend Browser-Tests; ohne Playwright werden sie übersprungen). `tests/e2e/test_dialogs.py` öffnet jeden Dialog einmal – fängt Ladereihenfolge-Fehler der klassischen Skripte.
- **Browser-Tests teilen sich einen Testserver** (Session-Fixture): Daten anderer Tests sind da. Eindeutige Titel verwenden und nichts über das voreingestellte Fach/die Reihenfolge annehmen; neue Tests auch einzeln laufen lassen. Bücher mit Kapiteln entstehen nur durch die Hintergrund-Zerlegung (im Test aus) → `/api/v1/books` per `page.route` einspielen (siehe `test_books_toc.py`). Für Sichtprüfungen echte Staging-Daten per GET holen und ebenso einspielen.
- `index.html` nie per Regex über mehrere Blöcke ändern: ein zu gieriges Muster hat einmal Zeichenfläche und Werkzeugleiste der Tafel mit entfernt (Tests fingen es). Exakte Textstellen ersetzen und den entfernten Block vorher ausgeben.
- Die Tafel kennt die gerade geöffnete Tafel: Umbenennen/Löschen von außen (Fachseite) läuft über `window.renameBoardFromList`/`deleteBoardFromList` in `whiteboard.js` (Titel nachziehen, Auto-Save stoppen). Die Tafel-Liste in der seitlich scrollenden Kopfleiste ist `position: fixed` (sonst abgeschnitten).
- Lesemodus (`body.reader-zen-mode`) ist genau eine Bildschirmhöhe: jeder zusätzliche Abstand oben schiebt die Seitenleiste unten aus dem Bild.

## Stand & nächste Schritte

Erledigt (Okt 2026): Dokumentarten + Neu-Einordnung, Themenkatalog aus Büchern, Seiten-Erschließung (läuft auf Staging; Bücher werden über Nacht nachgeholt), Stundenplan-Import, Test-Isolation, Renderer-Aufräumen.
Erledigt am 15.10.2026 (Aufräumen, Teil 1): Übungs-Vorrat abgeschaltet; Browser-Tests (Hauptansichten, Pencil-Referenz, Tafeln); ungenutzte Importe + `ruff`; eigener Staging-Code-Ordner, `deploy.sh` standardmäßig Staging; **zentrale KI-Schicht** `services/llm.py` mit Kostenprotokoll; 17 stille Fehler geloggt; **Tafeln wie Notizen** (`/api/v1/boards`: pro Fach, KI-Name, Archiv, Vorschaubild; Dokumente mit Notizen pro Seite).

Konzept Tutor „Luna“ + Übungsarten: Claude-Doc https://claude.ai/code/artifact/e9556b4a-e16b-4671-84a1-efa29623bc82 (Tabs „Luna – Tutor-Konzept“, „Übungsarten“). Übungsarten werden in einem eigenen Chat ausgearbeitet (nur Konzept, kein Code).

**Erledigt am 16.10.2026 (auf Staging, Produktion steht aus):** KI-Schicht mit Streaming und Werkzeug-Aufrufen (`chat_stream`, Responses API) und erstes Werkzeug „Unterlagen durchsuchen“. Offen: lange Wartezeit bis zum ersten Wort (Nachdenken) – beim Tutor-Bau Nachdenk-Aufwand (`reasoning.effort`) messen und eine Zwischenmeldung („Luna schaut in deinen Unterlagen nach …“) zeigen.

**Erledigt am 16.10.2026: Oberfläche aufgeräumt (nur auf Staging, Produktion steht aus – gesammelt nach Sichtung durch den Nutzer):** einheitlicher Icon-Satz statt Emojis (50+ neue Icons, `js/icons.js`), Fächer farbcodiert, Bücher als aufklappbares Inhaltsverzeichnis (auch auf der Fachseite, Bücher mit „Ändern“), Dokumente und Tafeln als aufklappbare Listen, Suche + Fach-Filter in der Upload-Liste (Buchkapitel ausgeblendet), Tafeln auf der Fachseite umbenennen (alle) und löschen (Eltern, neu: `DELETE /api/v1/boards/{id}`), Tafel-Kopfleiste verschlankt und seitlich scrollbar, Dokumentleiste über der Seite entfernt, Reader-Seitenleiste nicht mehr abgeschnitten, durchgehend Icons statt Text, neutrale Kind/Eltern-Icons. Backend: Level-/Stufentexte ohne Emojis. Pi: WLAN-Stromsparmodus aus (siehe Umgebungen).

**Nächster Schritt:** Staging-Stand nach Sichtung auf dem iPad gesammelt nach Produktion (`./deploy.sh prod`). Danach Gedächtnis/Lernstand in der DB (mit dem Nutzer abstimmen), dann HTTPS. Später, eigener Chat: „Luna fragen“-Testseite (Eltern-Modus, nur Staging) zum Sammeln echter Fragen.

Vereinbarte Reihenfolge:
1. **Aufräumen, Teil 2:** erledigt am 15./16.10.2026, alles auf Produktion (Frontend-Aufteilung + Zeichenkern, Upload-Weg entflochten, Kapiteltabellen als JSON, README). Dabei behoben: Löschen/Zusammenführen erschlossener Dokumente scheiterte (500), erschlossene Seiten folgten Umsortieren/Zusammenführen nicht. Kleinere Reste bei Gelegenheit: Aufräumen innerhalb der `js/`-Dateien, zusammengehörige CSS-Abschnitte (nur mit Bildschirmfoto-Vergleich), Tabs aus `index.html` wie die Dialoge auslagern, `docs/` ist teils überholt.
2. **Fundament für Luna** (siehe Konzept, Abschnitt „Was das Fundament liefern muss“): ~~Materialsuche + Fundstellen-Anzeige~~ (erledigt 16.10., auf Produktion; dort fehlen bis zur Datenübernahme die erschlossenen Seiten), ~~KI-Schicht mit Streaming und Werkzeug-Aufrufen~~ (erledigt 16.10.), Gedächtnis/Lernstand in der DB, HTTPS auf dem Pi (Mikrofon in Safari), Übungsarten als Bausteine (wartet auf das Konzept).
3. **Arbeitsblatt-Ablauf** komplett (siehe Konzepte), danach Arbeitsheft-Seiten, Tests & Arbeiten (inkl. Stärken/Schwächen), Mitschriften, Hefte mit PDF-Export, Vokabellisten.
4. **Tutor** neu bauen (Konzept-Doc), an Seiten-Erschließung und Tafeln angebunden.
5. Übernahme Staging → Produktion per Skript mit Sicherung: Datenbank + Materialdateien als Ganzes kopieren (nicht neu hochladen). Der Cache `data/shared/` ist nach Datei-SHA-256 + Seite verschlüsselt und greift nur bei byte-gleichen Dateien; Buchkapitel sind eigene, aus dem Buch geschnittene PDFs – eine andere Kapitel-Einteilung (KI-Inhaltsverzeichnis) erzeugt andere Dateien und damit eine erneute Erschließung. Der Schlüssel enthält keine Prompt-Version: nach einer Prompt-Änderung liefert der Cache alte Ergebnisse.

**Tutor & Übungen werden neu gedacht** (eigene Session, „muss sauber sein und Spaß machen“). Der bisherige Code (`tutor_service.py`, Übungs-/Phrasen-Pool, Übungslogik in den Routern) ist ein früher Schnellschuss: einfrieren, nicht polieren (nutzt aber schon den gemeinsamen KI-Client). Tafeln liegen vorerst in `tutor_sessions`; beim Tutor-Umbau „Tafel“ und „Lernsitzung“ trennen.

Entschieden: Bei beschädigter PIN-Datei bleibt der Rückfall auf die Standard-PIN (wird als Fehler geloggt).

Bekannte offene Punkte: Tutor-WebSocket `/ws/tutor/…` ist eine Attrappe (`/ws` dagegen speist die Online-Anzeige); „Städte den Ländern zuordnen“ steht in Mathe, Fach unklar. Liegt eine Buchseite auf der Tafel, zeigt das Unterlage-Dropdown trotzdem „Freies Üben“. Kapiteltitel lassen sich nicht umbenennen (eine neue Zerlegung würde sie überschreiben). Buchdeckel (Seite 1 des Buch-Scans) werden bewusst noch nicht angezeigt; `cover_preview_url` zeigt fälschlich auf Kapitel 1.
