from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="GoThea App")

# Statische Dateien (CSS, JS, Assets) einbinden
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
async def get_index():
    index_file = FRONTEND_DIR / "index.html"
    return FileResponse(index_file)

@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "device": "Raspberry Pi",
        "message": "Backend läuft einwandfrei"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json({"type": "status", "message": "Verbunden mit Pi Backend"})
        while True:
            data = await websocket.receive_text()
            # Echo / Ping-Pong zur Bestätigung
            await websocket.send_json({"type": "echo", "received": data})
    except WebSocketDisconnect:
        pass
