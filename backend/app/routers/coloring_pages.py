"""Ausmalbilder: Eltern laden SVGs hoch und geben sie frei; Thea sieht nur freigegebene."""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.coloring_page import ColoringPage
from backend.app.services import coloring_pages as svc
from backend.app.services.parent_auth import is_parent, is_parent_viewer, require_parent

router = APIRouter(prefix="/api/v1/coloring-pages", tags=["Ausmalbilder"])

# Formen und Vorschaubild ändern sich nur mit einer neuen Berechnung (Adresse trägt ?v=…)
CACHE = {"Cache-Control": "private, max-age=31536000, immutable"}


class Release(BaseModel):
    freigegeben: bool


class Rename(BaseModel):
    name: str


def _get(db: Session, page_id: str, parent: bool) -> ColoringPage:
    page = db.get(ColoringPage, page_id)
    if page is None or not svc.visible(page, parent):
        raise HTTPException(status_code=404, detail="Ausmalbild nicht gefunden.")
    return page


def _summary(page: ColoringPage, parent: bool) -> dict:
    out = svc.summary(page, parent)
    if page.status in ("berechnet", "freigegeben"):
        v = svc.shapes_version(page)
        out["shapes_url"] = f"/api/v1/coloring-pages/{page.id}/shapes?v={v}"
        out["thumb_url"] = f"/api/v1/coloring-pages/{page.id}/thumb.svg?v={v}"
    return out


@router.get("")
def list_pages(db: Session = Depends(get_db), parent: bool = Depends(is_parent)):
    pages = db.query(ColoringPage).order_by(ColoringPage.created_at.desc()).all()
    return [_summary(p, parent) for p in pages if svc.visible(p, parent)]


@router.post("", status_code=201, dependencies=[Depends(require_parent)])
async def upload_page(background: BackgroundTasks, name: str = Form(""), file: UploadFile = File(...),
                      db: Session = Depends(get_db)):
    data = await file.read(svc.MAX_UPLOAD_BYTES + 1)
    try:
        page = svc.create(db, name or (file.filename or "").rsplit(".", 1)[0], data)
    except svc.ColoringError as e:
        raise HTTPException(status_code=422, detail=str(e))
    background.add_task(svc.process, page.id)  # dauert auf dem Pi bis etwa eine Minute
    return _summary(page, True)


@router.post("/{page_id}/recompute", dependencies=[Depends(require_parent)])
def recompute(page_id: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    page = _get(db, page_id, True)
    page.status, page.error, page.updated_at = "rechnet", None, datetime.utcnow()
    db.commit()
    background.add_task(svc.process, page.id)
    return _summary(page, True)


@router.put("/{page_id}/freigabe", dependencies=[Depends(require_parent)])
def release(page_id: str, payload: Release, db: Session = Depends(get_db)):
    page = _get(db, page_id, True)
    try:
        svc.set_released(db, page, payload.freigegeben)
    except svc.ColoringError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _summary(page, True)


@router.patch("/{page_id}", dependencies=[Depends(require_parent)])
def rename(page_id: str, payload: Rename, db: Session = Depends(get_db)):
    page = _get(db, page_id, True)
    page.name = payload.name.strip()[:120] or page.name
    db.commit()
    return _summary(page, True)


@router.delete("/{page_id}", status_code=204, dependencies=[Depends(require_parent)])
def remove(page_id: str, db: Session = Depends(get_db)):
    """Aus der Liste nehmen; die Dateien bleiben, damit schon bemalte Bilder weiter funktionieren."""
    page = _get(db, page_id, True)
    page.archived_at = datetime.utcnow()
    db.commit()
    return Response(status_code=204)


@router.get("/{page_id}/shapes")
def shapes(page_id: str, db: Session = Depends(get_db), parent: bool = Depends(is_parent_viewer)):
    """Linienfläche, Felder, Umriss. Auch für weggenommene Bilder, solange sie in einem Bild hängen könnten."""
    page = db.get(ColoringPage, page_id)
    if page is None or page.status not in ("berechnet", "freigegeben") or (not parent and page.status != "freigegeben"):
        raise HTTPException(status_code=404, detail="Ausmalbild nicht gefunden.")
    path = svc.shapes_path(page)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Ausmalbild noch nicht berechnet.")
    return FileResponse(path, media_type="application/json", headers=CACHE)


@router.get("/{page_id}/thumb.svg")
def thumb(page_id: str, db: Session = Depends(get_db), parent: bool = Depends(is_parent_viewer)):
    """Vorschaubild aus der berechneten Linienfläche (nie das hochgeladene Original)."""
    page = _get(db, page_id, parent)
    data = svc.thumb_svg(page)
    if data is None:
        raise HTTPException(status_code=404, detail="Ausmalbild noch nicht berechnet.")
    return Response(content=data, media_type="image/svg+xml", headers=CACHE)


@router.get("/{page_id}/original", dependencies=[Depends(require_parent)])
def original(page_id: str, db: Session = Depends(get_db)):
    """Die hochgeladene Datei – nur für die Eltern und nur als Download (nie im Browser angezeigt)."""
    page = _get(db, page_id, True)
    return FileResponse(svc.svg_path(page), media_type="application/octet-stream",
                        filename=f"{page.name}.svg", headers={"Content-Security-Policy": "sandbox"})
