import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.material import Material
from backend.app.models.annotation import PageAnnotation
from backend.app.schemas.annotation import PageAnnotationSaveRequest, PageAnnotationResponse

router = APIRouter(prefix="/api/v1/materials", tags=["Annotations"])

@router.get("/{material_id}/pages/{page}/annotations", response_model=PageAnnotationResponse)
def get_page_annotations(
    material_id: str,
    page: int,
    db: Session = Depends(get_db)
):
    """
    Ruft alle handschriftlichen Annotationen (Striche, Notizen, Markierungen)
    für eine bestimmte Dokumentenseite ab.
    """
    mat = db.query(Material).filter_by(id=material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")

    ann = db.query(PageAnnotation).filter_by(material_id=material_id, page_number=page).first()
    if not ann or not ann.strokes_json:
        return PageAnnotationResponse(
            material_id=material_id,
            page_number=page,
            strokes=[]
        )

    try:
        strokes = json.loads(ann.strokes_json)
    except Exception:
        strokes = []

    return PageAnnotationResponse(
        material_id=material_id,
        page_number=page,
        strokes=strokes
    )

@router.put("/{material_id}/pages/{page}/annotations", response_model=PageAnnotationResponse)
def save_page_annotations(
    material_id: str,
    page: int,
    req: PageAnnotationSaveRequest,
    db: Session = Depends(get_db)
):
    """
    Speichert oder aktualisiert alle handschriftlichen Annotationen einer Seite.
    """
    mat = db.query(Material).filter_by(id=material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")

    strokes_str = json.dumps(req.strokes)
    ann_id = f"ann_{material_id}_p{page}"

    ann = db.query(PageAnnotation).filter_by(material_id=material_id, page_number=page).first()
    if ann:
        ann.strokes_json = strokes_str
    else:
        ann = PageAnnotation(
            id=ann_id,
            user_id="usr_thea",
            material_id=material_id,
            page_number=page,
            strokes_json=strokes_str
        )
        db.add(ann)

    db.commit()
    db.refresh(ann)

    return PageAnnotationResponse(
        material_id=material_id,
        page_number=page,
        strokes=req.strokes
    )

@router.delete("/{material_id}/pages/{page}/annotations")
def delete_page_annotations(
    material_id: str,
    page: int,
    db: Session = Depends(get_db)
):
    """
    Löscht alle Annotationen einer Seite (z. B. 'Seite leeren').
    """
    ann = db.query(PageAnnotation).filter_by(material_id=material_id, page_number=page).first()
    if ann:
        db.delete(ann)
        db.commit()

    return {"status": "ok", "message": f"Annotationen für Seite {page} gelöscht."}
