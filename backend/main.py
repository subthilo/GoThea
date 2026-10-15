import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.database import engine, Base, SessionLocal, ensure_schema_migrations
import backend.app.models  # noqa: F401  (registriert alle Tabellen für create_all)
from backend.app.services.seeder import seed_database
from backend.app.routers.profile import router as profile_router
from backend.app.routers.taxonomy import router as taxonomy_router
from backend.app.routers.env import router as env_router
from backend.app.routers.planner import router as planner_router
from backend.app.routers.whiteboard import router as whiteboard_router, ws_router as whiteboard_ws_router
from backend.app.routers.materials import router as materials_router
from backend.app.routers.annotations import router as annotations_router
from backend.app.routers.inbox import router as inbox_router
from backend.app.routers.timetable import router as timetable_router
from backend.app.routers.books import router as books_router
from backend.app.routers.exercises import router as exercises_router
from backend.app.routers.auth import router as auth_router

# Meldungen der App-Module (Renderer, Segmentierung, Importe) im systemd-Journal sichtbar machen
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
for noisy in ("httpx", "httpcore", "openai", "multipart", "PIL"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Datenbanktabellen initialisieren
    Base.metadata.create_all(bind=engine)
    ensure_schema_migrations(engine)
    # 2. Seed-Daten einspielen
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

    from backend.app.services.material_ingestion import cleanup_temp_uploads
    cleanup_temp_uploads()

    from backend.app.config import BACKGROUND_WORKERS_ENABLED, EXERCISE_POOL_ENABLED
    from backend.app.services.page_renderer import page_renderer
    from backend.app.services.exercise_pool_service import exercise_pool_manager
    from backend.app.services.page_extraction import page_extraction_service
    if BACKGROUND_WORKERS_ENABLED:
        # 5. Seiten-Erschließung: neue Dokumente sofort, Buchkapitel gedrosselt im Hintergrund
        page_extraction_service.start(SessionLocal)
        # 3. Hintergrund-Seiten-Renderer starten & alle Materialien einreihen
        page_renderer.start()
        page_renderer.queue_all_database_materials(SessionLocal)
        # 4. Hintergrund-Übungsspeicher (kontinuierliches Vorrendern aller Übungsarten), nur wenn eingeschaltet
        if EXERCISE_POOL_ENABLED:
            exercise_pool_manager.start(SessionLocal)

    yield

    if BACKGROUND_WORKERS_ENABLED:
        page_extraction_service.stop()
        exercise_pool_manager.stop()
        page_renderer.stop()

app = FastAPI(title="GoThea Multimodale Lernzentrale", lifespan=lifespan)

# API Router einbinden
app.include_router(profile_router)
app.include_router(taxonomy_router)
app.include_router(env_router)
app.include_router(planner_router)
app.include_router(whiteboard_router)
app.include_router(whiteboard_ws_router)
app.include_router(materials_router)
app.include_router(annotations_router)
app.include_router(inbox_router)
app.include_router(timetable_router)
app.include_router(books_router)
app.include_router(exercises_router)
app.include_router(auth_router)

# Statische Frontend-Dateien einbinden
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
async def get_index():
    index_file = FRONTEND_DIR / "index.html"
    return FileResponse(
        index_file,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/favicon.ico")
@app.get("/apple-touch-icon.png")
@app.get("/apple-touch-icon-precomposed.png")
async def get_app_icon():
    # Schneller SVG/PNG-Fallback für Safari (modernes Minimal-Logo)
    svg_icon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none"><rect width="100" height="100" rx="22" fill="#6366f1"/><path d="M28 35h44v38a6 6 0 0 1-6 6H34a6 6 0 0 1-6-6V35z" stroke="#fff" stroke-width="6" stroke-linecap="round"/><path d="M38 27h24v8H38z" fill="#fff"/></svg>'
    return Response(content=svg_icon, media_type="image/svg+xml")

@app.get("/manifest.json")
async def get_manifest():
    manifest_file = FRONTEND_DIR / "manifest.json"
    return FileResponse(manifest_file, media_type="application/manifest+json")

@app.api_route("/api/health", methods=["GET", "HEAD"])
async def health_check():
    return {
        "status": "online",
        "device": "Raspberry Pi / Local",
        "app": "GoThea v0.1.0",
        "message": "Backend und Datenbank laufen einwandfrei"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json({"type": "status", "message": "Verbunden mit GoThea Backend"})
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "echo", "received": data})
    except WebSocketDisconnect:
        pass
