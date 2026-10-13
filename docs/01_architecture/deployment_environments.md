# 01.3 Umgebungen: Staging vs. Produktion

## Topologie der Umgebungen

Auf dem Raspberry Pi laufen ab sofort zwei strikt voneinander isolierte Instanzen:

```
┌────────────────────────────────────────────────────────────────────────┐
│  🟢 PRODUKTION (Port 8000)                                             │
│  - URL: http://192.168.1.135:8000                                      │
│  - Service: gothea.service (APP_ENV=production)                        │
│  - Datenbank: data/prod/app_data.db                                    │
│  - Material-Speicher: data/prod/materials/                             │
│  - Inbox / Dropzone: inbox/prod/                                       │
│  - Status: Echte Daten, keine Destruktiv-Aktionen erlaubt              │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  🟡 STAGING / TESTUMGEBUNG (Port 8001)                                 │
│  - URL: http://192.168.1.135:8001                                      │
│  - Service: gothea-staging.service (APP_ENV=staging)                   │
│  - Datenbank: data/staging/app_data.db                                 │
│  - Material-Speicher: data/staging/materials/                         │
│  - Inbox / Dropzone: inbox/staging/                                    │
│  - Status: Vollständige Test-Spielwiese, Dummy-Daten, 1-Klick-Reset    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Inbox- & Dropzone-Isolation (Samba)

Um das Ablegen von Dokumenten über das Heimnetzwerk (Mac Finder / Windows Explorer / iPad Dateien-App) so einfach wie möglich zu machen, sind die Eingangsordner nach Umgebungen getrennt:

* **Staging-Dropzone:** `/home/pi/GoThea/inbox/staging/`
  * Hier werden Rohdokumente zum risikofreien Testen der automatischen Erkennung abgelegt.
* **Produktions-Dropzone:** `/home/pi/GoThea/inbox/prod/`
  * Für den Produktivalltag mit Theas echten Unterlagen.
* **Fehler-Quarantäne:**
  * Schlägt die Verarbeitung einer Datei fehl (z. B. 0 Bytes, beschädigtes PDF), wird sie nach `inbox/<env>/_errors/` verschoben und ein Fehlerbericht `[dateiname].error.txt` erzeugt. Die Verarbeitung bricht nicht ab.

### Empfohlene Samba-Freigabe (`/etc/samba/smb.conf`):
```ini
[GoThea-Inbox-Staging]
   path = /home/pi/GoThea/inbox/staging
   read only = no
   guest ok = yes
   create mask = 0666
   directory mask = 0777

[GoThea-Inbox-Prod]
   path = /home/pi/GoThea/inbox/prod
   read only = no
   guest ok = yes
   create mask = 0666
   directory mask = 0777
```

---

## Umgebungsvariablen (`.env`)

Auf dem Raspberry Pi liegt unter `/home/pi/GoThea/.env` die Konfiguration für externe APIs (wird durch `deploy.sh` geschützt und nie überschrieben):
```bash
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini
```
* **`OPENAI_MODEL=gpt-4o-mini`**: Standardmodell für die multimodale Vorverarbeitung & Titelerkennung (Vision & Text).
* Für den interaktiven Tutor (Whiteboard-Lernbegleitung) werden die spezialisierten Modelle `gpt-6-luna` (Streaming-Tutor) und `gpt-6.1-sol` (Tafel-Diagnostik) angesteuert.

---

## Deployment-Befehle

* `./deploy.sh staging`: Aktualisiert nur die Staging-Instanz (Port 8001).
* `./deploy.sh prod`: Aktualisiert nur die Produktions-Instanz (Port 8000).
* `./deploy.sh all` (oder `./deploy.sh`): Führt die Tests aus und aktualisiert beide Umgebungen.

---

## Sicherheitsmerkmale
1. **Dateisystem-Isolation:** `data/prod`, `data/staging`, `inbox/prod` und `inbox/staging` sind physikalisch getrennte Ordner.
2. **Schutz vor Überschreiben:** `deploy.sh` schließt `data/`, `inbox/` und `.env` aus, sodass kein lokaler Teststand jemals die Daten auf dem Pi überschreibt.
3. **API-Schutz:** Der Endpoint `POST /api/v1/env/staging/reset` gibt in der Produktionsumgebung (`APP_ENV=production`) sofort einen `HTTP 403 Forbidden` zurück.
