# Testbericht: Iteration 01 – Datenkern & Taxonomie-Service

**Datum:** 2026-10-10  
**Meilenstein:** M1 (Core Database, User Profile & Taxonomy Service)  
**Testumgebung:** macOS Local venv (Python 3.9.6, SQLite in-memory, pytest 8.4.2)  
**Ergebnis:** ✅ **13 von 13 Tests bestanden (100% Success Rate)**  
**Gesamtabdeckung (Code Coverage):** **92%**

---

## 1. Zusammenfassung der Testsuite

| Testdatei | Typ | Getestete Funktionen | Status | Dauer |
| :--- | :---: | :--- | :---: | :---: |
| `tests/unit/test_taxonomy_models.py` | Unit | Subject-Erstellung, Topic-Relationen, Unique-Constraints | ✅ 3/3 Passed | 0.08s |
| `tests/integration/test_profile_api.py` | Integration | GET /profile, PATCH /profile, Validierung Klassenstufe (1–13) | ✅ 3/3 Passed | 0.09s |
| `tests/integration/test_taxonomy_api.py` | Integration | Fächerliste, Filter nach Klassenstufe, dynamische Erstellung, Duplikatschutz | ✅ 7/7 Passed | 0.12s |

---

## 2. Detaillierte Testergebnisse

### A. Unit-Tests (ORM-Ebene)
1. `test_create_subject_model`: Verifiziert die Anlage von Schulfächern mit Farbcodes und Icons. (PASSED)
2. `test_subject_unique_name_constraint`: Stellt sicher, dass doppelte Fächernamen mit `IntegrityError` abgelehnt werden. (PASSED)
3. `test_create_topic_with_relationship`: Prüft Fremdschlüsselverknüpfung und bidirektionale Beziehung zwischen Fach und Thema. (PASSED)

### B. Integrationstests (API-Ebene)
1. `test_get_profile`: Verifiziert das automatische Anlegen und Ausliefern des Standardprofils (Thea, 7. Klasse Gymnasium, Brandenburg). (PASSED)
2. `test_patch_profile_valid`: Prüft Teilaktualisierungen des Profils (z. B. Klassenwechsel). (PASSED)
3. `test_patch_profile_invalid_grade`: Validiert, dass unzulässige Klassenstufen (z. B. 15) mit HTTP 422 abgewiesen werden. (PASSED)
4. `test_list_subjects`: Bestätigt, dass alle initialen 7 Fächer über die API erreichbar sind. (PASSED)
5. `test_list_subjects_filter_by_grade`: Bestätigt, dass Fächerfilterung nach Klassenstufe greift (z. B. Physik ab Klasse 7, nicht in Klasse 4). (PASSED)
6. `test_create_subject_success`: Verifiziert die dynamische Erweiterung um neue Schulfächer (HTTP 201). (PASSED)
7. `test_create_subject_duplicate_fails`: Verhindert doppelte Fächer mit HTTP 400. (PASSED)
8. `test_list_topics_filter`: Prüft Filterung von Themen nach Fach und Klassenstufe. (PASSED)
9. `test_create_topic_success`: Prüft das dynamische Anlegen neuer Themen mit RLP-Niveaustufen (HTTP 201). (PASSED)
10. `test_create_topic_invalid_subject`: Prüft Fehlerbehandlung bei ungültiger `subject_id` (HTTP 404). (PASSED)

---

## 3. Coverage-Matrix

```text
Name                              Stmts   Miss  Cover
-----------------------------------------------------
backend/app/database.py              24      4    83%
backend/app/models/taxonomy.py       27      0   100%
backend/app/models/user.py           12      0   100%
backend/app/routers/profile.py       25      4    84%
backend/app/routers/taxonomy.py      46      1    98%
backend/app/schemas/profile.py       16      0   100%
backend/app/schemas/taxonomy.py      29      0   100%
backend/app/services/seeder.py       21      0   100%
backend/main.py                      42     10    76%
-----------------------------------------------------
TOTAL                               242     19    92%
```

---

## 4. Fazit & Freigabe
Die Kernfunktionen von **Meilenstein 1 (Core Database, Profil & Taxonomie)** erfüllen alle architektonischen Vorgaben, weisen eine Testabdeckung von 92% auf und sind für das Deployment auf den Raspberry Pi freigegeben.
