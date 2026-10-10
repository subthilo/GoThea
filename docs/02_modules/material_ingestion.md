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

## 5. High-Performance Rendering Engine (Dual-Engine Architektur)

Um Dokumente auch auf ressourcenschonender Edge-Hardware (Raspberry Pi 4, 32-Bit ARM `armv7l`) ohne Speicherengpässe oder lange Ladezeiten bereitzustellen:

* **Primäre Engine (Linux & Raspberry Pi): System-natives Poppler `pdftoppm`**
  * Verwendet `/usr/bin/pdftoppm` mit den Parametern `-png -r 150 -f {page} -l {page} -singlefile`.
  * Ausführung in nativer C-Performance (< 50 ms pro Seite), extrem geringer RAM-Footprint.
  * Keine C++ Kompilierung beim `pip install`-Schritt (verhindert Build-Timeouts auf 32-Bit ARM).
* **Fallback Engine (macOS & Entwicklung): PyMuPDF (`fitz`)**
  * Wird automatisch genutzt, falls `pdftoppm` nicht im Pfad gefunden wird (z. B. auf lokalen Entwickler-Macs).
* **Bild-Direktauslieferung:**
  * Hochgeladene Fotos (PNG/JPEG) von Heftern werden ohne Umwandlung direkt mit entsprechendem MIME-Type ausgeliefert.
* **Optimierte Abhängigkeiten:**
  * `pymupdf` wurde aus `requirements.txt` entfernt, sodass der Raspberry Pi schlank und ohne schwere Toolchains deployt werden kann.

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

### Modell-Allokation: Vorverarbeitung vs. Didaktischer Tutor

* **`gpt-4o-mini` (Vorverarbeitung / Ingestion):**
  * Aufgaben: Text- und Bild-OCR, Inhaltsanalyse von Deckblättern, Fächerzuordnung, Titelerstellung, JSON-Normalisierung.
  * Vorteile: Sehr hohe Ausführungsgeschwindigkeit, fehlerfreies JSON-Schema, minimale Token-Kosten.
* **`gpt-6-luna` & `gpt-6.1-sol` (Lernbegleiter & Didaktik):**
  * Aufgaben: Sokratischer Live-Tutor auf dem iPad Whiteboard, latenzarme Audio-Unterstützung (< 500 ms Streaming), pixelgenaue Fehleranalyse von Rechenschritten und Schülerskizzen.

