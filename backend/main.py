from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.database import engine, Base, SessionLocal
from backend.app.models.user import User
from backend.app.models.taxonomy import Subject, Topic
from backend.app.services.seeder import seed_database
from backend.app.routers.profile import router as profile_router
from backend.app.routers.taxonomy import router as taxonomy_router
from backend.app.routers.env import router as env_router

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Datenbanktabellen initialisieren
    Base.metadata.create_all(bind=engine)
    # 2. Seed-Daten einspielen
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield

app = FastAPI(title="GoThea Multimodale Lernzentrale", lifespan=lifespan)

# API Router einbinden
app.include_router(profile_router)
app.include_router(taxonomy_router)
app.include_router(env_router)

# Statische Frontend-Dateien einbinden
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
async def get_index():
    index_file = FRONTEND_DIR / "index.html"
    return FileResponse(index_file)

@app.get("/favicon.ico")
@app.get("/apple-touch-icon.png")
@app.get("/apple-touch-icon-precomposed.png")
async def get_app_icon():
    # Schneller SVG/PNG-Fallback für Safari
    svg_icon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🦉</text></svg>'
    return Response(content=svg_icon, media_type="image/svg+xml")

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
