from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas.inbox import InboxStatusResponse, InboxProcessResult
from backend.app.services.inbox_service import get_inbox_status, process_all_inbox_files

router = APIRouter(prefix="/api/v1/inbox", tags=["Inbox / Dropzone"])

@router.get("/status", response_model=InboxStatusResponse)
def get_status():
    """
    Liefert den aktuellen Füllstand des Inbox-Netzwerkordners (Samba Dropzone).
    """
    return get_inbox_status()

@router.post("/process", response_model=InboxProcessResult)
def process_inbox(db: Session = Depends(get_db)):
    """
    Startet die automatische Verstoffwechselung aller Dateien im Inbox-Ordner.
    Erfolgreich verarbeitete Dateien werden in den regulären Materialspeicher
    verschoben und verschwinden aus dem Inbox-Ordner.
    Fehlerhafte Dateien landen in _errors/.
    """
    return process_all_inbox_files(db=db)
