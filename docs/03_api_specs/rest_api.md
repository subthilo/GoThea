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
