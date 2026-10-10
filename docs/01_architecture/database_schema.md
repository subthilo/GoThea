# 01.2 Relationales Datenbankschema (DDL)

## SQLite-Konfiguration
* Speicherort: `data/app_data.db` (lokal auf dem Pi persistent)
* Modus: **WAL-Modus** (`PRAGMA journal_mode=WAL;`), um gleichzeitiges Lesen (API) und Schreiben (Worker) ohne Sperren zu ermöglichen.
* Fremdschlüssel-Unterstützung: `PRAGMA foreign_keys = ON;`.

---

## Entitäten & Beziehungen (ER-Übersicht)

```
[ users ] (Schülerprofil)
   ├── 1:N ──> [ iserv_accounts ] (Verschlüsselte IServ Zugangsdaten)
   ├── 1:N ──> [ tests ] (Prüfungstermine)
   │             ├── 1:N ──> [ completed_tasks ] (Erledigte Plan-Einheiten)
   │             └── 1:N ──> [ tutor_sessions ] (Live-Lernsitzungen)
   └── 1:N ──> [ competency_records ] (Mastery-Score & Fehlermuster)

[ subjects ] (Schulfächer)
   ├── 1:N ──> [ topics ] (Themen nach Klassenstufe & RLP Niveaustufe)
   ├── 1:N ──> [ tests ]
   ├── 1:N ──> [ study_blocks ] (Sperrtage je Fach oder global)
   └── 1:N ──> [ materials ] (Bücher, Hefter, Arbeitsblätter)
                 └── 1:N ──> [ material_chunks ] (Semantische Text- & Formelabschnitte)
```

---

## Tabellendefinitionen

### 1. `users` (Schülerprofile)
| Feld | Typ | Constraints | Beschreibung |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | UUID des Nutzers |
| `name` | TEXT | NOT NULL | Anzeigename (z. B. Thea) |
| `grade_level`| INTEGER | NOT NULL, 1..13 | Klassenstufe (Default: 7) |
| `school_type`| TEXT | NOT NULL | Grundschule, Gymnasium, etc. |
| `federal_state` | TEXT | NOT NULL | Default: 'Brandenburg' |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |

### 2. `subjects` (Dynamische Schulfächer)
| Feld | Typ | Constraints | Beschreibung |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | UUID oder Kurzcode (z. B. 'math') |
| `name` | TEXT | NOT NULL, UNIQUE | Fachname (z. B. 'Mathematik') |
| `color_code`| TEXT | NOT NULL | Hex-Farbe für UI/Kalender |
| `icon` | TEXT | NOT NULL | Emoji-Icon (z. B. 📐) |
| `min_grade` | INTEGER | DEFAULT 1 | Untere Klassenstufe |
| `max_grade` | INTEGER | DEFAULT 13 | Obere Klassenstufe |
| `is_active` | INTEGER | DEFAULT 1 | Aktiv-Flag |

### 3. `topics` (Themen pro Fach & Klassenstufe)
| Feld | Typ | Constraints | Beschreibung |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | UUID des Themas |
| `subject_id` | TEXT | FK -> subjects(id) | Zugehöriges Schulfach |
| `name` | TEXT | NOT NULL | Themenname (z. B. 'Rationale Zahlen') |
| `grade_level`| INTEGER | NOT NULL | Klassenstufe (1..13) |
| `rlp_level_code` | TEXT | NULLABLE | Niveaustufe laut RLP ('A'..'H') |
| `standard_competencies` | TEXT | NULLABLE | Auszug der RLP-Kompetenzen |

### 4. `tests` (Prüfungstermine & Klassenarbeiten)
| Feld | Typ | Constraints | Beschreibung |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | ID der Prüfung (`tst_...`) |
| `user_id` | TEXT | FK -> users(id) | Schüler-Zuordnung |
| `subject_id` | TEXT | FK -> subjects(id) | Schulfach |
| `kind` | TEXT | NOT NULL | Art ('Klassenarbeit', 'Test', 'Klausur') |
| `date` | TEXT | NOT NULL | Prüfungstermin (`YYYY-MM-DD`, indiziert) |
| `note` | TEXT | NULLABLE | Themenangabe oder Notiz |
| `source_origin` | TEXT | DEFAULT 'manual' | Herkunft (`manual`, `iserv_caldav`) |
| `external_uid` | TEXT | NULLABLE | Externe UID bei CalDAV-Sync |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |

### 5. `completed_tasks` (Erledigte Plan-Aufgaben)
| Feld | Typ | Constraints | Beschreibung |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | ID des Eintrags (`tsk_...`) |
| `test_id` | TEXT | FK -> tests(id) | Zugehörige Prüfung |
| `task_identifier` | TEXT | NOT NULL | Eindeutige Kennung (`{test_id}_{date}`) |
| `completed_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Erledigungszeitstempel |

*Constraint:* `UNIQUE(test_id, task_identifier)`

### 6. `study_blocks` (Sperrtage / Lernpausen)
| Feld | Typ | Constraints | Beschreibung |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | ID des Sperrtags (`blk_...`) |
| `date` | TEXT | NOT NULL | Gesperrtes Datum (`YYYY-MM-DD`) |
| `subject_id` | TEXT | FK -> subjects(id), NULLABLE | Fachspezifisch oder global (NULL) |
| `type` | TEXT | DEFAULT 'all' | 'all' (ganzer Tag) oder 'subject' |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Erstellungszeitpunkt |

*Constraint:* `UNIQUE(date, subject_id)`

### 7. `tutor_sessions` (Whiteboard Live-Sitzungen)
| Feld | Typ | Constraints | Beschreibung |
| :--- | :--- | :--- | :--- |
| `id` | TEXT | PRIMARY KEY | Sitzungs-ID (`ses_...`) |
| `user_id` | TEXT | FK -> users(id) | Schüler |
| `test_id` | TEXT | FK -> tests(id), NULLABLE | Zugeordnete Prüfung |
| `subject_id` | TEXT | FK -> subjects(id) | Schulfach |
| `topic_id` | TEXT | FK -> topics(id), NULLABLE | Thema |
| `title` | TEXT | NULLABLE | Titel der Tafel |
| `grade_level` | INTEGER | DEFAULT 7 | Klassenstufe |
| `start_time` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Startzeitpunkt (indiziert) |
| `end_time` | TIMESTAMP | NULLABLE | Beendigungszeitpunkt |
| `board_state_json` | TEXT | NULLABLE | Vektorstriche (Strokes, Tools, BBoxes) |
| `snapshot_data_url` | TEXT | NULLABLE | PNG Base64 Vorschau |
| `summary_notes` | TEXT | NULLABLE | Notizen der Sitzung |
