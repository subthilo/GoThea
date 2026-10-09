# GoThea – Dokumentations-Index & Modulübersicht

Willkommen in der technischen Dokumentation von **GoThea (Multimodale Lernzentrale & KI-Tutor)**.

---

## 📚 Inhaltsverzeichnis

### [01. Systemarchitektur & Infrastruktur](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/01_architecture/overview.md)
* **[01.1 Systemübersicht & Topologie](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/01_architecture/overview.md):** Lokaler Raspberry-Pi-Betrieb (Edge), Client-Anbindung im WLAN, Migrationspfad zur Cloud.
* **[01.2 Datenbankschema & DDL](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/01_architecture/database_schema.md):** Tabellenstrukturen, Primär-/Fremdschlüssel, Indizes, SQLite WAL-Modus.
* **[01.3 Sicherheit & Deployment](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/01_architecture/deployment_and_security.md):** Lokales HTTPS mit Caddy, AES-256-GCM Verschlüsselung für Zugangsdaten, Offline-Resilienz.

### [02. Fach- und Servicemodule](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/profile_and_curriculum.md)
* **[02.1 Schülerprofil & Brandenburger Rahmenlehrplan](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/profile_and_curriculum.md):** Multi-Grade Support (Klassen 1–13), Niveaustufen A–H.
* **[02.2 Lernplan- & Countdown-Engine](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/planner_and_countdown.md):** Mathematische Vorbereitungsfenster $N(k,g)$, Zeitbudgets $B(k,g)$, Phasenallokation, Sperrtage.
* **[02.3 IServ-Connector](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/iserv_connector.md):** CalDAV-Terminsync, WebDAV-Dateisync, HTTP-Session-Crawler für Aufgaben.
* **[02.4 Material-Ingestion & RAG](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/material_ingestion.md):** 2-Stufen Human-in-the-Loop Upload, Vorab-Analyse, semantisches Chunking, Vektorsuche.
* **[02.5 Whiteboard Engine](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/whiteboard_engine.md):** Latenzarme Apple-Pencil-Erfassung, Vektoren, Diff-Snapshots, Overlays.
* **[02.6 Sokratischer KI-Tutor & Audio](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/02_modules/socratic_tutor.md):** Pädagogischer Prompt-Governor, Leitfragen-System, Streaming TTS & Barge-In.

### [03. Schnittstellen-Spezifikationen](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/03_api_specs/rest_api.md)
* **[03.1 REST API Spezifikation](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/03_api_specs/rest_api.md):** Alle HTTP-Endpunkte mit Request/Response-DTOs.
* **[03.2 WebSocket Protokoll](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/03_api_specs/websocket_protocol.md):** Event-Typen für Whiteboard-Synchronisation und Audio-Streaming.

### [04. Testberichte](file:///Users/thilo/Library/CloudStorage/SynologyDrive-DatenSync/Repos/GoThea/docs/04_test_reports/)
* Iterationsberichte mit Testergebnissen, Code Coverage und Prüfprotokollen.

---

## 🗺️ Umsetzungs-Status (Roadmap)

| Meilenstein | Beschreibung | Status | Tests |
| :--- | :--- | :---: | :---: |
| **M0: Setup** | Raspberry Pi Deployment, SSH, PWA-Grundgerüst | ✅ Abgeschlossen | Manuell (OK) |
| **M1: Core DB & Taxonomie** | SQLite WAL, User, Fächer & Themen (7. Klasse BB), REST API | 🔄 In Arbeit | In Vorbereitung |
| **M2: Lernplan-Engine** | Countdown-Algorithmus, Prüfungen, Phasen, Sperrtage | ⏳ Geplant | - |
| **M3: IServ-Connector** | CalDAV, WebDAV, AES-256 Vault | ⏳ Geplant | - |
| **M4: Material-Upload** | 2-Stufen Human-in-the-Loop Ingestion | ⏳ Geplant | - |
| **M5: Whiteboard Engine** | iPad Canvas, PointerEvents, Overlays | ⏳ Geplant | - |
| **M6: KI-Tutor & Audio** | Sokratischer Governor, Vision, Streaming TTS | ⏳ Geplant | - |
