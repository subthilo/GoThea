# Testbericht: Iteration 02 – Lernplan & Countdown-Engine

**Datum:** 2026-10-10  
**Meilenstein:** M2 (Countdown & Dynamische Lernplan-Generierung)  
**Testumgebung:** macOS Local venv (Python 3.9.6, SQLite in-memory, pytest 8.4.2) & Raspberry Pi 4 (Debian Bookworm, SQLite WAL)  
**Ergebnis:** ✅ **23 von 23 Tests bestanden (100% Success Rate)**  
**Gesamtabdeckung (Code Coverage):** **92%**

---

## 1. Zusammenfassung der Testsuite

| Testdatei | Typ | Getestete Funktionen | Status | Dauer |
| :--- | :---: | :--- | :---: | :---: |
| `tests/unit/test_planner_algorithm.py` | Unit | $N(k,g)$ Vorbereitungsfenster, $B(k,g)$ Tagesbudgets, Phasenaufteilung (Phase 1/2/3), Ruhetag am Prüfungstag, Sperrtage-Ausschluss | ✅ 4/4 Passed | 0.08s |
| `tests/integration/test_planner_api.py` | Integration | CRUD /tests, CRUD /plan/block (Sperrtage), GET /plan (dynamische 7-Tage-Timeline & Heutige Aufgaben), POST /plan/complete-task (Task Toggle), Staging Seeder (/staging/seed-dummy-tests) | ✅ 4/4 Passed | 0.14s |
| `tests/integration/test_env_api.py` | Integration | Staging vs. Prod Erkennung (/env), Staging Reset (/staging/reset) | ✅ 2/2 Passed | 0.04s |
| `tests/unit/test_taxonomy_models.py` | Unit | Subject-Erstellung, Topic-Relationen, Unique-Constraints | ✅ 3/3 Passed | 0.02s |
| `tests/integration/test_profile_api.py` | Integration | Profil-Auslieferung, Updates, Klassenstufen-Validierung | ✅ 3/3 Passed | 0.04s |
| `tests/integration/test_taxonomy_api.py` | Integration | Fächerliste, Filterung nach Klassenstufe, dynamische Erstellung | ✅ 7/7 Passed | 0.06s |

---

## 2. Detaillierte Testergebnisse (Milestone 2)

### A. Algorithmische Unit-Tests (`backend/app/services/planner.py`)
1. `test_preparation_window_formulas`:
   - Prüft die mathematische Formel für das Vorbereitungsfenster:
     $$N(\text{Test}, 7) = 3 \text{ Tage}$$
     $$N(\text{Klassenarbeit}, 7) = 10 \text{ Tage}$$
     $$N(\text{Klausur}, 11) = 17 \text{ Tage}$$
   - Verifiziert, dass Klassenstufen-Multiplikatoren präzise greifen. (PASSED)
2. `test_daily_budget_formulas`:
   - Prüft das tägliche Lernzeit-Budget:
     $$B(\text{Test}, 7) = 20 \text{ Minuten}$$
     $$B(\text{Klassenarbeit}, 7) = 25 \text{ Minuten}$$
     $$B(\text{Klausur}, 12) = 45 \text{ Minuten}$$ (PASSED)
3. `test_phases_and_countdown_workflow`:
   - Verifiziert den Countdown von 10 Tagen bis 0:
     - Tage 10..4: **Phase 1: Grundlagen & Verstehen**
     - Tage 3..2: **Phase 2: Aktives Üben & Vertiefen**
     - Tag 1: **Phase 3: Letzte Runde (Generalprobe)**
     - Tag 0: **Prüfungstag (Ruhemodus)** – 0 Min, automatisch als erledigt markiert. (PASSED)
4. `test_blocked_days_are_excluded`:
   - Verifiziert, dass an Tagen mit Sperreinträgen (`StudyBlock`) keine Lernaufgaben eingeplant werden (0 Minuten). (PASSED)

### B. Integrationstests (API-Ebene)
1. `test_create_and_list_test`:
   - Erstellt eine neue Klassenarbeit in Mathematik über `POST /api/v1/tests`.
   - Listet Prüfungen über `GET /api/v1/tests` und filtert nach Status. (PASSED)
2. `test_study_block_crud`:
   - Legt einen Sperrtag (z. B. "Wandertag / Geburtstag") über `POST /api/v1/plan/block` an.
   - Listet Sperrtage auf und löscht sie wieder via `DELETE /api/v1/plan/block/{block_id}`. (PASSED)
3. `test_plan_calculation_and_task_toggle`:
   - Berechnet den dynamischen Lernplan für die nächsten 7 Tage via `GET /api/v1/plan`.
   - Schaltet den Erledigt-Status einer Aufgabe hin und her via `POST /api/v1/plan/complete-task`. (PASSED)
4. `test_staging_seed_dummies`:
   - Ruft den Staging-Seeder `POST /api/v1/staging/seed-dummy-tests` auf.
   - Verifiziert die Erstellung von 3 realistischen Test-Arbeiten mit korrekter Phasenverteilung. (PASSED)

---

## 3. Code Coverage Matrix

```text
Name                                   Stmts   Miss  Cover
----------------------------------------------------------
backend/app/config.py                     10      0   100%
backend/app/database.py                   18      4    78%
backend/app/models/completed_task.py      13      0   100%
backend/app/models/study_block.py         14      0   100%
backend/app/models/taxonomy.py            27      0   100%
backend/app/models/test.py                20      0   100%
backend/app/models/user.py                12      0   100%
backend/app/routers/env.py                17      1    94%
backend/app/routers/planner.py           105     17    84%
backend/app/routers/profile.py            25      4    84%
backend/app/routers/taxonomy.py           46      1    98%
backend/app/schemas/planner.py            65      0   100%
backend/app/schemas/profile.py            16      0   100%
backend/app/schemas/taxonomy.py           29      0   100%
backend/app/services/planner.py          121     15    88%
backend/app/services/seeder.py            21      0   100%
----------------------------------------------------------
TOTAL                                    559     42    92%
```

---

## 4. Live-Verifikation auf Raspberry Pi (Staging)

- **Host:** `192.168.1.135`
- **Port:** `8001` (Service `gothea-staging.service`)
- **Staging-DB:** `/home/pi/GoThea/data/staging/app_data.db` (SQLite WAL)
- **Status:** HTTP 200 OK auf allen Endpunkten (`/api/v1/env`, `/api/v1/tests`, `/api/v1/plan`, `/api/v1/staging/seed-dummy-tests`).
- **Web-UI:** Dynamischer Lernplan mit Countdown-Karten, Checkboxen, Modal-Dialogen für neue Prüfungen und Sperrtage live verifiziert.
