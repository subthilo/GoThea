# 02.3 IServ-Connector (Schnittstellen ohne API-Key)

## 1. Übersicht

Schulen vergeben aus Sicherheitsgründen fast nie offizielle API-Keys an Schüler oder Eltern. IServ basiert jedoch auf offenen Standardprotokollen, die für jeden Schüler-Account ab Werk freigeschaltet sind.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ISERV-SCHNITTSTELLEN-KANÄLE                     │
│                                                                        │
│  Kanal 1: CalDAV (RFC 4791)                                            │
│  - URL: https://<schule>.iserv.de/caldav/                              │
│  - Zweck: Klassenarbeitskalender & Termine                             │
│  - Auth: HTTP Basic Auth                                               │
│                                                                        │
│  Kanal 2: WebDAV (RFC 4918)                                            │
│  - URL: https://<schule>.iserv.de/webdav/                              │
│  - Zweck: Unterrichtsdateien aus Klassen- & Fachordnern                │
│  - Auth: HTTP Basic Auth                                               │
│                                                                        │
│  Kanal 3: HTTP Web-Session Client (Python httpx)                       │
│  - URL: https://<schule>.iserv.de/iserv/app/login                      │
│  - Zweck: Modul "Aufgaben" (Hausaufgaben, Fristen, Lehrer-PDFs)        │
│  - Auth: Session-Cookie & CSRF-Token                                   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Kanäle im Detail

### Kanal 1: CalDAV (Prüfungstermine)
* Ruft VEvents aus dem Klassen- und Schulkalender ab.
* Scannt den Betreff nach Signalwörtern (*„Klassenarbeit“*, *„Test“*, *„LK“*, *„Klausur“*).
* Duplikaterkennung über die eindeutige `external_uid` (CalDAV UID). Aktualisiert Termine automatisch bei Terminverschiebungen der Lehrkraft.

### Kanal 2: WebDAV (Unterrichtsmaterialien)
* Scannt Ordner wie `/Gruppen/<Klasse>` oder Fachordner (`/Gruppen/Bio_7`).
* Erkennt neue oder modifizierte Dateien via `ETag`.
* Lädt neue PDFs automatisch herunter und übergibt sie an die Vorab-Klassifizierung der Material-Ingestion.

### Kanal 3: Aufgaben-Modul Crawler
* Authentifiziert sich mit den Schülerdaten am Webinterface.
* Fragt die internen JSON-Endpunkte ab (`/iserv/exercise/api/exercises`).
* Extrahiert Abgabefristen und lädt beigefügte Aufgabenblätter herunter.

---

## 3. Schutzmechanismen & Polling-Frequenz
* **Schonendes Polling:** Der automatische Abgleich erfolgt standardmäßig alle 60 Minuten (werktags 07:00 – 18:00 Uhr), um Schulserver und Brute-Force-Filter nicht zu triggern.
* **Manueller Sync:** Im Frontend steht jederzeit der Button *„Jetzt mit IServ synchronisieren“* bereit.
