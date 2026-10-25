"""Theas gemalte Hintergründe und Kacheln – ohne PIN (es ist ihre App); endgültig löschen nur die Eltern."""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.painting import Painting
from backend.app.services import paintings as svc
from backend.app.services.parent_auth import require_parent

router = APIRouter(prefix="/api/v1/paintings", tags=["Malen"])


class SlotAssign(BaseModel):
    painting_id: str


def _get(db: Session, painting_id: str) -> Painting:
    painting = db.get(Painting, painting_id)
    if painting is None:
        raise HTTPException(status_code=404, detail=f"Bild '{painting_id}' nicht gefunden.")
    return painting


async def _read_image(image: Optional[UploadFile]) -> Optional[bytes]:
    if image is None:
        return None
    # Eins mehr als erlaubt lesen, damit zu große Bilder erkannt werden, ohne alles in den Speicher zu holen
    return await image.read(svc.MAX_IMAGE_BYTES + 1)


@router.get("")
def resolve_slots(keys: str = Query(..., description="Plätze der Seite, durch Komma getrennt"),
                  db: Session = Depends(get_db)):
    """Für jeden Platz einer Seite das Bild, das dort erscheint (samt Rückfall auf „für alle Fächer“)."""
    wanted = [k for k in (part.strip() for part in keys.split(",")) if k]
    try:
        return {"slots": svc.resolve(db, wanted)}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/slots/{slot_key:path}/history")
def slot_history(slot_key: str, format: Optional[str] = None, db: Session = Depends(get_db)):
    """„Meine Bilder“ für diesen Platz, auch weggeräumte, das neueste zuerst."""
    try:
        return [dict(svc.summary(p), slots=svc.slots_of(db, p.id)) for p in svc.history(db, slot_key, format)]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/slots/{slot_key:path}")
def assign_slot(slot_key: str, payload: SlotAssign, db: Session = Depends(get_db)):
    painting = _get(db, payload.painting_id)
    try:
        svc.assign(db, slot_key, painting)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"slot_key": slot_key, "painting": svc.summary(painting)}


@router.delete("/slots/{slot_key:path}", status_code=204)
def clear_slot(slot_key: str, db: Session = Depends(get_db)):
    """Thea malt „für alle Fächer“: der Platz des einen Fachs zeigt dann wieder das gemeinsame Bild."""
    try:
        svc.unassign(db, slot_key)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return Response(status_code=204)


@router.post("", status_code=201)
async def create_painting(kind: str = Form(...), format: str = Form(...), strokes_json: Optional[str] = Form(None),
                          slot_key: Optional[str] = Form(None), image: Optional[UploadFile] = File(None),
                          db: Session = Depends(get_db)):
    try:
        painting = svc.create(db, kind, format, strokes_json, await _read_image(image), slot_key)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return dict(svc.summary(painting), slots=svc.slots_of(db, painting.id))


@router.get("/{painting_id}")
def get_painting(painting_id: str, db: Session = Depends(get_db)):
    """Striche zum Weitermalen."""
    painting = _get(db, painting_id)
    return dict(svc.summary(painting), strokes_json=painting.strokes_json, slots=svc.slots_of(db, painting.id))


@router.put("/{painting_id}")
async def update_painting(painting_id: str, strokes_json: Optional[str] = Form(None),
                          image: Optional[UploadFile] = File(None), db: Session = Depends(get_db)):
    painting = _get(db, painting_id)
    try:
        svc.update(db, painting, strokes_json, await _read_image(image))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return svc.summary(painting)


@router.get("/{painting_id}/image")
def painting_image(painting_id: str, db: Session = Depends(get_db)):
    painting = _get(db, painting_id)
    path = svc.image_path(painting)
    if path is None:
        raise HTTPException(status_code=404, detail="Zu diesem Bild gibt es noch keine Bilddatei.")
    ext = path.suffix.lstrip(".")
    # Die URL trägt ?v=<Änderungszeit>: jede neue Fassung hat eine neue Adresse, also darf lange gecacht werden
    return FileResponse(path, media_type=svc.MEDIA_TYPES.get(ext, "application/octet-stream"),
                        headers={"Cache-Control": "private, max-age=31536000, immutable"})


@router.post("/{painting_id}/archive")
def archive_painting(painting_id: str, db: Session = Depends(get_db)):
    """Thea räumt weg: von allen Plätzen genommen, unter „Meine Bilder“ zurückholbar."""
    return svc.summary(svc.archive(db, _get(db, painting_id)))


@router.delete("/{painting_id}", status_code=204, dependencies=[Depends(require_parent)])
def delete_painting(painting_id: str, db: Session = Depends(get_db)):
    svc.delete(db, _get(db, painting_id))
    return Response(status_code=204)
