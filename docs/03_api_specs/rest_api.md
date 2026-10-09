# 03.1 REST API Spezifikation

## Basis-URL: `/api/v1`

---

## 0. Umgebungs- & Staging-Status

### `GET /api/v1/env`
* **Beschreibung:** Liefert Informationen zur aktuellen Umgebung (Staging vs. Produktion).
* **Response (200 OK):**
```json
{
  "app_env": "staging",
  "is_staging": true,
  "db_name": "app_data.db",
  "env_label": "STAGING (Testdaten)"
}
```

### `POST /api/v1/staging/reset`
* **Beschreibung:** Setzt die Datenbank auf den Werkszustand zurück (nur im Staging-Modus erlaubt, in Produktion gesperrt mit `403 Forbidden`).
* **Response (200 OK):**
```json
{
  "status": "success",
  "message": "Staging-Datenbank wurde erfolgreich auf den Werkszustand zurückgesetzt."
}
```

---

## 1. Profil & Klassenstufe

### `GET /api/v1/profile`
* **Beschreibung:** Liefert das aktive Schülerprofil.
* **Response (200 OK):**
```json
{
  "id": "usr_default_thea",
  "name": "Thea",
  "grade_level": 7,
  "school_type": "Gymnasium",
  "federal_state": "Brandenburg",
  "created_at": "2026-10-10T00:00:00Z"
}
```

### `PATCH /api/v1/profile`
* **Beschreibung:** Ändert die Klassenstufe oder die Schulform.
* **Request:**
```json
{
  "grade_level": 8,
  "school_type": "Gymnasium"
}
```
* **Response (200 OK):** Aktualisiertes Profilobjekt.

---

## 2. Taxonomie (Fächer & Themen)

### `GET /api/v1/taxonomy/subjects`
* **Query-Parameter:**
  * `grade_level` (optional, integer): Filtert Fächer nach Eignung für Klassenstufe.
* **Response (200 OK):**
```json
[
  {
    "id": "sub_math",
    "name": "Mathematik",
    "color_code": "#2563eb",
    "icon": "📐",
    "min_grade": 1,
    "max_grade": 13,
    "is_active": true
  }
]
```

### `GET /api/v1/taxonomy/topics`
* **Query-Parameter:**
  * `subject_id` (optional, string): Filter nach Fach.
  * `grade_level` (optional, integer): Filter nach Klassenstufe.
* **Response (200 OK):**
```json
[
  {
    "id": "top_math_7_rational",
    "subject_id": "sub_math",
    "name": "Rationale Zahlen",
    "grade_level": 7,
    "rlp_level_code": "E",
    "standard_competencies": "Rechnen mit negativen Zahlen, Brüche und Dezimalbrüche ordnen"
  }
]
```

### `POST /api/v1/taxonomy/subjects`
* **Beschreibung:** Legt ein neues Schulfach an (dynamische Erweiterung).
* **Request Body:**
```json
{
  "name": "Informatik",
  "color_code": "#10b981",
  "icon": "💻",
  "min_grade": 5,
  "max_grade": 13
}
```

### `POST /api/v1/taxonomy/topics`
* **Beschreibung:** Legt ein neues Thema an.
* **Request Body:**
```json
{
  "subject_id": "sub_math",
  "name": "Lineare Gleichungen",
  "grade_level": 7,
  "rlp_level_code": "E"
}
```

---

## 3. Lernplan- & Countdown-Engine

### `GET /api/v1/tests`
* **Beschreibung:** Listet alle anstehenden und vergangenen Prüfungen auf.
* **Query-Parameter:**
  * `status` (optional, string): z. B. `upcoming` oder `completed`.

### `POST /api/v1/tests`
* **Beschreibung:** Legt eine neue Arbeit/Klausur an.
* **Request Body:**
```json
{
  "subject_id": "sub_math",
  "topic_id": "top_math_7_rational",
  "title": "2. Klassenarbeit Rationale Zahlen",
  "test_kind": "Klassenarbeit",
  "test_date": "2026-10-24",
  "weight": 1.0,
  "notes": "Vorzeichenregeln, Brüche, Multiplikation"
}
```

### `DELETE /api/v1/tests/{test_id}`
* **Beschreibung:** Löscht eine Prüfung.

### `GET /api/v1/plan`
* **Beschreibung:** Berechnet dynamisch den 7-Tage-Lernplan, heutige Aufgaben und Countdown-Karten basierend auf $N(k,g)$, $B(k,g)$ und Sperrtagen.
* **Response (200 OK):**
```json
{
  "calculated_at": "2026-10-10T12:00:00",
  "upcoming_tests": [...],
  "today_tasks": [
    {
      "task_identifier": "tst_123_2026-10-10",
      "test_id": "tst_123",
      "subject_name": "Mathematik",
      "subject_icon": "📐",
      "subject_color": "#2563eb",
      "test_kind": "Klassenarbeit",
      "days_until_test": 6,
      "phase_number": 2,
      "phase_name": "Phase 2: Aktives Üben & Vertiefen",
      "phase_description": "Typische Rechen- und Textaufgaben eigenständig lösen.",
      "target_minutes": 25,
      "is_completed": false,
      "is_exam_day": false
    }
  ],
  "today_total_minutes": 25,
  "next_7_days": [...]
}
```

### `POST /api/v1/plan/complete-task`
* **Beschreibung:** Schaltet den Erledigt-Status einer täglichen Lernaufgabe um (Häkchen setzen / entfernen).
* **Request Body:**
```json
{
  "task_identifier": "tst_123_2026-10-10",
  "completed": true
}
```

### `GET /api/v1/plan/block` & `POST /api/v1/plan/block`
* **Beschreibung:** Verwaltet Sperrtage (z. B. Wandertage, Geburtstage, Sportturniere), an denen keine Lernblöcke geplant werden dürfen.
* **Request Body (POST):**
```json
{
  "block_date": "2026-10-18",
  "reason": "Schulausflug"
}
```

### `DELETE /api/v1/plan/block/{block_id}`
* **Beschreibung:** Entfernt einen Sperrtag.

### `POST /api/v1/staging/seed-dummy-tests`
* **Beschreibung:** Erstellt 3 realistische Test-Klassenarbeiten (Biologie, Mathe, Deutsch) für Entwicklungs- und Demonstrationszwecke (nur in Staging aktiv).

---

## 4. Multimodale Whiteboard Engine

### `GET /api/v1/whiteboard/sessions`
* **Beschreibung:** Listet alle vergangenen und aktiven Tafelsitzungen auf.
* **Query-Parameter:**
  * `limit` (optional, default 20): Begrenzung der Ergebnisliste.

### `GET /api/v1/whiteboard/sessions/active`
* **Beschreibung:** Liefert die aktuell offene, unvollendete Tafelsitzung (falls vorhanden, sonst `null`).

### `POST /api/v1/whiteboard/sessions`
* **Beschreibung:** Startet eine neue Lernsitzung auf der Tafel für ein Schulfach und optionales Thema/Prüfung.
* **Request Body:**
```json
{
  "subject_id": "sub_math",
  "topic_id": "top_math_7_rational",
  "title": "Rationale Zahlen Rechenübung",
  "grade_level": 7
}
```

### `GET /api/v1/whiteboard/sessions/{session_id}`
* **Beschreibung:** Liefert Details und gespeicherte Vektorstriche (`board_state_json`) einer Sitzung.

### `PUT /api/v1/whiteboard/sessions/{session_id}/state`
* **Beschreibung:** Auto-Save Endpunkt zur Persistierung der gezeichneten Vektorstriche und des Canvas-Snapshots.
* **Request Body:**
```json
{
  "board_state_json": "[...]",
  "snapshot_data_url": "data:image/png;base64,...",
  "summary_notes": "Aufgabe 2 gerechnet"
}
```

### `POST /api/v1/whiteboard/sessions/{session_id}/close`
* **Beschreibung:** Beendet die Tafelsitzung und setzt den End-Zeitstempel.

### `POST /api/v1/whiteboard/sessions/{session_id}/mock-tutor-hint`
* **Beschreibung:** Erzeugt sokratische Hinweis-Aktionen für das transparente KI-Overlay (`highlight_box`, `latex_hint`).

### `WebSocket /ws/tutor/{session_id}`
* **Beschreibung:** Latenzarmer Echtzeit-Kanal für Apple Pencil Updates (`canvas_update`), Stift-Unterbrechungen (`user_interrupt`), Heartbeats (`ping`/`pong`) und sokratische KI-Overlay-Aktionen (`board_actions`).


