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

### `POST /api/v1/taxonomy/import-timetable`
* **Beschreibung:** Lädt ein Stundenplan-Dokument (PDF oder Bild) hoch, extrahiert Fächerkürzel mittels multimodaler OpenAI-Vision-Analyse (oder heuristischem Offline-Fallback), gleicht sie mit dem 23-Fächer-Kanon des Brandenburger Rahmenlehrplans ab, legt fehlende Fächer & Basisthemen automatisch in der Datenbank an und ordnet das Dokument im Dossier *„Stundenplan & Organisation“* ein.
* **Content-Type:** `multipart/form-data`
* **Form-Parameter:**
  - `file`: `UploadFile` (PDF, PNG, JPG, WebP)
* **Response Body (200 OK):**
```json
{
  "message": "Stundenplan erfolgreich analysiert. 3 neue Fächer angelegt.",
  "detected_subjects": [
    { "id": "sub_chemie", "name": "Chemie", "icon": "🧪", "color_code": "#06b6d4" },
    { "id": "sub_math", "name": "Mathematik", "icon": "📐", "color_code": "#3b82f6" }
  ],
  "created_subjects": [
    { "id": "sub_chemie", "name": "Chemie", "icon": "🧪", "color_code": "#06b6d4" }
  ],
  "material": {
    "id": "mat_1234abcd",
    "title": "Stundenplan - Klasse 7 (2026-10-11)",
    "kind": "Stundenplan",
    "subject_id": "sub_math",
    "topic_id": null,
    "file_path": "materials/Stundenplan_Organisation/Stundenplan_-_Klasse_7_2026-10-11.pdf",
    "page_count": 1,
    "file_size": 245000,
    "mime_type": "application/pdf",
    "dossier_title": "Stundenplan & Organisation"
  }
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

---

## 5. Smarte Material-Ingestion (Arbeitsblätter & Hefter)

### `POST /api/v1/materials/pre-analyze`
* **Beschreibung:** Stufe 1 des Human-in-the-Loop Workflows. Extrahiert Metadaten, Seitenanzahl und Text aus PDF oder Bild und prognostiziert Fach, Thema und Dokumentenart.
* **Content-Type:** `multipart/form-data`
* **Body:** `file`: Upload-Binärdatei (max. 50 MB)
* **Response (200 OK):**
```json
{
  "upload_token": "upl_a1b2c3d4e5f6",
  "filename": "biologie_pflanzenzelle_uebung.pdf",
  "file_size": 240800,
  "mime_type": "application/pdf",
  "page_count": 2,
  "predicted_subject_id": "sub_bio",
  "predicted_topic_id": "top_bio_7_zellen",
  "predicted_title": "Biologie Pflanzenzelle Uebung",
  "predicted_kind": "Arbeitsblatt",
  "preview_snippet": "Aufbau der Pflanzenzelle: Zellwand, Vakuole und Chloroplasten..."
}
```

### `POST /api/v1/materials/confirm`
* **Beschreibung:** Stufe 2 des Human-in-the-Loop Workflows. Bestätigt die geprüften/editierten Metadaten, speichert das Dokument dauerhaft und erzeugt semantische Chunks.
* **Request Body:**
```json
{
  "upload_token": "upl_a1b2c3d4e5f6",
  "subject_id": "sub_bio",
  "topic_id": "top_bio_7_zellen",
  "title": "Aufbau der Pflanzenzelle",
  "kind": "Arbeitsblatt",
  "summary": "Wichtiges Merkblatt für die Klassenarbeit"
}
```
* **Response (201 Created):** `MaterialRead`-Objekt mit ID `mat_...` und `chunks_count`.

### `GET /api/v1/materials`
* **Beschreibung:** Listet alle gespeicherten Lernmaterialien auf.
* **Query-Parameter:**
  * `subject_id` (optional): Filter nach Schulfach.
  * `topic_id` (optional): Filter nach Thema.

### `GET /api/v1/materials/{material_id}`
* **Beschreibung:** Liefert Detailinformationen eines Materials inklusive Volltext und semantischer Chunks.

### `GET /api/v1/materials/{material_id}/file`
* **Beschreibung:** Liefert die Rohdatei des Materials zur Anzeige im Browser oder zum Download.

### `GET /api/v1/materials/{material_id}/preview`
* **Beschreibung:** Rendert eine bestimmte Seite eines PDF-Dokuments oder Bildmaterials serverseitig als gestochen scharfes PNG-Bild (150 DPI Retina). Wird für das In-App Dokumenten-Popup und die interaktive Tafel-Hinterlegung verwendet.
* **Query-Parameter:**
  * `page` (optional, integer, default: 1): 1-basierter Index der zu rendernden Dokumentseite.
* **Response (200 OK):**
  * `Content-Type`: `image/png` (oder Original-Bild-MIME-Type bei Bilddateien).
  * Body: Binäre PNG-Bilddaten.

### `DELETE /api/v1/materials/{material_id}`
* **Beschreibung:** Löscht das Material, alle Chunks und die physische Datei vom Dateisystem (204 No Content).

---

## 6. Inbox / Samba-Dropzone (Batch-Ingestion)

### `GET /api/v1/inbox/status`
* **Beschreibung:** Liefert den aktuellen Füllstand des Inbox-Netzwerkordners (Samba-Dropzone) und die Anzahl eventueller Quarantäne-Fehler.
* **Response (200 OK):**
```json
{
  "inbox_dir": "/home/pi/GoThea/inbox",
  "pending_count": 3,
  "files": [
    {
      "filename": "mathe_blatt1.pdf",
      "file_size": 204850,
      "mime_type": "application/pdf",
      "modified_at": "2026-10-10T20:30:00"
    }
  ],
  "errors_count": 0
}
```

### `POST /api/v1/inbox/process`
* **Beschreibung:** Startet die atomare Verstoffwechselung aller wartenden Dateien im Inbox-Ordner. Führt eine multimodale Inhaltsanalyse (Vision/Text) durch, bestimmt Fach, Thema, Titel und einen normierten Dateinamen, verschiebt physische Dateien nach `materials/`, ordnet sie Mappen (`dossiers`) zu und leert den Inbox-Ordner.
* **Response (200 OK):**
```json
{
  "total_detected": 3,
  "processed_count": 3,
  "errors_count": 0,
  "processed_items": [
    {
      "material_id": "mat_a1b2c3d4",
      "title": "Hebel: Grundlagen und Anwendungen",
      "filename": "Physik_Einfache_Maschinen_Arbeitsblatt_Hebel_Grundlagen_und_Anwendungen.pdf",
      "kind": "Arbeitsblatt",
      "subject_id": "sub_physics",
      "subject_name": "Physik",
      "topic_id": "top_phys_einfache_maschinen",
      "topic_name": "Einfache Maschinen",
      "dossier_id": "dos_e5f6g7h8",
      "dossier_title": "Arbeitsblätter: Einfache Maschinen",
      "page_count": 2
    }
  ],
  "quarantined_items": []
}
```

---

## 7. Stundenplan & Schulalltag-Organisation

### `GET /api/v1/timetable`
* **Beschreibung:** Liefert den vollständigen, strukturierten Wochenplan (Montag bis Freitag, 1. bis 8. Stunde) mit A-/B-Wochen-Support, Raum-, Lehrer- und Fachzuordnung.
* **Query-Parameter:**
  * `week_type` (optional, string: `"A"` oder `"B"`): Erzwingt die Stundenansicht für die entsprechende Woche. Ohne Parameter wird die aktuelle Kalenderwoche berechnet (ungerade = A, gerade = B).
* **Response (200 OK):**
```json
{
  "school_name": "Humboldt-Gymnasium Eichwalde",
  "class_name": "Klasse 7D",
  "school_year": "2026/2027",
  "current_week_type": "A",
  "scan_material_id": "mat_12345",
  "scan_material_title": "Stundenplan Thea - Klasse 7D",
  "periods": [
    { "period": 1, "label": "1. Std", "start_time": "07:45", "end_time": "08:30", "is_break": false },
    { "period": 2, "label": "2. Std", "start_time": "08:30", "end_time": "09:15", "is_break": false },
    { "period": 6, "label": "6.1 Std", "start_time": "12:15", "end_time": "13:00", "is_break": false },
    { "period": 7, "label": "6.2 Std", "start_time": "13:05", "end_time": "13:50", "is_break": false }
  ],
  "slots": [
    {
      "id": "slot_mo_1",
      "day_of_week": "Montag",
      "period": 1,
      "period_label": "1. Std",
      "start_time": "07:45",
      "end_time": "08:30",
      "subject_id": "sub_german",
      "subject_code": "D",
      "subject_name": "Deutsch",
      "subject_icon": "📖",
      "subject_color": "#ef4444",
      "teacher": "DÜCK",
      "room": "201",
      "week_type": "both",
      "is_double_period": true,
      "is_break": false,
      "note": null
    }
  ],
  "week_differences": [
    "Montag 5./6.1 Std: In A-Woche Sport (Halle gewo, Fr. DÜCK), in B-Woche Englisch (Raum 104, Fr. SCHD)."
  ]
}
```

### `GET /api/v1/timetable/today`
* **Beschreibung:** Liefert den Tagesplan für den heutigen Tag. Am Wochenende wird automatisch der kommende Montag ausgegeben.
* **Query-Parameter:**
  * `week_type` (optional, string: `"A"` oder `"B"`): Optionaler Override des Wochentyps.
* **Response (200 OK):**
```json
{
  "day": "Montag",
  "is_weekend": false,
  "active_week": "A",
  "slots_count": 6,
  "lessons": [
    {
      "id": "slot_mo_1",
      "period": 1,
      "period_label": "1. Std",
      "start_time": "07:45",
      "end_time": "08:30",
      "subject_id": "sub_german",
      "subject_name": "Deutsch",
      "subject_code": "D",
      "subject_icon": "📖",
      "subject_color": "#ef4444",
      "teacher": "DÜCK",
      "room": "201",
      "is_break": false,
      "note": null
    }
  ]
}
```

### `POST /api/v1/timetable/slot`
* **Beschreibung:** Fügt eine neue Unterrichtsstunde zum Plan hinzu.
* **Status:** `201 Created`
* **Request Body:**
```json
{
  "day_of_week": "Freitag",
  "period": 8,
  "period_label": "8. Std",
  "start_time": "14:40",
  "end_time": "15:25",
  "subject_id": "sub_math",
  "subject_code": "Ma-AG",
  "subject_name": "Mathematik",
  "teacher": "HORN",
  "room": "303",
  "week_type": "both",
  "is_double_period": false,
  "is_break": false,
  "note": "Mathe Olympiade AG"
}
```

### `PUT /api/v1/timetable/slot/{slot_id}`
* **Beschreibung:** Aktualisiert Raum, Lehrer, Zeiten, Notiz oder Fach eines Stundenplan-Eintrags.
* **Status:** `200 OK` (oder `404 Not Found`).

### `DELETE /api/v1/timetable/slot/{slot_id}`
* **Beschreibung:** Entfernt eine Unterrichtsstunde aus dem Stundenplan.
* **Status:** `204 No Content` (oder `404 Not Found`).

### `POST /api/v1/timetable/reset`
* **Beschreibung:** Löscht alle modifizierten Einträge und stellt Theas offiziellen Untis-Klassenplan (Klasse 7D) wieder her.
* **Response (200 OK):**
```json
{
  "status": "success",
  "message": "Stundenplan erfolgreich auf Werkseinstellungen (Klasse 7D) zurückgesetzt."
}
```

### `POST /api/v1/taxonomy/import-timetable`
* **Beschreibung:** Lädt ein Stundenplan-Dokument (PDF oder Bild) hoch, extrahiert per Vision/Heuristik alle Schulfächer und synchronisiert neue Fächer mit RLP-Themen in die SQLite-Datenbank.
* **Content-Type:** `multipart/form-data`
* **Body:** `file`: PDF oder Foto des Stundenplans.
* **Response (200 OK):**
```json
{
  "status": "success",
  "material_id": "mat_abc123",
  "material_title": "Stundenplan Thea - Klasse 7D",
  "dossier_id": "dos_orga456",
  "created_subjects": [
    { "id": "sub_chemie", "name": "Chemie", "icon": "🧪", "color_code": "#059669" }
  ],
  "existing_subjects": []
}
```


