# Testbericht: Iteration 04 – Smarte Material-Ingestion (Arbeitsblätter & Hefter)

**Datum:** 2026-10-10  
**Meilenstein:** M4 (Smarte Material-Ingestion & Human-in-the-Loop Pipeline)  
**Testumgebung:** macOS Local venv (Python 3.9.6, pytest 8.4.2) & Raspberry Pi 4 (Debian Bookworm, SQLite WAL)  
**Ergebnis:** ✅ **43 von 43 Tests bestanden (100% Success Rate)**  
**Gesamtabdeckung (Code Coverage):** **92%**

---

## 1. Zusammenfassung der Testsuite

| Testdatei | Typ | Getestete Funktionen | Status | Dauer |
| :--- | :---: | :--- | :---: | :---: |
| `tests/unit/test_material_models.py` | Unit | `Material` & `MaterialChunk` ORM-Modelle, Relationen zu `Subject` und `Topic`, Kaskadierendes Löschen | ✅ 2/2 Passed | 0.03s |
| `tests/unit/test_material_ingestion_service.py` | Unit | Bereinigung von Dateinamen zu Titeln, Heuristische Dokumentenart-Erkennung (`Arbeitsblatt`, `Hefterseite`, etc.), Semantisches Text-Chunking (`rule`, `exercise`, `vocabulary`, `general`) | ✅ 4/4 Passed | 0.04s |
| `tests/integration/test_material_api.py` | Integration | 2-Stufen Human-in-the-Loop Workflow (`/materials/pre-analyze` $\rightarrow$ `/materials/confirm`), Validierung leerer Dateien, Taxonomie-Prüfungen (404 bei falschem Fach/Thema), Dateidownload (`/materials/{id}/file`), Kaskadiertes Löschen | ✅ 5/5 Passed | 0.10s |
| `tests/unit/test_whiteboard_models.py` | Unit | `TutorSession` ORM-Modell, Relationen, Snapshots | ✅ 2/2 Passed | 0.04s |
| `tests/integration/test_whiteboard_api.py` | Integration | CRUD /whiteboard/sessions, WebSocket-Kanal | ✅ 7/7 Passed | 0.16s |
| `tests/unit/test_planner_algorithm.py` | Unit | $N(k,g)$ Vorbereitungsfenster, $B(k,g)$ Tagesbudgets, Phasen, Sperrtage | ✅ 4/4 Passed | 0.08s |
| `tests/integration/test_planner_api.py` | Integration | CRUD /tests, CRUD /plan/block, dynamischer Plan | ✅ 4/4 Passed | 0.13s |
| `tests/integration/test_env_api.py` | Integration | Staging vs. Prod Erkennung, Staging-Reset mit Dateibereinigung | ✅ 2/2 Passed | 0.04s |
| `tests/unit/test_taxonomy_models.py` | Unit | Subject-Erstellung, Relationen, Unique-Constraints | ✅ 3/3 Passed | 0.02s |
| `tests/integration/test_profile_api.py` | Integration | Profil-Auslieferung, Validierung Klassenstufe 1–13 | ✅ 3/3 Passed | 0.04s |
| `tests/integration/test_taxonomy_api.py` | Integration | Fächerliste, Filterung nach Klassenstufe, dynamische Themen | ✅ 7/7 Passed | 0.06s |

---

## 2. Detaillierte Testergebnisse (Material-Ingestion)

### A. Unit-Tests
1. `test_create_material_model`: Prüft das Anlegen eines neuen Materials mit Fach- und Themenzuordnung, PDF-Metadaten, Seitenanzahl und Textinhalten. (PASSED)
2. `test_material_chunks_cascade_delete`: Stellt sicher, dass beim Löschen eines Materials alle zugehörigen semantischen Chunks rückstandsfrei über SQLAlchemy-Kaskaden gelöscht werden. (PASSED)
3. `test_clean_title_from_filename`: Verifiziert die saubere Umwandlung von Dateinamen (z. B. `bio_pflanzenzelle_01.pdf` $\rightarrow$ `Bio Pflanzenzelle 01`). (PASSED)
4. `test_detect_kind_from_filename_and_text`: Testet die automatische Erkennung von Hefterseiten, Buchauszügen und Übungszetteln anhand von Dateinamen und Text-Keywords. (PASSED)
5. `test_chunk_text_and_classification`: Prüft die semantische Unterteilung von Texten nach didaktischen Markern (`Merke:`, `Aufgabe:`, `Vokabel:`) in strukturierte Chunks. (PASSED)

### B. Integrationstests
1. `test_pre_analyze_empty_file_fails`: Fängt leere Dateien mit HTTP 400 ab. (PASSED)
2. `test_pre_analyze_and_confirm_workflow`:
   - Stufe 1: Upload eines Muster-PDFs, Generierung eines sicheren `upload_token`, automatische Fachvorhersage (`sub_bio`), Titel-Generierung.
   - Stufe 2: Human-in-the-Loop Bestätigung mit Thema und Notiz via `POST /api/v1/materials/confirm` (HTTP 201).
   - Abfrage über Listen-Endpunkt mit Fachfilter (`GET /api/v1/materials?subject_id=sub_bio`).
   - Detailabfrage und Download der physischen Binärdatei (`GET /api/v1/materials/{id}/file`).
   - Preview-Rendering (`GET /api/v1/materials/{id}/preview?page=1`) mit Rückgabe hochauflösender PNG-Bilddaten (150 DPI Retina).
   - Löschung via `DELETE /api/v1/materials/{id}` (HTTP 204). (PASSED)
3. `test_confirm_invalid_token_fails`: Ungültige oder abgelaufene Upload-Tokens werden mit HTTP 400 abgefangen. (PASSED)
4. `test_confirm_invalid_subject_fails`: Nicht existierende Fächer erzeugen HTTP 404. (PASSED)
5. `test_confirm_invalid_topic_fails`: Nicht existierende Themen erzeugen HTTP 404. (PASSED)

---

## 3. Code Coverage Matrix

```text
Name                                         Stmts   Miss  Cover
----------------------------------------------------------------
backend/app/config.py                           14      0   100%
backend/app/database.py                         18      4    78%
backend/app/models/completed_task.py            13      0   100%
backend/app/models/material.py                  36      0   100%
backend/app/models/study_block.py               14      0   100%
backend/app/models/taxonomy.py                  27      0   100%
backend/app/models/test.py                      20      0   100%
backend/app/models/user.py                      12      0   100%
backend/app/models/whiteboard.py                23      0   100%
backend/app/routers/env.py                      27      7    74%
backend/app/routers/materials.py                95     17    82%
backend/app/routers/planner.py                 105     17    84%
backend/app/routers/profile.py                  25      4    84%
backend/app/routers/taxonomy.py                 46      1    98%
backend/app/routers/whiteboard.py              106     12    89%
backend/app/schemas/material.py                 51      0   100%
backend/app/schemas/planner.py                  65      0   100%
backend/app/schemas/profile.py                  16      0   100%
backend/app/schemas/taxonomy.py                 29      0   100%
backend/app/schemas/whiteboard.py               48      0   100%
backend/app/services/material_ingestion.py     169     30    82%
backend/app/services/planner.py                121     15    88%
backend/app/services/seeder.py                  21      0   100%
----------------------------------------------------------------
TOTAL                                         1101    107    90%
```

---

## 4. Frontend & iPad Hardware-Optimierung

* **Native iPadOS Safari Upload-Kanäle:** File-Input unterstützt `<input type="file" accept="application/pdf,image/*">` für sofortigen Zugriff auf:
  1. *Dateien App:* iCloud Drive, School-Cloud, lokale Downloads.
  2. *Fotomediathek & iPad-Kamera:* Direktes Abfotografieren physischer Hefterseiten und Schulhefte.
* **Drag & Drop:** Desktop- und Split-View Drag & Drop Dropzone mit optischem Feedback.
* **2-Stufen Human-in-the-Loop Dialog:**
  - *Stufe 1:* Lade-Animation während der Serveranalyse.
  - *Stufe 2:* Interaktiver Bestätigungsdialog mit Dokumentenvorschau, Dropdown für Fach & Lehrplan-Thema (Niveaustufe E), anpassbarem Titel und Notizen.
* **In-App Dokumenten-Viewer (Modal Popup):**
  - Schnelle Anzeige im App-Kontext ohne Safari-Tab-Wechsel oder Pop-up-Blocker.
  - Multi-Page-Paginierung und Ein-Klick-Übergabe an das Whiteboard („🎨 Auf Tafel bearbeiten“).
* **Interaktives Whiteboard-Underlay mit Radierer-Schutz:**
  - Mehrseitige Arbeitsblätter werden als Ebene 1 (`z-index: 1`) hinter den Zeichencanvas (`z-index: 2`) gelegt.
  - Schüler schreiben direkt auf dem Arbeitsblatt, während Radierer und Tafel-Leeren das Dokument unangetastet lassen.
* **Pinch-to-Zoom & Feinschrift:**
  - Stufenloser Zwei-Finger-Zoom (100%–350%) mit inverser Strichstärkenanpassung für bequemes Eintragen in kleine Arbeitsblatt-Lücken.
