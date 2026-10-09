# 01.1 Systemübersicht & Topologie

## 1. Lokale Edge-Topologie (Raspberry Pi)

GoThea ist als lokale Webapplikation konzipiert, die primär auf einem **Raspberry Pi 4 oder 5** im Heimnetzwerk ausgeführt wird. 

```
                               HEIMNETZWERK (WLAN / mDNS)
┌────────────────────────────────────────────────────────────────────────┐
│  Client: iPad (Safari im PWA-Modus / Web-App)                          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTPS (Port 443 / 8000)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Raspberry Pi (Raspberry Pi OS)                                        │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Webserver / Reverse Proxy (FastAPI Uvicorn / Caddy)              │  │
│  └──────────────┬──────────────────────────────────┬────────────────┘  │
│                 │ REST API (/api/*)                │ WebSocket (/ws/*) │
│                 ▼                                  ▼                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Python Backend (FastAPI / ASGI)                                  │  │
│  │ - Lernplan- & Prüfungs-Engine (Phasenallokation)                 │  │
│  │ - Fächer- & Themen-Taxonomie (Klassen 1–13, RLP A–H)             │  │
│  │ - IServ Sync-Worker (CalDAV, WebDAV, Web-Session)                │  │
│  │ - Material-Ingestion & Chunker                                   │  │
│  │ - Whiteboard-State-Manager & Sokratischer Tutor                  │  │
│  └──────────────┬──────────────────────────────────┬────────────────┘  │
│                 │                                  │                   │
│                 ▼                                  ▼                   │
│  ┌───────────────────────────────┐  ┌───────────────────────────────┐  │
│  │ SQLite DB                     │  │ Lokaler File Storage          │  │
│  │ (app_data.db via WAL-Modus)   │  │ (PDFs, Hefter-Scans, Uploads) │  │
│  └───────────────────────────────┘  └───────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

## 2. Portabilität & Cloud-Migrationspfad

Die Architektur verwendet strikte Abstraktionen:
* **Datenbank:** SQLAlchemy ORM ermöglicht den nahtlosen Wechsel von SQLite auf PostgreSQL (via `DATABASE_URL`).
* **Speicher:** `StorageProvider`-Schnittstelle kapselt Dateizugriffe (lokal oder S3/MinIO/Cloudflare R2).
* **Container:** Vollständige Definition in `Dockerfile` und `docker-compose.yml` für VPS/Cloud-Server.
