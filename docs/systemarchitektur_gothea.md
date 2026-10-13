# Technische System- und Softwarearchitektur: GoThea (Multimodale Lernzentrale & KI-Tutor)

## 1. Executive Summary & Zielarchitektur

Die Plattform **GoThea** ist eine adaptive, multimodale Lernumgebung für Schülerinnen und Schüler aller Jahrgangsstufen (Klassen 1 bis 13, Initialkonfiguration: 7. Klasse Gymnasium, Land Brandenburg). Sie verbindet ein termin- und countdownbasiertes Lernplansystem mit einem interaktiven, sokratischen KI-Lernbegleiter.

### Kernanforderungen

* **Eingabe:** Hybrides Whiteboard mit latenzarmer Apple-Pencil-Erfassung (Striche, Handschrift, Skizzen) und Tastatureingabe.
* **Ausgabe:** Visuelle Rückmeldungen direkt auf dem Whiteboard (Overlays, Formeln, Markierungen) gepaart mit natürlicher Audioausgabe (Streaming TTS).
* **Didaktik:** Sokratische Führung. Die KI liefert keine fertigen Lösungen, sondern analysiert Rechenschritte und Denkfehler auf dem Whiteboard und stellt altersgerechte Leitfragen.
* **Infrastruktur & Portabilität:** Vollständige Lauffähigkeit auf einem lokalen Single-Board-Computer (Raspberry Pi 4/5) im Heimnetzwerk mit nahtlosem Migrationspfad zu Cloud-Servern (VPS / Dedicated Server).
* **Material-Ingestion:** Minimaler Erfassungsaufwand durch automatische KI-Klassifizierung (Fach, Thema, Titel) mit interaktiver Bestätigung und dynamischer Erweiterbarkeit der Schulfächer und Themen in der Datenbank.
* **Schulserver-Konnektivität (IServ):** Automatischer Abgleich von Schularbeiten, Hausaufgaben und Unterrichtsmaterialien ohne Schuladministrator-Freigabe oder API-Schlüssel über Standard-Protokolle (CalDAV, WebDAV) und Web-Session-Handling.
* **Lehrplan-Konformität:** Anbindung an das Brandenburger Rahmenlehrplan-Modell (Niveaustufen A–H) und offene Bildungsressourcen (OER).

## 2. Topologie & Deployment-Architektur

### 2.1 Lokaler Betrieb (Edge: Raspberry Pi)

Im Initialbetrieb fungiert der Raspberry Pi als lokaler Application-, API- und Static-Content-Server im Heimnetzwerk (WLAN).

```
                      HEIMNETZWERK (WLAN / mDNS)
┌────────────────────────────────────────────────────────────────────────┐
│  Client (iPad Pro / iPad Air / PC / Mac)                               │
│  Browser: Safari / Chrome (PWA-Modus / Web-App)                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTPS / WSS (Port 443 / TLS)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Raspberry Pi 4 / 5 (Raspberry Pi OS 64-bit)                           │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Reverse Proxy & Webserver (Caddy mit automatischem lokalem TLS)  │  │
│  │ - Statisches Hosting des HTML5/JS Whiteboards & Dashboards       │  │
│  │ - SSL-Termination (Caddy Internal CA / root.crt auf iPad)        │  │
│  │ - WebSocket-Upgrade-Handling                                     │  │
│  └──────────────┬──────────────────────────────────┬────────────────┘  │
│                 │ /api/* (HTTP)                    │ /ws/* (WebSocket) │
│                 ▼                                  ▼                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Python Backend (FastAPI / Uvicorn ASGI)                          │  │
│  │ - Lernplan- & Prüfungs-Engine (Alters- & Stufenadaptiv)          │  │
│  │ - Ingestion Worker (Auto-Tagging, OCR, Chunker, RAG-Pipeline)    │  │
│  │ - PageRenderingService (3-Tier Priority Queue, Retina-Cache)     │  │
│  │ - ExercisePoolManager (Zero-Wait Continuous Pool mit Audio-TTS)  │  │
│  │ - BookSegmentationService (3-Stufen TOC & Outline Slicing)       │  │
│  │ - ScoreService (Adaptives Lernen, Gamification & Streaks)        │  │
│  │ - ParentAuth & PIN-Security (Brute-Force Lockout, Session-Cookie)│  │
│  │ - Whiteboard-State-Management, Inking & Stroke-Aggregator        │  │
│  │ - PhoneticSpeechNormalizer & Multimodal Audio Gateway            │  │
│  │ - IServ Sync-Worker (CalDAV, WebDAV & Session Crawler)           │  │
│  │ - RAG-Retrieval (Lokales SQLite + sqlite-vec Index)              │  │
│  └──────────────┬──────────────────────────────────┬────────────────┘  │
│                 │                                  │                   │
│                 ▼                                  ▼                   │
│  ┌───────────────────────────────┐  ┌───────────────────────────────┐  │
│  │ SQLite DB                     │  │ Lokaler File-Storage          │  │
│  │ (app_data.db via WAL-Modus)   │  │ (PDF-Bücher, Hefter-Scans,    │  │
│  │ + sqlite-vec Vector Table     │  │  IServ-Materialien, Uploads)  │  │
│  └───────────────────────────────┘  └───────────────────────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    │ Ausgehende TLS-Verbindungen (WAN)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Externe Dienste & Foundation-Model APIs                               │
│  - Schulserver IServ (HTTPS / WebDAV / CalDAV via Schüler-Login)       │
│  - Multimodal Vision LLM (Bild-, Handschrift- & Vorab-Klassifizierung) │
│  - Text-to-Speech API (Chunked Streaming Audio)                        │
│  - Embedding API (text-embedding-3-small für RAG-Index)                │
│  - Offene Bildungsportale (WirLernenOnline API, Bildungsserver RLP)    │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Migrationspfad zum dedizierten Cloud-Server

Die Architektur ist durch folgende Abstraktionen entkoppelt:

1. **Containerisierung:** Sämtliche Komponenten sind in Docker-Containern definiert (`docker-compose.yml`). Ein Umzug erfordert lediglich das Klonen des Repositories auf einen Linux-Server und das Starten der Container.
2. **Datenbank-Abstraktion (SQLAlchemy ORM):** Wechsel von SQLite zu PostgreSQL erfolgt ausschließlich über den Connection-String in der Umgebungsvariable `DATABASE_URL`.
3. **Storage-Abstraktion:** Lokale Dateiablage für PDFs und Whiteboard-Snapshots nutzt ein abstraktes Interface (`StorageProvider`), das wahlweise auf dem lokalen Dateisystem oder auf S3-kompatiblem Object Storage (AWS S3, MinIO, Cloudflare R2) arbeitet.

## 3. Subsysteme & Komponentenarchitektur

### 3.1 Frontend: Single-Page Application (SPA) & Whiteboard Engine

Das Frontend ist modular strukturiert und verzichtet auf schwere Frameworks, um auf mobilen Browsern minimale Latenzzeiten und geringen Speicherverbrauch zu garantieren.

```
frontend/
├── index.html                  # Shell mit Reiter-Navigation
├── css/
│   ├── main.css                # Basisstile, Theming (Hell/Dunkel)
│   └── whiteboard.css          # Canvas-Overlays, Toolbar
└── js/
    ├── app.js                  # Initialisierung & App State
    ├── router.js               # Tab-Wechsel & View-Management
    ├── modules/
    │   ├── plan.js             # Lernplan-Visualisierung & Sperrtage
    │   ├── tests.js            # Terminverwaltung (CRUD)
    │   ├── iserv_sync.js       # IServ-Konto-Verbindung, Sync-Status & Log
    │   ├── profile.js          # Klassenstufen- & Schulform-Auswahl
    │   ├── materials/
    │   │   ├── uploader.js     # Native Dateiauswahl, Kamera-Capture & Drag-Drop
    │   │   ├── review_modal.js # Vorschau, Fach-/Themen-Bestätigung & Override
    │   │   ├── taxonomy.js     # Dynamische Fach- & Themenauswahl
    │   │   └── oer_search.js   # Online-Recherche im Brandenburger Lehrplan
    │   ├── whiteboard/
    │   │   ├── canvas.js       # Low-Latency Touch/Pencil Handler
    │   │   ├── renderer.js     # Vektor- & Bild-Rendering
    │   │   ├── snapshot.js     # Frame-Extractor & Diff-Detection
    │   │   └── overlay.js      # KI-Markierungen & Annotations-Layer
    │   └── audio/
    │       ├── player.js       # Streaming Web Audio API Handler
    │       └── vad.js          # Voice Activity Detection (Barge-In)
    └── services/
        ├── api.js              # REST Client (Fetch API & Multipart Upload)
        └── ws.js               # WebSocket Manager mit Reconnect-Logik
```

### 3.2 Backend: Python / FastAPI Services

```
backend/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py                 # FastAPI-Applikation & Lifespan Handler
│   ├── config.py               # Pydantic BaseSettings (.env Loader)
│   ├── database.py             # SQLAlchemy Engine, SessionLocal, Base
│   ├── models/                 # ORM-Datenbankmodelle
│   │   ├── user.py             # Schülerprofil (Klassenstufe, Schulform)
│   │   ├── test.py
│   │   ├── study_block.py
│   │   ├── iserv_account.py    # Lokale, verschlüsselte IServ-Credentials & Sync-State
│   │   ├── taxonomy.py         # Dynamische Fächer (Subject) & Themen (Topic)
│   │   ├── material.py         # Schulbücher, Hefter, Chunks & Vektoren
│   │   ├── session.py
│   │   └── competency.py
│   ├── schemas/                # Pydantic DTOs für Requests & Responses
│   ├── routers/
│   │   ├── profile.py          # Umschalten von Klassenstufe & Schulzweig
│   │   ├── tests.py            # CRUD für Arbeiten und Prüfungen
│   │   ├── plan.py             # Planberechnungs-Endpunkte
│   │   ├── iserv.py            # Trigger & Konfiguration für IServ-Synchronisation
│   │   ├── taxonomy.py         # Endpunkte für Fächer- und Themenverwaltung
│   │   ├── materials.py        # Upload, Pre-Scan, Bestätigung & Material-CRUD
│   │   ├── oer.py              # Anbindung an Brandenburger RLP & WLO API
│   │   └── tutor_ws.py         # Echtzeit-WebSocket für Whiteboard & Audio
│   └── services/
│       ├── planner.py          # Countdown-Logik mit altersadaptiven Lernzeiten
│       ├── classifier.py       # Vision-/Text-Vorab-Klassifikation
│       ├── iserv_connector.py  # CalDAV, WebDAV & HTTP Session Client für IServ
│       ├── ingestion.py        # PDF/Foto-Pipeline, OCR, Formel-LaTeX
│       ├── rlp_connector.py    # Bildungsserver Berlin-Brandenburg Scraper/Parser
│       ├── oer_fetcher.py      # WirLernenOnline / MUNDO API Client
│       ├── rag.py              # Chunking, Embeddings, Hybrid-Retrieval
│       ├── ai_tutor.py         # Prompt-Assemblierung, Socratic Governor
│       ├── vision.py           # Snapshot-Aufbereitung & Bild-Diff
│       └── tts_streamer.py     # Chunked Streaming der OpenAI TTS API
```

## 4. Kommunikationsprotokolle & Datenflüsse

### 4.1 REST API (Steuerung, Planverwaltung & IServ)

| **Methode** | **Endpunkt** | **Beschreibung** | **Payload / Query** |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/profile` | Profil mit aktiver Klassenstufe/Schulform | \- |
| `PATCH` | `/api/v1/profile` | Aktualisiert Klassenstufe (`grade_level`) | `{ "grade_level": 7, "school_type": "Gymnasium" }` |
| `POST` | `/api/v1/iserv/connect` | Verknüpft IServ-Konto (lokal verschlüsselt) | `{ "server_url": "https://schule.iserv.de", "username": "thea.muster", "password": "..." }` |
| `POST` | `/api/v1/iserv/sync-now`| Startet sofortigen Hintergrundabgleich | \- |
| `GET` | `/api/v1/iserv/status`  | Zeigt letzten Sync-Zeitpunkt & gefundene Daten | \- |
| `GET` | `/api/v1/taxonomy/subjects` | Liefert Fächer (gefiltert nach Klassenstufe) | Filter: `grade_level=7` |
| `POST` | `/api/v1/materials/pre-analyze` | **Stufe 1 Upload:** Schnelle KI-Erkennung | `multipart/form-data`: Datei (PDF/Bild) |
| `POST` | `/api/v1/materials/confirm` | **Stufe 2 Upload:** Bestätigung durch User | `{ "temp_file_id": "...", "subject_id": "...", "grade_level": 7, ... }` |
| `GET` | `/api/v1/plan` | Berechnet tagesaktuellen Lernplan | \- |
| `POST` | `/api/v1/plan/block` | Sperrt einen Tag („Tag frei“ / „Fach frei“) | `{ "date": "2026-10-15", "subject_id": null, "type": "all" }` |

### 4.2 WebSocket Protokoll (Interaktive Whiteboard- & Audio-Session)

Endpunkt: `/ws/tutor/{session_id}`

Client und Server kommunizieren ereignisbasiert:
* **Client $\rightarrow$ Server:** Canvas-Inkremente (`canvas_update`), Pausen-Trigger, Voice-Activity-Detection und Unterbrechungen (`user_interrupt`).
* **Server $\rightarrow$ Client:** Gekoppelte Sprachausgabe (`audio_chunk`) und visuelle Whiteboard-Aktionen (`board_actions` mit Markierungen, Pfeilen und LaTeX-Overlays).

## 5. Das Pädagogische KI-Orchestrator-Subsystem

### 5.1 Sokratischer Governor (Prompt-Architektur)

Die Foundation-API wird dynamisch basierend auf der hinterlegten Klassenstufe instruiert:

```
[SYSTEM PROMPT - ADAPTIVER SOKRATISCHER GOVERNOR]
Du bist der persönliche Lerncoach für {user_name} (Klasse {grade_level}, {school_type}, Land Brandenburg).
Rahmenlehrplan-Niveaustufe: {curriculum_level_code}.
Fach: {subject_name} | Thema: {topic_name}.

PÄDAGOGISCHE LEITLINIEN (STRIKTE EINHALTUNG):
1. Gib NIEMALS die direkte Lösung oder den nächsten Rechenschritt vor.
2. Wenn du einen Fehler im Schüler-Lösungsweg siehst:
   - Bestätige zuerst, was bereits richtig gerechnet/geschrieben wurde.
   - Stelle eine gezielte, verständliche Leitfrage zum ersten fehlerhaften Schritt.
   - Verweise auf konkrete Stellen auf dem Whiteboard (z. B. "Schau dir mal die zweite Zeile links an").
3. Alters- und Stufenkalibrierung:
   - Klasse 1–4: Spielerische Sprache, sehr kurze Sätze (1–2 Sätze), bildhafte Vergleiche.
   - Klasse 5–9: Klare sokratische Leitfragen, exakte mathematisch-naturwissenschaftliche Begriffe der Sek I.
   - Klasse 10–13 (Oberstufe): Wissenschaftspropädeutische Sprache, Beweisführung, tiefgehende Quellendiskussion.
4. Halte deine gesprochenen Antworten kurz und prägnant (max. 2–3 Sätze). 
   Schülerinnen und Schüler hören zu, statt lange Texte von der Tafel abzulesen.
5. Verwende AUSSCHLIESSLICH die Fachbegriffe und Definitionen aus den hinterlegten 
   Unterrichtsmaterialien und dem Brandenburger Rahmenlehrplan.
```

### 5.2 Die Interaktive Whiteboard-Tutoring-Schleife (Sense → Diagnose → Guide → Track → Remediate)

Das Whiteboard ist die zentrale Interaktionsfläche zwischen Schüler und KI. Der Lernprozess ist als geschlossener, adaptiver 5-Phasen-Kreislauf modelliert:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   DER 5-PHASEN INTERAKTIONS- UND DIAGNOSE-KREISLAUF             │
│                                                                                  │
│  1. SENSE (Wahrnehmung)                                                          │
│  - Schüler bearbeitet Thema / Arbeitsblatt mit dem Apple Pencil                  │
│  - Tafel-Zustand wird bei Schreibpausen (Debounce ~2.5s) oder auf Knopfdruck     │
│    ("Hilf mir") als Vektor-Diff & Snapshot an das Backend übertragen             │
│                                      │                                           │
│                                      ▼                                           │
│  2. DIAGNOSE (Schritt-für-Schritt Analyse)                                       │
│  - Vision- & Reasoning-LLM analysiert die Handschrift Zeile für Zeile           │
│  - Erkennt nicht nur das Endergebnis, sondern Zwischenschritte & Denkansatz      │
│  - Lokalisiert exakt den ersten fehlerhaften Term oder logischen Bruch          │
│                                      │                                           │
│                                      ▼                                           │
│  3. GUIDE (Sokratisches Scaffolding direkt auf der Tafel)                        │
│  - Visuell: KI blendet farbige Markierungsbox (#wb-overlay) um die Zeile ein    │
│  - Auditiv / Text: KI stellt eine kurze Leitfrage (z. B. Vorzeichen-Hinweis)    │
│  - Keine fertige Lösung – Schüler behält die kognitive Führung                   │
│                                      │                                           │
│                                      ▼                                           │
│  4. TRACK (Knowledge Tracing in 'competency_records')                            │
│  - System kategorisiert den Fehlertyp (z. B. "Distributivgesetz mit Minus")     │
│  - Aktualisiert 'mastery_score' und trägt Fehlermuster in 'frequent_errors' ein  │
│  - Speichert Lösungsversuche in 'tutor_sessions'                                 │
│                                      │                                           │
│                                      ▼                                           │
│  5. REMEDIATE (Gezieltes Adressieren von Schwachstellen)                         │
│  - Lernplan-Engine priorisiert das fehlerbehaftete Teilkonzept                   │
│  - Schlägt im nächsten Übungsblock maßgeschneiderte Vertiefungsaufgaben vor      │
│  - Wiederholung, bis das Teilkonzept sicher beherrscht wird (Mastery Learning)   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

#### Funktionsweise der Schritt-für-Schritt Unterstützung:
1. **Arbeiten auf der Vorlage:** Der Schüler rechnet direkt in den Zeilen eines hochgeladenen Arbeitsblatts oder auf freier Tafel.
2. **Unterbrechungsfreier Denkfluss:** Die KI unterbricht den Schüler nicht während des Schreibens. Erst wenn der Schüler innehält oder aktiv Unterstützung anfordert, greift der Tutor ein.
3. **Konkrete visuelle Zeiger:** Statt abstrakter Textnachrichten nutzt die KI das transparente `#wb-overlay` (`board_actions`), um präzise auf Formeln, Rechnungen oder biologische Skizzen zu zeigen.
4. **Altersgerechte Dosierung:** Bei Schülern der 7. Klasse werden Hilfestellungen in maximal 3 gestuften Hinweisen (Prompting-Hierarchie) gegeben:
   * *Stufe 1:* Orientierungshinweis („Schau dir die zweite Zeile noch einmal an.“)
   * *Stufe 2:* Konzeptueller Hinweis („Was passiert mit den Vorzeichen, wenn vor der Klammer ein Minus steht?“)
   * *Stufe 3:* Konkreter Rechenhinweis („Rechne zuerst $-2 \cdot (-3)$ aus.“)

## 6. Lernplan- und Countdown-Algorithmus (Altersadaptiv)

Der Lernplan reagiert deterministisch auf Prüfungstermine, Lernfortschritte und temporäre Sperrtage und skaliert die Anforderungen mit der Klassenstufe.

### 6.1 Mathematische Modellierung & Alterskalibrierung

Für jeden anstehenden Prüfungstermin $T$ sei:

* $d(T) \in \mathbb{N}$: Das Prüfungsdatum.
* $k(T) \in \{\text{Test}, \text{Klassenarbeit}, \text{Klausur}\}$: Die Prüfungsart.
* $g \in \{1, \dots, 13\}$: Die aktuelle Klassenstufe.

#### Vorbereitungsfenster $N(k, g)$ in Tagen:

$$
N(k, g) = \begin{cases} 
3 \text{ bis } 4 \text{ Tage}, & \text{wenn } k = \text{Test} \land g \le 4 \\
5 \text{ Tage}, & \text{wenn } k = \text{Test} \land g \in \{5, \dots, 9\} \\
7 \text{ Tage}, & \text{wenn } k = \text{Test} \land g \ge 10 \\
7 \text{ Tage}, & \text{wenn } k = \text{Klassenarbeit} \land g \le 4 \\
10 \text{ Tage}, & \text{wenn } k = \text{Klassenarbeit} \land g \in \{5, \dots, 9\} \\
14 \text{ Tage}, & \text{wenn } k = \text{Klausur} \land g \ge 10 
\end{cases}
$$

#### Tägliches Richt-Zeitbudget $B(k, g)$ in Minuten:

$$
B(k, g) = \begin{cases}
10 \text{ bis } 15 \text{ Min.}, & \text{wenn } g \le 4 \\
20 \text{ Min.}, & \text{wenn } k = \text{Test} \land g \in \{5, \dots, 9\} \\
25 \text{ Min.}, & \text{wenn } k = \text{Klassenarbeit} \land g \in \{5, \dots, 9\} \\
35 \text{ bis } 45 \text{ Min.}, & \text{wenn } g \ge 10 \text{ (Oberstufe)}
\end{cases}
$$

### 6.2 Phasenallokation

Sei $C = \{c_1, c_2, \dots, c_m\}$ die chronologisch geordnete Menge der verfügbaren Lerntage vor dem Prüfungstag $d(T)$ mit $c_m < d(T)$.

1. **Phase 1 – Grundlagen & Verstehen:** Tage $c_i$ mit $i \le \lfloor 0{,}4 \cdot m \rfloor$.
2. **Phase 2 – Aktives Üben & Vertiefen:** Tage $c_i$ mit $\lfloor 0{,}4 \cdot m \rfloor < i < m$.
3. **Phase 3 – Letzte Runde (Generalprobe):** Tag $c_m$.
4. **Prüfungstag $d(T)$:** Ruhemodus: *„Heute musst du nicht mehr lernen. Du kannst das. Viel Erfolg!“*

## 7. Relationales Datenbankschema (DDL)

```sql
-- Tabelle: Schülerprofile (Multi-Grade Support)
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    grade_level INTEGER NOT NULL DEFAULT 7 CHECK(grade_level BETWEEN 1 AND 13),
    school_type TEXT NOT NULL DEFAULT 'Gymnasium' CHECK(school_type IN ('Grundschule', 'Oberschule', 'Gesamtschule', 'Gymnasium', 'Oberstufenzentrum')),
    federal_state TEXT NOT NULL DEFAULT 'Brandenburg',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabelle: Lokale IServ-Konto-Konfiguration (Verschlüsselt)
CREATE TABLE iserv_accounts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    server_url TEXT NOT NULL,           -- z. B. 'https://gymnasium-koenigs-wusterhausen.iserv.de'
    username TEXT NOT NULL,             -- z. B. 'thea.muster'
    encrypted_secret TEXT NOT NULL,     -- AES-GCM verschlüsseltes Passwort
    caldav_sync_enabled INTEGER DEFAULT 1,
    webdav_sync_enabled INTEGER DEFAULT 1,
    tasks_sync_enabled INTEGER DEFAULT 1,
    last_sync_at TIMESTAMP,
    last_sync_status TEXT DEFAULT 'idle',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabelle: Dynamische Schulfächer
CREATE TABLE subjects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,          -- z. B. 'Mathe', 'Physik', 'Informatik'
    color_code TEXT NOT NULL DEFAULT '#2563eb',
    icon TEXT NOT NULL DEFAULT '📚',
    min_grade INTEGER DEFAULT 1,
    max_grade INTEGER DEFAULT 13,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_subjects_name ON subjects(name);

-- Tabelle: Dynamische Themen pro Fach & Klassenstufe
CREATE TABLE topics (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                 -- z. B. 'Bruchrechnung', 'Optik', 'Photosynthese'
    grade_level INTEGER NOT NULL DEFAULT 7,
    rlp_level_code TEXT,                -- 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'
    standard_competencies TEXT,         -- Auszug der geforderten Standards laut RLP
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_topics_subject_grade_name ON topics(subject_id, grade_level, name);

-- Tabelle: Prüfungstermine
CREATE TABLE tests (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('Test', 'Klassenarbeit', 'Klausur')),
    date TEXT NOT NULL,                 -- Format: YYYY-MM-DD
    note TEXT,                          -- z. B. Themenbeschreibung
    source_origin TEXT DEFAULT 'manual',-- 'manual', 'iserv_caldav', 'iserv_tasks'
    external_uid TEXT,                  -- CalDAV UID zur Duplikatsvermeidung
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tests_date ON tests(date);
CREATE INDEX idx_tests_external_uid ON tests(external_uid);

-- Tabelle: Erledigte Aufgaben im Lernplan
CREATE TABLE completed_tasks (
    id TEXT PRIMARY KEY,
    test_id TEXT NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    task_identifier TEXT NOT NULL,      -- Format: {test_id}_{date}
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_tasks_unique ON completed_tasks(test_id, task_identifier);

-- Tabelle: Sperrtage (Freie Tage)
CREATE TABLE study_blocks (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,                 -- Format: YYYY-MM-DD
    subject_id TEXT REFERENCES subjects(id) ON DELETE CASCADE, -- NULL = Ganzer Tag frei
    type TEXT NOT NULL CHECK(type IN ('all', 'subject')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_blocks_unique ON study_blocks(date, COALESCE(subject_id, 'ALL'));

-- Tabelle: Unterrichtsmaterialien & Dokumente (Bücher, Hefter, IServ-Downloads)
CREATE TABLE materials (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
    topic_id TEXT REFERENCES topics(id) ON DELETE SET NULL,
    grade_level INTEGER NOT NULL DEFAULT 7,
    title TEXT NOT NULL,
    material_type TEXT NOT NULL CHECK(material_type IN ('book_pdf', 'notebook_scan', 'worksheet', 'web_link', 'oer_package', 'iserv_file')),
    source_origin TEXT DEFAULT 'upload', -- 'upload', 'rlp_online', 'iserv_webdav', 'iserv_exercise'
    external_file_id TEXT,              -- ETag oder IServ Pfad-Hash
    file_path TEXT,
    source_url TEXT,
    page_count INTEGER DEFAULT 0,
    processing_status TEXT NOT NULL DEFAULT 'pending' CHECK(processing_status IN ('pending', 'processing', 'ready', 'failed')),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_materials_lookup ON materials(subject_id, topic_id, grade_level);
CREATE INDEX idx_materials_ext_id ON materials(external_file_id);

-- Tabelle: Semantische Chunks & Volltextsuche
CREATE TABLE material_chunks (
    id TEXT PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    topic_id TEXT REFERENCES topics(id) ON DELETE SET NULL,
    grade_level INTEGER NOT NULL DEFAULT 7,
    chapter_title TEXT,
    page_number INTEGER,
    chunk_type TEXT NOT NULL CHECK(chunk_type IN ('rule_box', 'exercise', 'theory', 'formula', 'vocabulary')),
    content_markdown TEXT NOT NULL,     -- Inkl. normalisierter LaTeX-Formeln ($...$)
    embedding_json TEXT,                -- Vektor-Fallback für SQLite
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_chunks_lookup ON material_chunks(material_id, subject_id, topic_id);

-- Tabelle: Live-Lernsitzungen & Whiteboard-Persistenz
CREATE TABLE tutor_sessions (
    id TEXT PRIMARY KEY,
    test_id TEXT REFERENCES tests(id) ON DELETE SET NULL,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    topic_id TEXT REFERENCES topics(id) ON DELETE SET NULL,
    grade_level INTEGER NOT NULL DEFAULT 7,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    board_state_json TEXT,
    summary_notes TEXT
);

-- Tabelle: Kompetenz- & Fehler-Tracking (Knowledge Tracing)
CREATE TABLE competency_records (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    mastery_score REAL NOT NULL DEFAULT 0.0,
    frequent_errors TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_competency_lookup ON competency_records(user_id, subject_id, topic_id);
```

## 8. Raspberry Pi Deployment & HTTPS Setup

Damit Apple Pencil, Web Audio API, Kamera und Canvas-Rendering ohne Einschränkungen im iPadOS Safari laufen, verlangt das Betriebssystem eine **sichere HTTPS-Verbindung**.

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: gothea_api
    restart: unless-stopped
    environment:
      - DATABASE_URL=sqlite:////app/data/app_data.db
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - STORAGE_PATH=/app/data/materials
      - ISERV_SECRET_KEY=${ISERV_SECRET_KEY}
    volumes:
      - ./data:/app/data
    expose:
      - "8000"

  web:
    image: caddy:2-alpine
    container_name: gothea_proxy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    environment:
      - DOMAIN_NAME=${LOCAL_DOMAIN:-raspberrypi.local}
    volumes:
      - ./frontend:/usr/share/caddy:ro
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./certs:/data/caddy/certificates
    depends_on:
      - backend
```

## 9. Ausfallsicherheits-, Sicherheits- und Datenschutzkonzept

1. **Datensparsamkeit:** Keine Schüler-Klarnamen oder private Identifikatoren an externe KI-APIs.
2. **Offline-Resilienz:** Bei Internetausfall bleiben Dashboard, Terminplan und lokales Whiteboard einsatzbereit.
3. **Hardware-Schonung:** SQLite im WAL-Modus (`PRAGMA journal_mode=WAL;`), asynchrone Worker-Jobs für OCR und Embeddings entlasten die Pi-CPU.

---

## 10. Smarte Ingestion-Pipeline & Nahtloser Upload

### 10.1 Geräteunterstützung: iPad vs. Desktop (PC / Mac)

Der Upload von Dokumenten ist auf dem iPad **vollständig nativ, barrierefrei und erfordert keinerlei Umwege**:

* **iPadOS Safari Integration:**
  Über Standard-HTML5-File-Inputs (`<input type="file" accept="application/pdf,image/*">`) öffnet das iPad automatisch das native System-Menü:
  1. *Dateien (Files App):* Zugriff auf Downloads, iCloud Drive, Schul-Clouds (OneDrive, Google Drive, WebDAV) und USB-Sticks.
  2. *Fotomediathek:* Direkter Zugriff auf bereits gespeicherte Fotos von Arbeitsblättern.
  3. *Kamera:* Sofortiges Abfotografieren einer Hefterseite im Raum.
* **Drag & Drop:**
  Auf dem iPad funktioniert Drag & Drop über den Split-View-Modus identisch zum Desktop.
* **Desktop (PC / Mac):**
  Funktioniert standardmäßig via Dateidialog oder Desktop-Drag & Drop.

### 10.2 Der 2-Stufen Human-in-the-Loop Workflow

```
┌────────────────────────────────────────────────────────────────────────┐
│ STUFE 1: DATEI-UPLOAD & VORAB-KLASSIFIZIERUNG (ASYNCHRON)              │
│                                                                        │
│ 1. User wählt Datei (PDF / Foto) via Drag & Drop, Kamera oder Files    │
│ 2. Frontend sendet Datei an POST /api/v1/materials/pre-analyze         │
│ 3. Backend-Vision-Worker analysiert Titelseite / erste 2 Seiten:       │
│    - Extrahiert Überschrift, optische Merkmale & Schlüsselbegriffe    │
│    - KI schlägt Fach, Thema, Klassenstufe und Dokumenttitel vor        │
│ 4. Backend liefert strukturierten JSON-Vorschlag zurück (in ~1-2 Sek.) │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STUFE 2: INTERAKTIVER BESTÄTIGUNGS-DIALOG (FRONTEND MODAL)             │
│                                                                        │
│  Fach:        [ Biologie ▼ ]  (KI-Vorschlag aktiv)                     │
│  Klasse:      [ 7. Klasse ▼ ] (Gleicht mit Profil ab)                  │
│  Thema:       [ Fotosynthese und Blattaufbau ]                         │
│  Titel:       [ Heftereintrag Blattquerschnitt ]                       │
│  Materialart: (o) Hefter-Mitschrift  ( ) Schulbuch  ( ) Arbeitsblatt   │
│                                                                        │
│          [ Abbrechen ]              [ Speichern & Verarbeiten (Enter)] │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ VOLLSTÄNDIGE INGESTION & VEKTORISIERUNG                                │
│                                                                        │
│ - Bei Bedarf: Automatisches INSERT in 'subjects' oder 'topics'         │
│ - Verschieben der Datei in persistenten Speicher                       │
│ - OCR, LaTeX-Konvertierung, semantisches Chunking & Vektor-Indexierung │
└────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Automatisierte Inbox / Samba-Dropzone Pipeline (Batch-Verarbeitung)

Neben dem interaktiven Einzel-Upload über das Web-UI verfügt GoThea über eine automatisierte Dropzone-Architektur für den schnellen Netzwerk-Import über den Mac Finder, Windows Explorer oder iPad Dateien-App:

* **Getrennte Netzwerkordner:**
  * Staging: `inbox/staging/` (Port 8001)
  * Produktion: `inbox/prod/` (Port 8000)
* **Multimodaler Inhalts-Analyzer (`document_analyzer.py`):**
  * Verarbeitet Scans und Dateien mit kryptischen Roh-Namen (z. B. `fgjg.pdf`, `Hebel.pdf`).
  * Text-Erkennung für digitale Dokumente ($\ge 80$ Zeichen).
  * Vision-Pipeline für reine Bild- und Papierscans (Seite 1 wird in-memory über system-natives `pdftoppm` als 100 DPI JPEG gerendert und an `gpt-4o-mini` übergeben).
  * Vollautomatisches Renaming: Erzeugt normierte Dateinamen nach dem Schema `[Fach]_[Thema]_[Dokumentart]_[Titel].pdf` und legt fehlende Themen in der Lehrplan-Datenbank automatisch an.
* **Digitale Mappenführung (`dossiers`):**
  * Verknüpft Dokumente automatisch mit übergeordneten Mappen (Übungsmappen, Fachhefter, Lehrbücher, Testsammlungen).
* **Ausfallsichere Quarantäne:**
  * Defekte Dateien werden nach `inbox/<env>/_errors/` verschoben und mit einem `.error.txt`-Bericht dokumentiert. Der Batch-Lauf für alle weiteren Dokumente wird niemals unterbrochen.

---

## 11. Online-Materialien & OER-Schnittstellen (Land Brandenburg)

Der Zugriff auf Online-Materialien für Brandenburger Schulklassen unterliegt klaren rechtlichen und technischen Rahmenbedingungen. Das System nutzt offene Schnittstellen und trennt strikt zwischen frei zugänglichen und geschützten Ressourcen.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             ONLINE-QUELLEN-ARCHITEKTUR                                   │
│                                                                                          │
│  1. ÖFFENTLICH & AUTOMATISIERBAR (OER & LEHRPLÄNE)                                       │
│  ┌──────────────────────────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ Bildungsserver Berlin-Brandenburg (BBB)  │  │ WirLernenOnline (WLO) & MUNDO API    │  │
│  │ - Rahmenlehrplan Online (RLP 1-10)       │  │ - Freie Bildungsmedien (OER)         │  │
│  │ - Kompetenzraster & Niveaustufen (A-H)   │  │ - Filter nach: Bundesland=BB, Fach,  │  │
│  │ - Standardillustrierende Lernaufgaben    │  │   Schulform & Klassenstufe           │  │
│  └────────────────────┬─────────────────────┘  └──────────────────┬───────────────────┘  │
│                       │ JSON / HTML-Parser                        │ REST API             │
│                       ▼                                           ▼                      │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ RLP- & OER-Connector Service (app/services/rlp_connector.py)                       │  │
│  │ - Importiert Themenkataloge und Regel-Kompetenzen direkt in 'topics'               │  │
│  │ - Stellt Muster-Übungsaufgaben als didaktische Fallbacks bereit                   │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│  2. GESCHÜTZT / PROPRIETÄR (SCHUL-CLOUDS & VERLAGE)                                      │
│  ┌──────────────────────────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ Schul-Cloud Brandenburg / Schulportal    │  │ Schulbuchverlage (Klett, Cornelsen)  │  │
│  │ - Geschlossener Bereich (VIDIS / SSO)    │  │ - Proprietäre E-Books mit DRM        │  │
│  │ ➔ Kein API-Zugriff für Fremdsysteme      │  │ ➔ Keine freie Download-API           │  │
│  └────────────────────┬─────────────────────┘  └──────────────────┬───────────────────┘  │
│                       │                                           │                      │
│                       └─────────────────────┬─────────────────────┘                      │
│                                             ▼                                            │
│                         Menschlicher Upload (Human-in-the-Loop)                          │
│                         - Schüler/Eltern exportieren PDF oder fotografieren Hefter       │
│                         - Privilegierte Privatkopie (§ 53 UrhG) auf persönlichem Pi      │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Multi-Grade & Schulstufen-Generalisierung (Klassen 1 bis 13)

Das System ist nicht auf die 7. Klasse beschränkt, sondern passt sich flexibel an jede Klassenstufe und Schulform an.

### 12.1 Das Brandenburger Niveaustufen-Modell (A bis H)

Der gemeinsame Rahmenlehrplan Berlin-Brandenburg für die Jahrgangsstufen 1 bis 10 basiert auf acht aufeinander aufbauenden Niveaustufen:

| Niveaustufe | Typische Klassenstufe | Schulstufe | Relevanz für den KI-Tutor |
| :---: | :---: | :--- | :--- |
| **A – B** | Klasse 1 – 2 | Schulanfangsphase (SAPH) | Fokus auf Audio/Sprache, Bildsymbole, Zahlen bis 100, Fibel-Texte |
| **C** | Klasse 3 – 4 | Grundschule | Grundrechenarten bis $10^6$, einfache Lesetexte, 15 Min. Lerneinheiten |
| **D** | Klasse 5 – 6 | Ende Grundschule (BB) | Brüche, Dezimalzahlen, erste Grammatik-Fachbegriffe |
| **E** | Klasse 7 – 8 | Sek I (Gymnasium / Gesamtschule) | Rationale Zahlen, Variablen, Zellbiologie, 20–25 Min. Einheiten |
| **F** | Klasse 8 – 9 | Sek I | Reelle Zahlen, chemische Reaktionen, erweiterte Argumentation |
| **G** | Klasse 9 – 10 | Erweiterte Berufsbildungsreife (EBR) | Praxisbezug, MSA-Vorbereitung |
| **H** | Klasse 10 | Fachoberschulreife (FOR) / Gymnasiale Orientierung | Vorbereitung gymnasiale Oberstufe, Beweise |
| **Sek II** | Klasse 11 – 12/13 | Gymnasiale Oberstufe (GOST) | Analysis, Vektorrechnung, wissenschaftspropädeutisches Arbeiten |

---

## 13. IServ-Integration ohne API-Key (Connector-Architektur)

Schulen vergeben aus Sicherheitsgründen fast nie offizielle API-Keys oder OAuth-Client-Secrets an Schülerinnen, Schüler oder Eltern. Dennoch ist eine vollautomatische Anbindung an IServ technisch problemlos und stabil realisierbar. 

IServ basiert auf quelloffenen Standard-Diensten, die standardmäßig für jeden einzelnen Schüler-Account freigeschaltet sind. Das Backend verbindet sich direkt mit diesen Schnittstellen unter Verwendung der gewöhnlichen IServ-Zugangsdaten (Benutzername & Passwort des Schülers).

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             ISERV-CONNECTOR-TOPOLOGIE                                    │
│                                                                                          │
│  1. AUTOMATISCHER ABGLEICH VIA STANDARDS (KEIN API-KEY NOTWENDIG)                        │
│  ┌──────────────────────────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ IServ CalDAV-Server                      │  │ IServ WebDAV-Server                  │  │
│  │ https://schule.iserv.de/caldav/          │  │ https://schule.iserv.de/webdav/      │  │
│  │ - Kalender "Klassenarbeiten" & "Tests"   │  │ - Verzeichnis: /Gruppen/Klasse 7b    │  │
│  │ - Persönliche Schul-Termine              │  │ - Verzeichnis: /Eigene Dateien       │  │
│  └────────────────────┬─────────────────────┘  └──────────────────┬───────────────────┘  │
│                       │ RFC 4791 / Basic Auth                     │ RFC 4918 / Basic Auth│
│                       ▼                                           ▼                      │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ IServ Sync Service (app/services/iserv_connector.py auf Raspberry Pi)             │  │
│  │                                                                                    │  │
│  │ 2. OPTIONALER SESSION-CONNECTOR (FÜR DAS ISERV-AUFGABEN-MODUL)                     │  │
│  │ ┌────────────────────────────────────────────────────────────────────────────────┐ │  │
│  │ │ HTTP-Client (Python 'httpx' mit Session-Cookie & CSRF-Token)                   │ │  │
│  │ │ - Authentifiziert sich an https://schule.iserv.de/iserv/app/login              │ │  │
│  │ │ - Liest JSON-Endpunkte des Aufgaben-Moduls: /iserv/exercise/api/exercises      │ │  │
│  │ │ - Extrahiert Abgabefristen, Arbeitsanweisungen und beigefügte Lehrer-PDFs       │ │  │
│  │ └────────────────────────────────────────────────────────────────────────────────┘ │  │
│  └─────────────────────────────────────┬──────────────────────────────────────────────┘  │
│                                        │                                                 │
│                     ┌──────────────────┴──────────────────┐                              │
│                     ▼                                     ▼                              │
│  ┌──────────────────────────────────────┐  ┌──────────────────────────────────────────┐  │
│  │ Termine & Fristen                    │  │ Gefundene Arbeitsblätter & PDFs          │  │
│  │ -> Automatisch in Tabelle 'tests'    │  │ -> Direkte Übergabe an Ingestion-Worker  │  │
│  │ -> Startet Countdown im Lernplan     │  │ -> OCR, LaTeX-Konvertierung & RAG-Index  │  │
│  └──────────────────────────────────────┘  └──────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

### 13.1 Die drei Schnittstellenkanäle im Detail

#### Kanal 1: CalDAV (Prüfungstermine & Kalender)
* **Technologie:** Standardisiertes Kalenderprotokoll über HTTPS (RFC 4791).
* **Endpunkt:** `https://<schule>.iserv.de/caldav/`
* **Authentifizierung:** HTTP Basic Authentication mit IServ-Benutzername und Passwort.
* **Funktionsweise:** 
  1. Der Sync-Worker ruft alle Kalender ab, auf die Thea Zugriff hat (persönlicher Kalender, Klassenkalender, Schuljahresplan).
  2. VEvents werden geparst. Enthält der Betreff Signalwörter wie *„Klassenarbeit“*, *„Test“*, *„LK“* oder den Fachnamen (z. B. *„Mathe KA 2“*), wird der Termin automatisch als Datensatz in die Tabelle `tests` eingetragen.
  3. Über die eindeutige `external_uid` (CalDAV UID) werden Duplikate verhindert und Terminverschiebungen der Lehrkraft automatisch aktualisiert.

#### Kanal 2: WebDAV (Unterrichtsmaterialien & Dateiaustausch)
* **Technologie:** Standardisiertes Netzwerk-Dateiprotokoll über HTTPS (RFC 4918).
* **Endpunkt:** `https://<schule>.iserv.de/webdav/`
* **Authentifizierung:** HTTP Basic Authentication.
* **Funktionsweise:**
  1. Der Worker scannt freigegebene Ordner wie `/Gruppen/<Klassenname>` oder Fachordner (z. B. `/Gruppen/Bio_7`).
  2. Neue PDFs oder Dokumente werden über ihren `ETag` erkannt.
  3. Der Worker lädt neue Dateien automatisch in den lokalen Speicher des Raspberry Pi herunter und übergibt sie direkt an die Vorab-Klassifizierung (Kapitel 10), wo Fach und Thema zugeordnet werden.

#### Kanal 3: Web-Session-Client (Aufgaben-Modul & Vertretungsplan)
* **Hintergrund:** Das IServ-Modul *„Aufgaben“* (wo Lehrer Hausaufgaben und Wochenpläne mit Fristen einstellen) liegt hinter der Web-Oberfläche und nicht im CalDAV-Kalender.
* **Funktionsweise:**
  1. Python (`httpx.AsyncClient`) sendet einen `POST`-Request an das Login-Formular (`/iserv/app/login?_login`) und holt ein reguläres Session-Cookie ab.
  2. Anschließend ruft der Client die internen JSON-Endpunkte ab, die das IServ-Webinterface selbst nutzt (z. B. `/iserv/exercise/api/exercises`).
  3. **Ergebnis:** Aufgaben mit Deadlines werden erfasst, beigefügte Arbeitsblätter heruntergeladen und dem Lernplan für das entsprechende Fach zugewiesen.

### 13.2 Sicherheits- & Datenschutz-Architektur

1. **Verschlüsselte Ablage der Zugangsdaten:**
   * Das IServ-Passwort wird **niemals** im Klartext in der SQLite-Datenbank gespeichert.
   * Es wird mittels symmetrischer Authenticated Encryption (**AES-256-GCM**) verschlüsselt. Der Schlüssel (`ISERV_SECRET_KEY`) verbleibt als Umgebungsvariable ausschließlich auf dem Raspberry Pi.
2. **Keine Weitergabe an Foundation-Modelle:**
   * Die IServ-Zugangsdaten verlassen das lokale Heimnetzwerk unter keinen Umständen. Sie werden niemals an externe APIs (wie OpenAI) übermittelt.
3. **Schonendes Polling (Schutz vor Sperrung):**
   * Um den Schulserver nicht zu belasten und Brute-Force-Schutzmechanismen nicht auszulösen, pollt der Worker standardmäßig in einem Intervall von **60 Minuten** (werktags zwischen 07:00 und 18:00 Uhr).
   * Zusätzlich steht im Frontend ein manueller Button *„Jetzt mit IServ synchronisieren“* zur Verfügung.