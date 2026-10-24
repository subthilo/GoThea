# GoThea – Dokumentations-Index & Modulübersicht

Willkommen in der modularen technischen Dokumentation von **GoThea (Multimodale Lernzentrale & KI-Tutor)**.

> **Stand: 15.10.2026, teils überholt.** Maßgeblich sind `CLAUDE.md` (Arbeitsgrundlage, aktueller Stand) und
> `README.md`. Nicht mehr aktuell sind u. a. Übungs-Arena/Vorräte, Lückentext-Trainer und Tutor-Overlay;
> Übungen, Tafeln (`/api/v1/boards`), Suche und Lernplan-Abschnitte fehlen hier.

---

## 📚 Inhaltsverzeichnis

### [01. Systemarchitektur & Infrastruktur](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/01_architecture/overview.md)
* **[01.1 Systemübersicht & Topologie](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/01_architecture/overview.md):** Lokaler Raspberry-Pi-Betrieb (Edge), Client-Anbindung im WLAN, Migrationspfad zur Cloud.
* **[01.2 Datenbankschema & DDL](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/01_architecture/database_schema.md):** Tabellenstrukturen (inkl. `page_annotations`, `exercise_scores`, `board_exercises`), Primär-/Fremdschlüssel, Indizes, SQLite WAL-Modus.
* **[01.3 Umgebungen: Staging vs. Produktion](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/01_architecture/deployment_environments.md):** Getrennte Datenbanken, Port 8000 (Prod) & Port 8001 (Staging), Deployment-Targets.
* **[01.4 Sicherheits- und Datenschutzkonzept](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/01_architecture/deployment_and_security.md):** AES-256-GCM Vault, PII-Maskierung, **PIN-geschützter Elternbereich (`parent_auth.py`)** mit Brute-Force Lockout.

### [02. Fach- und Servicemodule](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/profile_and_curriculum.md)
* **[02.1 Schülerprofil & Brandenburger Rahmenlehrplan](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/profile_and_curriculum.md):** Multi-Grade Support (Klassen 1–13), Niveaustufen A–H.
* **[02.2 Lernplan- & Countdown-Engine](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/planner_and_countdown.md):** Mathematische Vorbereitungsfenster $N(k,g)$, Zeitbudgets $B(k,g)$, Phasenallokation, Sperrtage.
* **[02.3 IServ-Connector](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/iserv_connector.md):** CalDAV-Terminsync, WebDAV-Dateisync, HTTP-Session-Crawler für Aufgaben.
* **[02.4 Material-Ingestion & Vorrendern](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/material_ingestion.md):** 2-Stufen Ingestion, universeller **`PageRenderingService`** (Priority-Queue 1–3, In-Flight Lock), $\ge 20$-Seiten Buch-Erkennung, Quarantäne-Pipeline.
* **[02.5 Whiteboard Engine](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/whiteboard_engine.md):** Latenzarme Apple-Pencil-Erfassung, Vektoren, Diff-Snapshots, Overlays.
* **[02.6 Sokratischer KI-Tutor & Audio](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/socratic_tutor.md):** Pädagogischer Prompt-Governor, Leitfragen-System, **phonetischer Formel-Normalizer (`clean_text_for_speech`)**, Nova-Stimme (0.90) & `/api/v1/exercises/tts`.
* **[02.7 Stundenplan & Organisation](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/timetable_widget.md):** Natives Wochenraster, Untis-Klassenplan 7D, A/B-Wochen Switcher, Dashboard-Widget, Deep-Links.
* **[02.8 Schulbücher & Segmentierung](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/book_browser.md):** **3-stufige automatische Buch-Segmentierung (`book_segmentation.py`)**, Hintergrund-Slicing, Fallback-Browsing ohne Sackgassen, Apple-Pencil Inking mit Palm Rejection.
* **[02.9 Übungs-Arena & Hintergrund-Pools](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/exercise_arena_and_pools.md):** Vollbild-Arena (`cloze_trainer.js`), **kontinuierlicher Vorratsspeicher (`exercise_pool_service.py`)** mit vorgerendertem TTS-Audio (< 10 ms Latenz), Handschrift-Erkennung mit Wiederholungsbitte.
* **[02.10 Didaktisches Score-Tracking & Gamification](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/gamification_and_scores.md):** Fächer- und Methodenscores (`score_service.py`), **adaptive Schwierigkeitsstufen (leicht, mittel, schwer)**, XP, Level-Progression (1–5), Streaks 🔥.
* **[02.11 iPadOS Design-System & Ergonomie](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/ui_and_design_system.md):** Squircle App-Tiles (`22px`), 55+ SVG-Vektor-Icons, radikale Textreduktion, Eulen-Eliminierung & Viewport-Fixes.

### [03. Schnittstellen-Spezifikationen](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/03_api_specs/rest_api.md)
* **[03.1 REST API Spezifikation](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/03_api_specs/rest_api.md):** Alle HTTP-Endpunkte (Profile, Taxonomie, Environment, Ingestion, Inbox, Stundenplan, Schulbücher, **Eltern-Auth, Übungs-Arena, Scores, TTS & Buch-Notizen**).
* **[03.2 WebSocket Protokoll](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/03_api_specs/websocket_protocol.md):** Event-Typen für Whiteboard-Synchronisation und Audio-Streaming.

### [04. Testberichte](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/04_test_reports/)
* **[04.1 Iteration 01 – Datenkern & Taxonomie](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/04_test_reports/iteration_01_profile_taxonomy.md):** 15 Tests, 100% Passed.
* **[04.2 Iteration 02 – Lernplan & Countdown-Engine](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/04_test_reports/iteration_02_planner_engine.md):** 23 Tests, 100% Passed.
* **[04.3 Iteration 03 – Whiteboard & Canvas Engine](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/04_test_reports/iteration_03_whiteboard_engine.md):** 32 Tests, 100% Passed.
* **[04.4 Iteration 04 – Smarte Material-Ingestion](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/04_test_reports/iteration_04_material_ingestion.md):** 43 Tests, 100% Passed.
* **[04.5 Iteration 05 – Stundenplan & Organisation](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/04_test_reports/iteration_05_timetable_and_organization.md):** 76 Tests, 100% Passed.
* **[04.6 Iteration 06 – Handschriftliche Buchnotizen](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/04_test_reports/iteration_06_book_inking_engine.md):** 89 Tests, 100% Passed.
* **[04.7 Iteration 07 – Vollständige Plattform- & Performance-Verifikation](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/04_test_reports/iteration_07_full_platform_verification.md):** 143 Tests, 100% Passed.
* **[04.8 Iteration 08 – iPadOS Modernisierung & Redesign](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/04_test_reports/iteration_08_ui_redesign_and_ipados_modernization.md):** **146 Tests, 100% Passed (Vollständige Suite)**.

---

## 🗺️ Umsetzungs-Status (Roadmap)

| Meilenstein | Beschreibung | Status | Tests |
| :--- | :--- | :--- | :--- |
| **M0: Setup** | Raspberry Pi Deployment, SSH, PWA-Grundgerüst | ✅ Abgeschlossen | Manuell (OK) |
| **M1: Core DB & Taxonomie** | SQLite WAL, User, Fächer & Themen (7. Klasse BB), Staging/Prod | ✅ Abgeschlossen | 15/15 Passed (92% Cov) |
| **M2: Lernplan-Engine** | Countdown-Algorithmus, Prüfungen, Phasen, Sperrtage | ✅ Abgeschlossen | 23/23 Passed (92% Cov) |
| **M3: Whiteboard Engine** | iPad Canvas, PointerEvents, Overlays, WebSocket | ✅ Abgeschlossen | 32/32 Passed (93% Cov) |
| **M4: Material-Upload & Rendern** | 2-Stufen Ingestion, 3-Tier `PageRenderingService`, Prefetching | ✅ Abgeschlossen | 43/43 Passed (92% Cov) |
| **M5: Stundenplan & Orga** | Untis 7D Raster, A/B-Wochen, Dashboard-Widget, Auto-Routing | ✅ Abgeschlossen | 76/76 Passed (86% Cov) |
| **M5.1: Schulbuch-Notizen** | Ultra-Low-Latency Inking, Palm Rejection, Bézier-Glättung | ✅ Abgeschlossen | 89/89 Passed (86% Cov) |
| **M6: Übungs-Arena & Pools** | Continuous Background Generator (`< 10ms`), Lückentext, Vision OCR | ✅ Abgeschlossen | 114/114 Passed |
| **M7: Didaktik & Elternschutz** | Adaptive Schwierigkeit, XP, Streaks, PIN-Schutz mit Lockout | ✅ Abgeschlossen | 139/139 Passed |
| **M8: Auto-Segmentierung** | 3-stufige Inhaltsverzeichnis-Erkennung, Outline/Vision Slicing | ✅ Abgeschlossen | 143/143 Passed |
| **M8.1: iPadOS-Design & Redesign** | Squircle App-Tiles, 55+ SVGs, Textreduktion, Eulen-Entfernung | ✅ Abgeschlossen | **146/146 Passed** |
| **M9: IServ-Connector** | CalDAV, WebDAV, AES-256 Vault | ⏳ Geplant | - |
| **M10: Sokratischer Audio-Tutor** | Live-Audio Dialog & Multimodal Vision Streaming | ⏳ Geplant | - |
