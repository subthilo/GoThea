# 🎓 GoThea – Multimodale Lernzentrale & Sokratischer KI-Tutor

[![Test Suite](https://img.shields.io/badge/Tests-76%2F76%20Passed-success?style=flat-square&logo=pytest)](docs/04_test_reports/iteration_05_timetable_and_organization.md)
[![Code Coverage](https://img.shields.io/badge/Coverage-86%25-brightgreen?style=flat-square)](docs/04_test_reports/iteration_05_timetable_and_organization.md)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square&logo=python)](backend/)
[![Platform](https://img.shields.io/badge/Hardware-Raspberry%20Pi%204%2F5%20%26%20iPadOS-orange?style=flat-square&logo=raspberrypi)](docs/01_architecture/overview.md)
[![License](https://img.shields.io/badge/License-Proprietary-lightgrey?style=flat-square)](#)

> **GoThea** ist eine adaptive, multimodale Lernumgebung für Schülerinnen und Schüler (Initialkonfiguration: 7. Klasse Gymnasium, Land Brandenburg; erweiterbar auf Klassen 1 bis 13).  
> Sie verbindet ein intelligentes, countdownbasiertes Lernplansystem mit einem interaktiven, sokratischen KI-Lernbegleiter auf einem hardwarebeschleunigten iPad-Whiteboard sowie einem vollintegrierten Untis-Stundenplan-Widget mit A-/B-Wochen Turnus.

---

## 📑 Inhaltsverzeichnis

1. [Vision & Kernphilosophie](#-vision--kernphilosophie)
2. [Der 5-Phasen Interaktions- und Diagnose-Kreislauf](#-der-5-phasen-interaktions--und-diagnose-kreislauf)
3. [Hauptfunktionen & Architektur-Highlights](#-hauptfunktionen--architektur-highlights)
   * [1. Multimodales iPad Whiteboard](#1-multimodales-ipad-whiteboard-apple-pencil--retina)
   * [2. Smarte Material-Ingestion & Vorlagen](#2-smarte-material-ingestion--vorlagen-in-app-viewer)
   * [3. Countdown- & Lernplan-Engine](#3-altersadaptiver-countdown--lernplan-algorithmus)
   * [4. Stundenplan-Widget & Organisation (Untis 7D & A/B-Wochen)](#4-stundenplan-widget--organisation-untis-7d--ab-wochen)
   * [5. Schülerprofil & Brandenburger Lehrplan](#5-schülerprofil--brandenburger-lehrplan-rlp-a-h)
   * [6. Staging- vs. Produktions-Umgebung](#6-staging--vs-produktions-umgebung-auf-dem-pi)
4. [Technologie-Stack](#-technologie-stack)
5. [Repository- & Verzeichnisstruktur](#-repository--verzeichnisstruktur)
6. [Installation & Lokale Entwicklung](#-installation--lokale-entwicklung)
7. [Deployment auf dem Raspberry Pi](#-deployment-auf-dem-raspberry-pi)
8. [Projekt-Roadmap & Status](#-projekt-roadmap--status)
9. [Weiterführende Dokumentation](#-weiterführende-dokumentation)

---

## 💡 Vision & Kernphilosophie

Konventionelle Lern-Apps liefern oft nur statische Quizze oder spucken als Chatbot fertige Lösungen aus. **GoThea verfolgt einen radikal anderen Ansatz:**

1. **Sokratische Führung statt Lösungs-Spoiler:**  
   Die KI verrät niemals die fertige Lösung oder den nächsten Rechenschritt. Sie stellt altersgerechte, präzise Leitfragen, würdigt gelungene Teilschritte und motiviert zum eigenständigen Nachdenken.
2. **Die Tafel als gemeinsame Arbeitsfläche:**  
   Schüler arbeiten natürlich mit dem Apple Pencil – genau wie auf Papier. Sie rechnen Aufgaben auf der Tafel oder füllen direkt die Lücken hinterlegter Schul-Arbeitsblätter aus. Die KI beobachtet den Lösungsweg in Echtzeit über ein transparentes Overlay.
3. **Schritt-für-Schritt Diagnose:**  
   Die KI analysiert nicht nur, ob das Endergebnis stimmt, sondern liest jeden Zwischenschritt Zeile für Zeile und lokalisiert exakt den ersten Denkfehler.
4. **Wissenslücken gezielt schließen (Knowledge Tracing):**  
   Fehlermuster werden systematisch erfasst (`competency_records`). Die Lernplan-Engine wählt daraufhin maßgeschneiderte Übungsaufgaben aus, die genau diese Schwachstelle isoliert trainieren.

---

## 🔄 Der 5-Phasen Interaktions- und Diagnose-Kreislauf

Das Herzstück der Interaktion zwischen Schüler und KI auf dem Whiteboard:

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
│  - Erkennt Zwischenschritte, Denkansätze und den exakten ersten Fehler           │
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

### Die 3-Stufige Hilfestellungs-Hierarchie (Scaffolding):
* **Stufe 1 (Orientierung):** *„Schau dir in der zweiten Zeile links den Term vor der Klammer an.“*
* **Stufe 2 (Konzept & Regel):** *„Welche Vorzeichenregel gilt, wenn ein Minus vor einer Klammer steht?“*
* **Stufe 3 (Konkreter Zwischenschritt):** *„Rechne zuerst nur $-2 \cdot (-3)$. Was ergibt das?“*

---

## 🚀 Hauptfunktionen & Architektur-Highlights

### 1. Multimodales iPad Whiteboard (Apple Pencil & Retina)
* **Latenzarmes Zeichnen:** Hardwarebeschleunigtes HiDPI Retina-Rendering (`devicePixelRatio = 2.0`), Bezier-Glättung (`quadraticCurveTo`) und Druckstufenerfassung (`e.pressure`).
* **100% Gestenschutz:** Unbedingtes Abfangen nativer iOS-Safari-Gesten (kein Aufpoppen des störenden Menüs **„Teilen ...“**, Lupen-Unterdrückung).
* **Palm Rejection (Handflächenerkennung):** Umschaltbarer Stiftmodus ignoriert Handballen-Touches beim Schreiben.
* **Dualer Radierer:** 
  * 🧹 *Pixel-Radierer* (`destination-out`) für feines Freiradieren.
  * 🎯 *Objekt-Radierer* (Vektordistanz-Berechnung $dist(P, \overline{AB})$) zum Löschen ganzer Striche mit einem Fingertipp.
* **Infinite Canvas & 1:1 Zwei-Finger-Scrollen:** Unbegrenztes vertikales Mitschreiben, hardwarebeschleunigtes Verschieben und sanfte kubische Rückkehranimation zum Anfang.
* **Pinch-to-Zoom (100% – 350%) & Strichstärken-Skalierung:**
  * Stufenloser Zwei-Finger-Zoom oder Toolbar-Buttons (`➖`, `100%`, `➕`).
  * **Inverse Strichstärken-Anpassung ($\text{width} = \frac{\text{baseWidth}}{scale}$):** Erlaubt sauberes, feines Eintragen von Zahlen und Wörtern in enge Arbeitsblatt-Lücken bei 2.5x Zoom.
* **5-Ebenen Z-Index Schichten-Architektur:**
  * `z-index: 1`: `#wb-doc-underlay` (Arbeitsblatt-Vorlage als mehrseitiger DIN-A4-Kartenstapel).
  * `z-index: 2`: `#wb-canvas` (Schüler-Schreibebene direkt **auf** dem Arbeitsblatt).
  * `z-index: 5`: `#wb-overlay` (KI-Tutor Hinweisboxen und Markierungen).
  * `z-index: 8`: `#wb-doc-topbar` (Vorlagenleiste mit Schließen-Button).
  * `z-index: 10`: `#wb-toolbar` (schwebende iPad-Werkzeugleiste).
* **Radierer-Schutz (Eraser Immunity):** Weder der Pixel- noch der Objektradierer noch „Tafel leeren“ können das hinterlegte Arbeitsblatt beschädigen – radiert wird ausschließlich Schülertinte.

### 2. Smarte Material-Ingestion & Vorlagen (In-App Viewer)
* **Native iPadOS Safari Uploads:** Direkter Zugriff auf die iOS *Dateien-App* (iCloud Drive, Schul-Cloud, USB), die *Fotomediathek* und die *iPad-Kamera* zum Abfotografieren physischer Hefterseiten.
* **Automatisierte Samba-Inbox / Dropzone (`inbox/staging/` & `inbox/prod/`):**
  * Dokumente (PDFs, Scans) einfach über das Netzwerk in die Inbox werfen.
  * Ein Klick auf **„📥 Jetzt einsortieren“** verarbeitet ganze Dokumentenstapel atomar.
* **Multimodale KI-Inhaltsanalyse & Renaming (`document_analyzer.py`):**
  * Erkennt auch bei unleserlichen Scans ohne Text (`Hebel.pdf`, `fgjg.pdf`) per **Vision (`gpt-4o-mini`)** das Schulfach, das konkrete Lehrplanthema und die Dokumentart.
  * Ersetzt kryptische Dateinamen durch normierte Namen (`Fach_Thema_Art_Titel.pdf`) und vergibt saubere inhaltliche Titel.
  * Legt neue Themen im Lehrplan automatisch an.
* **Digitale Mappenführung (`dossiers`):**
  * Automatische Sortierung in Übungsmappen, Fachhefter, Lehrbücher und Testsammlungen.
  * Filterung im Materialien-Tab nach Dokumentarten (*📄 Arbeitsblätter*, *📁 Hefter & Notizen*, *📚 Schulbücher*, *📝 Tests & Arbeiten*).
* **2-Stufen Human-in-the-Loop Pipeline:**
  1. *Stufe 1:* Schnelle Vorab-Analyse via Vision/Text (schlägt Fach, Thema, Titel und Dokumentart vor).
  2. *Stufe 2:* Interaktiver Bestätigungsdialog mit manueller Korrekturmöglichkeit.
* **In-App Dokumenten-Viewer (Modal Popup):**
  * Verhindert das Blockieren durch Safaris Pop-Up-Blocker.
  * Multi-Page-Paginierung (`Seite X von Y`).
  * One-Tap-Button **„🎨 Auf Tafel bearbeiten“** lädt das Dokument nahtlos als Vorlage in das Whiteboard.
* **Dual-Engine High-Performance Rendering:**
  * *Linux / Raspberry Pi:* System-natives Poppler `pdftoppm` (< 50 ms pro Seite, nativer C-Code, vorinstalliert, minimaler RAM-Bedarf, keine C++-Build-Timeouts auf ARM).
  * *macOS / Entwicklerrechner:* Automatischer Fallback auf `PyMuPDF` (`fitz`).

### 3. Altersadaptiver Countdown- & Lernplan-Algorithmus
* **Mathematisches Vorbereitungsfenster $N(k,g)$:**
  * 7. Klasse Gymnasium: 5 Tage Vorbereitung für Tests, 10 Tage für Klassenarbeiten.
* **Tägliches Zeitbudget $B(k,g)$:**
  * 20 Min. für Tests, 25 Min. für Klassenarbeiten (verhindert Überlastung).
* **3-Phasenallokation:**
  * *Phase 1:* Grundlagen & Verstehen (die ersten 40% der Tage).
  * *Phase 2:* Aktives Üben & Vertiefen.
  * *Phase 3:* Generalprobe (letzter Tag vor der Arbeit).
  * *Prüfungstag:* Ruhemodus (*„Heute musst du nicht mehr lernen. Du schaffst das!“*).
* **Sperrtage-Manager:** Flexible Tage-Auszeit („Ganzer Tag frei“ oder „Fach frei“). Der Countdown kompensiert Ausfalltage automatisch.

### 4. Stundenplan-Widget & Organisation (Untis 7D & A/B-Wochen)
* **Interaktives Wochenraster (`#tab-timetable`):**
  * Zeigt Theas kompletten Stundenplan (Klasse 7D, Humboldt-Gymnasium Eichwalde) in einer maßgeschneiderten Wochenansicht (Montag bis Freitag, 1. bis 8. Stunde inkl. geteilter 6. Stunde).
  * Jede Unterrichtsstunde zeigt Fach-Icon, Kürzel & Fachname, Raumnummer, Lehrerkürzel, Doppelstunden-Markierung und Beginn/Ende.
* **A-/B-Wochen Turnus (Alternating Weeks):**
  * Berechnet automatisch die Kalenderwoche (ungerade = A-Woche, gerade = B-Woche) mit manuellem Umschalter im Header.
  * Berücksichtigt spezifische Stundenplan-Wechsel (z. B. Montag 5./6.1 Std: Sport in Turnhalle `gewo` bei Frau DÜCK in A-Woche vs. Englisch in Raum 104 bei Frau SCHD in B-Woche).
* **Tages-Widget auf dem Dashboard:**
  * Kompakte Übersicht „Dein Schultag heute“ direkt beim Öffnen der App (am Wochenende mit Vorschau auf Montag).
* **Deep-Links & Vernetzung:**
  * Klick auf einen Unterrichts-Slot öffnet die Detailkarte mit One-Tap-Aktionen:
    * 🎨 *„Auf Tafel öffnen“* (startet Whiteboard mit Fach-Vorauswahl)
    * 📚 *„Materialien zum Fach“* (springt in die gefilterte Mediathek)
    * 📄 *„Original-Scan ansehen“* (öffnet den eingescannten Stundenplan im Vollbild-Viewer)
* **Auto-Routing ins Fach „Organisation“ (`sub_orga`):**
  * Stundenpläne werden beim Hochladen über beliebige Kanäle (Upload, Samba-Dropzone) automatisch als Dokumentart `Stundenplan` erkannt und unverrückbar im Fach *Organisation* und Dossier *Stundenplan & Organisation* abgelegt (Verhinderung versehentlicher Fehlablagen in Einzelfächern).

### 5. Schülerprofil & Brandenburger Lehrplan (RLP A–H)
* **Klassenstufen 1 bis 13:** Dynamische Kalibrierung von Fächern, Themen und Niveaustufen.
* **Brandenburger Rahmenlehrplan (RLP):** Niveaustufe E für Klasse 7 Gymnasium.
* **Dynamische Taxonomie:** Vollständige CRUD-Schnittstelle für Fächer (Farben, Icons) und Themen.

### 6. Staging- vs. Produktions-Umgebung auf dem Pi
* **Port 8000 (Produktion):** Persistente Echtdaten der Schülerin (`data/prod/app_data.db`, `inbox/prod`).
* **Port 8001 (Staging):** Isolierte Testumgebung (`data/staging/app_data.db`, `inbox/staging`) mit Ein-Klick-Reset-Funktion und Dummy-Daten-Generierung.

---

## 🛠️ Technologie-Stack

| Bereich | Technologie | Beschreibung / Zweck |
| :--- | :--- | :--- |
| **Backend Framework** | **Python 3.9+ / FastAPI** | Asynchrones, hochperformantes REST- und WebSocket-Backend |
| **KI / Multimodal Ingestion** | **OpenAI `gpt-4o-mini` (Vision)** | Schnelle Bild- & Textanalyse von Scans, Titelerkennung, JSON-Mode |
| **KI / Didaktischer Tutor** | **`gpt-6-luna` & `gpt-6.1-sol`** | Sokratischer Live-Tutor (iPad Whiteboard / Audio) & Tafel-Diagnose |
| **Datenbank** | **SQLite (WAL-Modus)** | Lokale Edge-Datenbank, latenzarm, ausfallsicher, zero-maintenance |
| **ORM** | **SQLAlchemy 2.0** | Typisierte Datenbankmodelle (`timetable_slots`, `dossiers`, `materials`, `taxonomy`) |
| **PDF Rendering** | **Poppler `pdftoppm`** | Natives C-Tool auf Linux/Pi für ultraschnelles Seiten-Rendering |
| **Frontend Core** | **HTML5 / Vanilla JavaScript (ES6+)** | Leichtgewichtig, frameworklos für maximale iPadOS-Safari-Performance |
| **Styling** | **Modern Vanilla CSS** | HSL-Farbsystem, dynamisches Theme, iOS Human Interface Design |
| **Testsuite** | **pytest / pytest-cov** | 76 Unit- & Integrationstests mit 86% Code Coverage |
| **Deployment** | **systemd & Bash (`deploy.sh`)** | Dual-Service-Management auf Raspberry Pi OS (Staging & Prod) |

---

## 📂 Repository- & Verzeichnisstruktur

```text
GoThea/
├── backend/
│   ├── app/
│   │   ├── models/            # SQLAlchemy ORM (User, Test, Material, Whiteboard, Taxonomy)
│   │   ├── routers/           # REST-Endpunkte (Profile, Planner, Materials, Whiteboard, Env)
│   │   ├── schemas/           # Pydantic DTOs & Validierung
│   │   ├── services/          # Business-Logik (Planner, Material-Ingestion, Seeder)
│   │   ├── config.py          # Umgebungs-Konfiguration (Prod vs. Staging)
│   │   └── database.py        # SQLite Engine & Session-Handling
│   ├── main.py                # FastAPI-Applikation & Lifespan Event-Handling
│   └── requirements.txt       # Python-Abhängigkeiten (bereinigt für ARM 32/64-Bit)
├── frontend/
│   ├── index.html             # Single-Page-App Shell & Tab-Navigation
│   ├── style.css              # Globales Styling & iPad-Optimierungen
│   ├── app.js                 # App-State, Router, Material-Viewer & Modals
│   └── whiteboard.js          # Canvas-Engine, Touch/Pencil, Zoom, Underlay & Tools
├── docs/                      # Vollständige modulare technische Dokumentation
│   ├── 01_architecture/       # Systemübersicht, Datenbank-DDL, Security
│   ├── 02_modules/            # Detailkonzepte (Whiteboard, Planner, Materials, Tutor)
│   ├── 03_api_specs/          # REST API & WebSocket Spezifikationen
│   ├── 04_test_reports/       # Iterative Testberichte & Code Coverage
│   ├── index.md               # Dokumentations-Index
│   └── systemarchitektur_gothea.md # Umfassendes Gesamtdokument
├── tests/
│   ├── integration/           # Integrationstests für alle REST-APIs & WebSockets
│   ├── unit/                  # Unit-Tests für Algorithmen & ORM-Modelle
│   └── conftest.py            # Pytest Fixtures & Test-Datenbank Setup
├── deploy.sh                  # One-Click Deployment-Script für Raspberry Pi
├── gothea.service             # Systemd-Konfiguration für Produktion (Port 8000)
├── gothea-staging.service     # Systemd-Konfiguration für Staging (Port 8001)
├── pytest.ini                 # Test-Konfiguration
└── README.md                  # Dieses Dokument
```

---

## 💻 Installation & Lokale Entwicklung

### 1. Voraussetzungen
* Python 3.9 oder neuer
* Git
* *Optional (für PDF-Vorschau):* `poppler-utils` (macOS: `brew install poppler`, Linux: `sudo apt install poppler-utils`)

### 2. Lokales Setup
```bash
# Repository klonen
git clone https://github.com/subthilo/GoThea.git
cd GoThea

# Virtuelle Umgebung erstellen und aktivieren
python3 -m venv .venv
source .venv/bin/activate

# Abhängigkeiten installieren
pip install -r backend/requirements.txt
```

### 3. Tests ausführen
```bash
# Gesamte Testsuite mit Coverage-Report ausführen
pytest --cov=backend/app tests/ -v
```

### 4. Lokalen Entwicklungsserver starten
```bash
# Server mit Auto-Reload starten
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Anschließend die Web-App im Browser öffnen: **`http://localhost:8000`**

---

## 🍓 Deployment auf dem Raspberry Pi

Das Projekt verfügt über ein automatisiertes Deployment-Script (`deploy.sh`), das vor jedem Rollout lokal die Testsuite erzwingt und den Code anschließend per SSH/rsync auf den Raspberry Pi überträgt.

```bash
# Beide Umgebungen (Produktion & Staging) aktualisieren
./deploy.sh all

# Nur die Staging-Testumgebung aktualisieren
./deploy.sh staging

# Nur die Produktionsumgebung aktualisieren
./deploy.sh prod
```

### Zugriff im Heimnetzwerk:
* 🟢 **Produktion (Echtdaten):** `http://192.168.1.135:8000`
* 🟡 **Staging (Spielwiese / Reset):** `http://192.168.1.135:8001`

---

## 🗺️ Projekt-Roadmap & Status

| Meilenstein | Beschreibung | Status | Qualitätssicherung |
| :--- | :--- | :---: | :---: |
| **M0: Setup & Pi-Host** | Raspberry Pi Deployment, Dual-Port Setup (8000/8001), systemd | ✅ Abgeschlossen | Manuell verifiziert |
| **M1: Core DB & Taxonomie** | SQLite WAL, User, Fächer & Themen (7. Klasse BB), Staging/Prod | ✅ Abgeschlossen | 15 Tests (92% Coverage) |
| **M2: Lernplan-Engine** | Altersadaptiver Countdown, Phasenallokation, Sperrtage | ✅ Abgeschlossen | 23 Tests (92% Coverage) |
| **M3: Whiteboard Engine** | iPad Retina Canvas, Apple Pencil, Zoom (100–350%), Underlay | ✅ Abgeschlossen | 32 Tests (93% Coverage) |
| **M4: Material-Upload** | 2-Stufen Human-in-the-Loop Ingestion, Poppler-Rendering, Viewer | ✅ Abgeschlossen | 43 Tests (90% Coverage) |
| **M5: Stundenplan & Orga** | Untis 7D Raster, A/B-Wochen, Dashboard-Widget, Auto-Routing | ✅ Abgeschlossen | 76 Tests (86% Coverage) |
| **M6: IServ-Connector** | CalDAV Terminabgleich, WebDAV Materialien, AES-256 Vault | ⏳ Geplant | - |
| **M7: Sokratischer KI-Tutor** | Vision-Diagnose, Scaffolding Overlays, Knowledge Tracing | ⏳ Geplant | - |

---

## 📖 Weiterführende Dokumentation

Die vollständige technische Dokumentation ist modular im Ordner [`docs/`](docs/) gegliedert:

* **[Dokumentations-Index](docs/index.md):** Komplette Modulübersicht und Lesereihenfolge.
* **[01.1 Systemübersicht & Topologie](docs/01_architecture/overview.md):** Edge-Architektur auf dem Raspberry Pi.
* **[01.2 Datenbankschema & DDL](docs/01_architecture/database_schema.md):** Relationale Tabellen, Constraints und Indizes (`timetable_slots`).
* **[02.2 Lernplan- und Countdown-Engine](docs/02_modules/planner_and_countdown.md):** Mathematische Formeln $N(k,g)$ und $B(k,g)$.
* **[02.4 Smarte Material-Ingestion](docs/02_modules/material_ingestion.md):** Human-in-the-Loop Workflow, Auto-Routing nach `sub_orga`.
* **[02.5 Multimodale Whiteboard Engine](docs/02_modules/whiteboard_engine.md):** Low-Latency iPad Canvas, Gestenschutz, Zoom & Ebenen.
* **[02.6 Sokratischer KI-Tutor](docs/02_modules/socratic_tutor.md):** Leitfragen, Handschrift-Diagnose und Knowledge Tracing.
* **[02.7 Stundenplan & Organisation](docs/02_modules/timetable_widget.md):** Natives Wochenraster, Untis 7D, A/B-Wochen Switcher & Deep-Links.
* **[03.1 REST API Spezifikation](docs/03_api_specs/rest_api.md):** Interaktive HTTP-Endpunkte und DTOs (inkl. Section 7 Stundenplan).
* **[04.5 Testbericht Iteration 05](docs/04_test_reports/iteration_05_timetable_and_organization.md):** Detaillierter Testlauf & Coverage-Matrix (76 Tests, 100% Passed).
