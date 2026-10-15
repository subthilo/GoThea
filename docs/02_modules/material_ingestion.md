# 02.4 Smarte Material-Ingestion & RAG-Pipeline

## 1. Upload-Kanäle (iPad & Desktop)

* **iPadOS Safari:** Über native File-Inputs (`<input type="file" accept="application/pdf,image/*">`) öffnet das iPad direkt:
  1. *Dateien (Files App):* iCloud Drive, Schul-Clouds, USB-Sticks, Downloads.
  2. *Fotomediathek:* Fotos von Arbeitsblättern.
  3. *Kamera:* Sofortiges Abfotografieren von Hefterseiten.
* **Drag & Drop:** Volle Unterstützung auf dem Desktop und im iPad Split-View.

---

## 2. Der 2-Stufen Human-in-the-Loop Workflow

```
┌────────────────────────────────────────────────────────────────────────┐
│ STUFE 1: VORAB-KLASSIFIZIERUNG (ASYNCHRON)                             │
│ - Upload an POST /api/v1/materials/pre-analyze                         │
│ - Vision-LLM liest Deckblatt / erste Seiten                            │
│ - Schlägt Fach, Thema, Klassenstufe & Dokumententitel vor (~1-2 Sek.)  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STUFE 2: INTERAKTIVER BESTÄTIGUNGS-DIALOG (MODAL)                      │
│ - Schüler/Eltern sehen die vorgeschlagenen Metadaten                   │
│ - Möglichkeit zur manuellen Korrektur oder Bestätigung                 │
│ - Bestätigung via POST /api/v1/materials/confirm                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ VOLLSTÄNDIGE INGESTION & VEKTORISIERUNG                                │
│ - Speicherung im persistenten Storage                                  │
│ - OCR, Formel-Normalisierung (LaTeX $...$)                             │
│ - Semantisches Chunking nach Regeln, Übungen & Vokabeln                │
│ - Vektorisierung & sqlite-vec Fallback-Speicherung                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Online-Materialien & Brandenburger Lehrplan (OER)

* **Bildungsserver Berlin-Brandenburg (BBB):** Rahmenlehrplan Online, Standardillustrierende Aufgaben.
* **WirLernenOnline (WLO) & MUNDO API:** Freie Bildungsmedien gefiltert nach Bundesland BB, Fach und Klassenstufe.
* **Schulbücher (§ 53 UrhG):** Privilegierte Privatkopie von physischen Heftern/Büchern auf dem persönlichen Pi.

---

## 4. In-App Dokumenten-Viewer (Modal Popup)

Statt externer Browser-Tabs (die auf iPadOS Safari oft von Pop-Up-Blockern unterdrückt werden oder die PWA verlassen), öffnet GoThea Dokumente in einem responsiven, modalen In-App-Viewer (`#modal-material-viewer`):

* **Scharfe Retina-Vorschau:** Abruf der Einzelseiten als 150 DPI PNG über `GET /api/v1/materials/{id}/preview?page={page}`.
* **Navigation & Paginierung:** Multi-Page Paginierung (`Seite X von Y`) mit Vor-/Zurück-Buttons.
* **Nahtlose Whiteboard-Übergabe:** Über den Aktionsbutton **„🎨 Auf Tafel bearbeiten“** wird das geöffnete Dokument direkt als interaktive Arbeitsblatt-Vorlage in die Whiteboard-Engine geladen (`loadMaterialAsWorksheet(materialId, pageCount)`).
* **Dateidownload:** Separater Button **„💾 Herunterladen“** zur Übergabe an die iPadOS Dateien-App via `GET /api/v1/materials/{id}/file`.

---

## 5. Intelligenter Seiten-Rendering- & Caching-Dienst (`page_renderer.py`)

Um sämtliche Dokumente (Arbeitsblätter, Hefterseiten, Tests und Buchauszüge) auf dem Raspberry Pi blitzschnell und ohne Speicherengpässe bereitzustellen, betreibt GoThea den `PageRenderingService` ([`backend/app/services/page_renderer.py`](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/backend/app/services/page_renderer.py)) als zentralen Hintergrund-Dienst:

### 1. 3-stufige Prioritäts-Warteschlange (`PriorityQueue`)
Der Renderer unterscheidet drei strikte Prioritätsstufen:

| Stufe | Priorität | Auslöser | Verhalten |
|---|---|---|---|
| **1 (LIVE)** | Höchste | Direkter Seitenabruf im Browser (`GET /preview`) | Fast-Path: Sofortige Auslieferung aus Cache (< 5 ms) oder direktes Rendern mit 100% CPU. Pausiert Hintergrund-Jobs sofort. |
| **2 (PREFETCH)** | Hoch | Blättern zu Seite $P$ | Stößt $P-1$, $P+1$ und $P+2$ mit Priorität 2 an. Seiten sind beim Weiterblättern bereits geladen. |
| **3 (BACKGROUND)** | Niedrig | Neuer Upload / App-Start | Durchläuft im Leerlauf alle noch ungerenderten Seiten aller Dokumente. |

### 2. In-Flight Synchronisation (Doppel-Render-Schutz)
* Wenn mehrere Browser-Clients (z. B. Lehrer und Schülerin) zeitgleich dieselbe Seite anfordern, synchronisiert ein thread-sicheres `threading.Event`-Dictionary (`_in_flight_renders`) die Anfragen.
* Die erste Anfrage rendert das Bild; alle parallelen Anfragen warten auf dasselbe Event und lesen die fertige Datei direkt aus dem Cache, statt die CPU doppelt zu belasten.

### 3. CPU-Schonung auf dem Raspberry Pi
* Sobald eine Live-Anfrage eintrifft (`_live_in_progress_count > 0`), setzt der Hintergrund-Worker sofort aus.
* Zwischen Hintergrund-Jobs werden Mikropausen (40 ms) eingelegt, um die Systemtemperatur des Raspberry Pi niedrig zu halten und andere Prozesse nicht zu blockieren.

### 4. Persistenter Mtime-Disk-Cache
* Cache-Dateien werden unter `data/<env>/cache/pages/{material_id}_p{page}_{mtime}.jpg` gespeichert.
* Rendern erfolgt via `pdftoppm -jpeg -r 120 -f {page} -l {page}` in gestochen scharfer 120 DPI Retina-Auflösung.
* Bei Dokumentänderungen (z. B. Seiten-Reorder) werden veraltete Cache-Dateien sofort invalidiert.

---

## 5.1 Automatische Schulbuch-Erkennung & Ingestion-Routing

Beim Upload und bei der Inbox-Verarbeitung greift eine intelligente Heuristik zur Erkennung von Büchern:
1. **Die $\ge 20$-Seiten Regel**: Jedes PDF mit 20 oder mehr Seiten wird in `pre_analyze_upload` und `process_single_inbox_file` automatisch als `kind="Buch"` klassifiziert.
2. **Automatischer Segmentierungs-Trigger**: Erfüllt ein Dokument die Kriterien eines Schulbuchs (`is_candidate_book`), stößt das System sofort nach dem Speichern asynchron die Hintergrund-Segmentierung an (`trigger_background_book_segmentation`).
3. **Nachträgliche Segmentierung**: Ändern Eltern den Dokumenttyp im Bearbeiten-Modal (`PATCH /api/v1/materials/{id}`) auf `Buch`, wird die Hintergrund-Segmentierung sofort nachträglich gestartet.

---

## 6. Automatisierte Inbox / Dropzone-Pipeline (Batch-Ingestion & Renaming)

Neben dem interaktiven Einzel-Upload im Frontend bietet GoThea eine automatisierte Batch-Ingestion-Pipeline für Dokumente, die per Samba-Netzwerkfreigabe in den Ordner `inbox/staging/` oder `inbox/prod/` geschoben werden.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   INBOX / DROPZONE BATCH WORKFLOW                      │
│                                                                        │
│  1. Samba-Dropzone (`inbox/staging/` oder `inbox/prod/`)              │
│  - Anwender legt Rohscans ab (z. B. "fgjg.pdf", "Hebel.pdf", "asd.pdf")│
│                                      │                                 │
│                                      ▼                                 │
│  2. Ingestion-Trigger (`POST /api/v1/inbox/process` oder Web-UI)       │
│  - System prüft Dateien atomar (Validierung MIME & Dateigröße)         │
│                                      │                                 │
│                                      ▼                                 │
│  3. Multimodale Dokumentenanalyse (`document_analyzer.py`)             │
│  - Prüft auf digitalen Text:                                           │
│    • Falls ≥ 80 Zeichen Text: Schnelle Text-Analyse (< 500ms)          │
│    • Falls reiner Scan / Foto: Seite 1 wird via `pdftoppm` in Memory   │
│      als 100 DPI JPEG gerendert und per Vision analysiert.             │
│  - Modell: `gpt-4o-mini` (JSON Object Mode, Temp: 0.1)                 │
│  - Offline-Fallback: Heuristische Keywords & Dateinamenmuster          │
│                                      │                                 │
│                                      ▼                                 │
│  4. Metadaten-Extraktion & Klassifizierung                             │
│  - Fach: Zuordnung zu einem der 23 Schulfächer                         │
│  - Thema: Abgleich mit `topics` oder automatisches Anlegen neuer Themen│
│  - Dokumentart: Arbeitsblatt | Hefterseite | Schulbuch | Test | Arbeit │
│  - Inhaltlicher Titel: Präziser Titel (z. B. "Aufbau der Pflanzenzelle")│
│  - Normierter Dateiname: `Fach_Thema_Art_Titel.pdf`                    │
│                                      │                                 │
│                                      ▼                                 │
│  5. Atomare Dateiablage & Digitale Mappenführung (`dossiers`)          │
│  - Verschieben der physischen Datei nach `data/<env>/materials/`       │
│  - Einsortieren in thematische Mappe (Übungsmappe, Hefter, Sammlung)   │
│  - Speicherung mit normiertem Dateinamen in der Datenbank              │
│  - Text-Chunking & Volltext-Vorbereitung                               │
│                                      │                                 │
│                                      ▼                                 │
│  6. Fehlerquarantäne (`_errors/`)                                      │
│  - Defekte/0-Byte-Dateien werden nach `inbox/<env>/_errors/` isoliert   │
│  - Fehlerbericht `[name].error.txt` erklärt das Problem                │
│  - Die Batch-Verarbeitung der restlichen Dateien läuft stabil weiter   │
└────────────────────────────────────────────────────────────────────────┘
```

### Dokumentarten (`services/document_kinds.py`)

| Dokumentart | Bedeutung |
| :--- | :--- |
| Arbeitsblatt | Übungsmaterial zu einem Unterthema, auch kopierte Arbeitsheft-Seiten; darf schon auf Papier ausgefüllt sein |
| Mitschrift | Von Thea handschriftlich angelegte Notizen / Hefteinträge (früher „Hefterseite“) |
| Buch | Schulbuch oder Arbeitsheft; wird in Kapitel (`Buchauszug`) segmentiert |
| Test | Jede von der Lehrkraft **bewertete** Leistung: Test, Diktat, bewertetes Protokoll |
| Klassenarbeit | Große Arbeit / Klausur |
| Vokabelliste | Vokabeln mit Übersetzung und Beispielsätzen |
| Sonstiges | Passt in keine andere Art |
| Stundenplan | Wochenraster (Fach *Organisation*) |

Zusätzlich liefert die Analyse drei Signale, die am Material gespeichert werden: `solution_pages_json` (Seiten mit Lösungen / Erwartungshorizont), `worked_on_paper` (bereits auf Papier bearbeitet) und `teacher_graded` (Korrekturen, Punkte oder Note sichtbar). Kleine Dokumente (bis 6 Seiten) werden vollständig als Seitenbilder analysiert, größere über die ersten 3 Seiten.

Neu-Einordnung bestehender Dokumente: `scripts/reanalyze_materials.py` (Fach bleibt unverändert, Bücher verlieren ihre Kapitel nur bei ausdrücklich anderer Dokumentart).

### Modell-Allokation

* **Dokumentanalyse:** `OPENAI_ANALYSIS_MODEL`, Standard = Hauptmodell (`OPENAI_MODEL`). In der Messung mit `scripts/eval_document_classification.py` an 24 echten Dokumenten erreichte `gpt-6-luna` 24/24 korrekte Dokumentarten, `gpt-4o-mini` 19/24 bei rund 15-fachem Token-Verbrauch für Seitenbilder.
* **Tutor & Didaktik:** `OPENAI_MODEL` (`gpt-6-luna`).

---

### Stundenplan-Erkennung, Auto-Routing & Fächer-Übernahme (`timetable_analyzer.py`)

* **Ziel:** Das Hochladen eines Schulstundenplans (Foto oder PDF) soll die Schulfächer der Schülerin automatisch erfassen, fehlende Fächer anlegen und das Dokument zuverlässig im Fach **Organisation** (`sub_orga`) ablegen – selbst wenn der Nutzer oder ein Vision-Prompt versehentlich ein Einzelfach wie *Französisch* (wegen des Tageskürzels „Fr“) vorgeschlagen hat.
* **Erkennungs-Pipeline & Guardrails:**
  1. **Upload-Wege:**
     - Direkt via Web-UI über den Button *„📅 Stundenplan importieren“* (`POST /api/v1/taxonomy/import-timetable`).
     - Über den regulären Upload-Dialog (`POST /api/v1/materials/pre-analyze` & `confirm`).
     - Durch Ablegen im Samba/Finder-Netzwerkordner (`inbox/staging/` bzw. `inbox/prod/`).
  2. **Intelligente Erkennung (`is_timetable_document`):**
     - Prüft Dateinamen (`stundenplan`, `wochenplan`, `timetable`), extrahierten Text (Wochentage Mo–Fr, Stundenraster 1–8, A-/B-Woche) sowie Klassifikations-Tags.
     - **Auto-Routing Guardrail:** Erkennt die Heuristik oder das Vision-Modell einen Stundenplan, wird die Zuweisung hart auf `subject_id = "sub_orga"` und `kind = "Stundenplan"` forciert. Dies verhindert, dass ein Stundenplan in Unterheftern von Französisch, Mathe oder Sport verschwindet.
  3. **Kanonischer Fächer-Abgleich:**
     - OpenAI Vision scannt das Dokument auf Stundenplan-Kürzel (`D`, `Ma`, `*Sp`, `En(B)`, `Bio`, `Ch`, `WAT`, `LER`, `Rel`, etc.).
     - Offline-Heuristik als Fallback prüft Dateinamen und Text gegen den 23-Fächer-Kanon des Brandenburger Rahmenlehrplans (RLP).
     - Neu gefundene Fächer werden mit Icon, Farbschema und Basis-Lehrplanthemen der Jahrgangsstufe 7 in SQLite angelegt (`Subject` & `Topic`).
  4. **Dossier & Widget-Verbindung:**
     - Der Stundenplan wird im Dossier *„Stundenplan & Organisation“* einsortiert.
     - Auf der Material-Karte erscheint ein Schnellzugriff-Button **„🗓️ Stundenplan“**, der direkt zum interaktiven Stundenplan-Widget navigiert.
     - Automatische Seeder-Migration korrigiert beim Start ältere Fehlablagen automatisch nach `sub_orga`.

---

## 7. Frontend-Architektur: Upload-Zentrale & Interaktive Fach-Mediathek

Die GoThea Benutzeroberfläche trennt Ingestion und Facharbeit klar voneinander:

### A. Dedizierter Upload-Hub (`#tab-uploads` / `📥 Upload & Eingang`)
* **Manuelle Upload-Dropzone:** Prominente Drag-&-Drop Fläche mit direktem Klick-Dialog (`<input type="file">`). Startet sofort die 2-Stufen Analyse mit Vorschau.
* **Netzwerk-Posteingang (Samba Finder Dropzone):** Integrierte Inbox-Karte mit Statusanzeige wartender Dateien, manueller Prüfung und 1-Klick-Verarbeitung (`POST /api/v1/inbox/process`).
* **Upload-Historie & Zuletzt importiert:** Zeigt chronologisch alle hochgeladenen Dokumente mit Metadaten (Fach, Thema, Seitenzahl, Dateigröße) und Schnellaktionen (Öffnen, Reader, Löschen).

### B. Interaktive Fach-Mediathek (`#tab-subject-detail`)
* **Dashboard-Navigation:** In der Hauptübersicht (`#tab-dashboard`) führt ein Klick auf eine Fach-Kachel (`.subject-card`) direkt in die jeweilige Fach-Detailseite.
* **Hero-Header:** Dynamisch gefärbt im Corporate Design des jeweiligen Schulfachs (Icon, Fachname, Klassenstufe, Lehrplan-Referenz).
* **Direktaktionen:**
  - *„🎨 Tafel für dieses Fach öffnen“*: Wechselt direkt zur Tafel und wählt das Fach vor.
  - *„➕ Dokument für dieses Fach hochladen“*: Öffnet das Upload-Modal mit automatischer Fach-Vorbelegung.
  - *„🔗 Dokumente zusammenführen“*: Ermöglicht das gezielte Verbinden mehrerer Materialien dieses Fachs.
* **Einklappbare Lehrplanthemen:** Liste aller im Rahmenlehrplan hinterlegten Themen für diese Klassenstufe mit RLP-Niveaustufen (`E`, `F`, etc.).
* **Fach-Materialien-Grid:** Alle Arbeitsblätter, Hefterseiten, Schulbücher und Tests gefiltert nach Fach mit Filter-Pills (Alle, Arbeitsblätter, Mitschriften, Schulbücher, Tests & Arbeiten, Vokabeln, Sonstiges).

---

## 8. Dokumenten-Reorganisation: Fächerzuordnung, Seitenverwaltung & PDF-Merge

Schüler und Eltern haben bei der Pflege der Schulunterlagen volle Flexibilität, um gescannte Arbeitsblätter nachträglich zu strukturieren:

### A. Dokument einem anderen Fach / Thema zuordnen (`PATCH /api/v1/materials/{id}`)
* **Modal:** `#modal-edit-material` (erreichbar über den Button `✏️ Ändern` auf jeder Material-Karte).
* **Felder:**
  * **Schulfach:** Beliebiges Schulfach wählbar. Bei Fachwechsel wird die Themenliste automatisch aktualisiert und ungültige alte Themenverknüpfungen werden bereinigt.
  * **Thema:** Zuordnung zu Lehrplanthemen des Fachs oder Freilassen.
  * **Titel & Dokumentart:** Anpassbar (siehe Dokumentarten oben).
  * **Zusammenfassung / Notiz:** Freitext für Lernhinweise oder Prüfungstermine.

### B. Seitenreihenfolge ändern & Einzelseiten löschen (`POST /api/v1/materials/{id}/reorder-pages`)
* **Modal:** `#modal-reorder-pages` (erreichbar über `📑 Seiten` auf Mehrseiten-Dokumenten und im In-App Dokumenten-Viewer `#modal-material-viewer`).
* **Funktionsweise:**
  * Visuelle Kachelansicht aller Seiten mit 150 DPI Retina-Thumbnails.
  * **Verschieben:** Buttons `◀` und `▶` verschieben Seiten interaktiv nach links/rechts.
  * **Löschen / Aussortieren:** `🗑️` entfernt unerwünschte Seiten (z. B. leere Scan-Rückseiten). Mindestens 1 Seite verbleibt stets.
  * **Zurücksetzen:** `↺ Zurücksetzen` stellt die Original-Reihenfolge mit einem Klick wieder her.
* **Backend-Implementierung:**
  * Verwendet `pypdf.PdfWriter` / `PdfReader` für atomare Neuanordnung der PDF-Seiten.
  * Annotations-Erhalt: Vorhandene Freihand-Notizen (`PageAnnotation`) werden unter Beachtung des Unique-Constraints auf die neuen Seitenzahlen umnummeriert (unter Verwendung temporärer Negativ-Indizes).
  * Cache-Invalidierung: Gerenderte Seiten im Cache (`data/<env>/cache/pages/{id}_p*`) werden gelöscht, sodass Folgeseiten sofort scharf und aktuell neu gerendert werden.

### C. Dokumente zusammenführen (`POST /api/v1/materials/merge`)
* **Modal:** `#modal-merge-materials` (erreichbar über die Buttons `🔗 Dokumente zusammenführen` im Upload-Hub und auf Fachseiten).
* **Workflow:**
  1. **Dokumentauswahl:** Multiselekt-Liste mit Fach-Filter; Auswahl beliebig vieler PDFs und Einzelbilder (JPEG/PNG).
  2. **Reihenfolge bestimmen:** Geordnete Liste der ausgewählten Dokumente mit `▲` und `▼` Verschiebe-Buttons sowie `✕` zum Entfernen.
  3. **Ziel-Metadaten:** Neuer Titel, Ziel-Fach, Ziel-Thema, Dokumentart und Checkbox *„Originaldokumente nach dem Verbinden löschen“* (standardmäßig aktiv).
* **Backend-Implementierung:**
  * Zusammenführung via `pypdf.PdfWriter`. Bilddateien (Fotos von Heftern) werden via `PIL.Image` verlustfrei in PDF-Seiten konvertiert und nahtlos angehängt.
  * Extrahierter Text und Chunks werden verkettet, die Quell-Materialien samt Page-Caches werden sauber aufgeräumt.
