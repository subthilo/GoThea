# 01.3 Umgebungen: Staging vs. Produktion

## Topologie der Umgebungen

Auf dem Raspberry Pi laufen ab sofort zwei strikt voneinander isolierte Instanzen:

```
┌────────────────────────────────────────────────────────────────────────┐
│  🟢 PRODUKTION (Port 8000)                                             │
│  - URL: http://192.168.1.135:8000                                      │
│  - Service: gothea.service (APP_ENV=production)                        │
│  - Datenbank: data/prod/app_data.db                                    │
│  - Status: Echte Daten, keine Destruktiv-Aktionen erlaubt              │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  🟡 STAGING / TESTUMGEBUNG (Port 8001)                                 │
│  - URL: http://192.168.1.135:8001                                      │
│  - Service: gothea-staging.service (APP_ENV=staging)                   │
│  - Datenbank: data/staging/app_data.db                                 │
│  - Status: Vollständige Test-Spielwiese, Dummy-Daten, 1-Klick-Reset    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment-Befehle

* `./deploy.sh staging`: Aktualisiert nur die Staging-Instanz (Port 8001).
* `./deploy.sh prod`: Aktualisiert nur die Produktions-Instanz (Port 8000).
* `./deploy.sh all` (oder `./deploy.sh`): Führt die Tests aus und aktualisiert beide Umgebungen.

---

## Sicherheitsmerkmale
1. **Dateisystem-Isolation:** `data/prod` und `data/staging` sind physikalisch getrennte Ordner.
2. **Schutz vor Überschreiben:** `deploy.sh` schließt den Ordner `data/` via `--exclude 'data/'` aus, sodass kein lokaler Stand jemals die Datenbanken auf dem Pi überschreibt.
3. **API-Schutz:** Der Endpoint `POST /api/v1/staging/reset` gibt in der Produktionsumgebung (`APP_ENV=production`) sofort einen `HTTP 403 Forbidden` zurück.
