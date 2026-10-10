from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.material import Material, MaterialChunk
from backend.app.models.taxonomy import Subject, Topic
from backend.app.schemas.material import (
    PreAnalysisResponse,
    MaterialConfirmRequest,
    MaterialRead,
    MaterialDetailRead,
)
from backend.app.services.material_ingestion import (
    pre_analyze_upload,
    confirm_and_save_material,
    render_material_page_as_image,
)

router = APIRouter(prefix="/api/v1/materials", tags=["materials"])

@router.post("/pre-analyze", response_model=PreAnalysisResponse, status_code=status.HTTP_200_OK)
async def pre_analyze_material(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Stufe 1 der Material-Ingestion:
    Nimmt eine hochgeladene Datei (PDF, PNG, JPG) entgegen, extrahiert Metadaten/Text
    und schlägt Fach, Thema, Titel und Dokumententyp vor.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Die hochgeladene Datei ist leer.")

    # Max 50 MB
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Dateigröße überschreitet das Limit von 50 MB.")

    mime = file.content_type or "application/octet-stream"
    try:
        response = pre_analyze_upload(db, file.filename, content, mime)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler bei der Vorabanalyse: {str(e)}")

@router.post("/confirm", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
def confirm_material(
    request: MaterialConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Stufe 2 der Material-Ingestion (Human-in-the-Loop):
    Bestätigt die Metadaten durch den Nutzer und persistiert das Material dauerhaft
    inklusive semantischer Chunk-Segmentierung.
    """
    # Validierung Fach
    subject = db.query(Subject).filter_by(id=request.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail=f"Schulfach '{request.subject_id}' nicht gefunden.")

    # Validierung Thema
    if request.topic_id:
        topic = db.query(Topic).filter_by(id=request.topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail=f"Thema '{request.topic_id}' nicht gefunden.")

    try:
        material = confirm_and_save_material(db, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Speichern: {str(e)}")

    return MaterialRead(
        id=material.id,
        user_id=material.user_id,
        subject_id=material.subject_id,
        topic_id=material.topic_id,
        title=material.title,
        kind=material.kind,
        filename=material.filename,
        file_size=material.file_size,
        mime_type=material.mime_type,
        page_count=material.page_count,
        summary=material.summary,
        created_at=material.created_at,
        chunks_count=len(material.chunks) if material.chunks else 0,
        subject_name=subject.name,
        subject_icon=subject.icon,
        subject_color=subject.color_code,
        topic_name=material.topic.name if material.topic else None
    )

@router.get("", response_model=List[MaterialRead])
def list_materials(
    subject_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Liefert eine Liste gespeicherter Lernmaterialien, optional gefiltert nach Fach oder Thema.
    """
    query = db.query(Material)
    if subject_id:
        query = query.filter(Material.subject_id == subject_id)
    if topic_id:
        query = query.filter(Material.topic_id == topic_id)

    materials = query.order_by(Material.created_at.desc()).all()
    results = []
    for mat in materials:
        results.append(MaterialRead(
            id=mat.id,
            user_id=mat.user_id,
            subject_id=mat.subject_id,
            topic_id=mat.topic_id,
            title=mat.title,
            kind=mat.kind,
            filename=mat.filename,
            file_size=mat.file_size,
            mime_type=mat.mime_type,
            page_count=mat.page_count,
            summary=mat.summary,
            created_at=mat.created_at,
            chunks_count=len(mat.chunks) if mat.chunks else 0,
            subject_name=mat.subject.name if mat.subject else None,
            subject_icon=mat.subject.icon if mat.subject else None,
            subject_color=mat.subject.color_code if mat.subject else None,
            topic_name=mat.topic.name if mat.topic else None
        ))
    return results

@router.get("/{material_id}", response_model=MaterialDetailRead)
def get_material_detail(
    material_id: str,
    db: Session = Depends(get_db)
):
    """
    Liefert ein Material mit Volltext und semantischen Chunks.
    """
    mat = db.query(Material).filter_by(id=material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")

    return MaterialDetailRead(
        id=mat.id,
        user_id=mat.user_id,
        subject_id=mat.subject_id,
        topic_id=mat.topic_id,
        title=mat.title,
        kind=mat.kind,
        filename=mat.filename,
        file_size=mat.file_size,
        mime_type=mat.mime_type,
        page_count=mat.page_count,
        summary=mat.summary,
        created_at=mat.created_at,
        chunks_count=len(mat.chunks) if mat.chunks else 0,
        subject_name=mat.subject.name if mat.subject else None,
        subject_icon=mat.subject.icon if mat.subject else None,
        subject_color=mat.subject.color_code if mat.subject else None,
        topic_name=mat.topic.name if mat.topic else None,
        extracted_text=mat.extracted_text,
        chunks=mat.chunks
    )

@router.get("/{material_id}/file")
def get_material_file(
    material_id: str,
    db: Session = Depends(get_db)
):
    """
    Liefert die Binärdatei des Materials zur Anzeige oder zum Download.
    """
    mat = db.query(Material).filter_by(id=material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")

    file_path = Path(mat.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Datei auf dem Speichermedium nicht gefunden.")

    return FileResponse(
        path=str(file_path),
        media_type=mat.mime_type,
        filename=mat.filename
    )

@router.get("/{material_id}/preview")
def get_material_preview_image(
    material_id: str,
    page: int = 1,
    db: Session = Depends(get_db)
):
    """
    Rendert eine Seite des Materials (PDF oder Bild) als hochauflösendes PNG-Bild,
    perfekt für Whiteboard-Hintergründe und In-App Vorschau.
    """
    mat = db.query(Material).filter_by(id=material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")

    try:
        image_bytes, out_mime = render_material_page_as_image(mat.file_path, mat.mime_type, page)
        return Response(content=image_bytes, media_type=out_mime)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Datei auf dem Speichermedium nicht gefunden.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Rendern der Dokumentseite: {str(e)}")

@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    material_id: str,
    db: Session = Depends(get_db)
):
    """
    Löscht ein Material, die zugehörigen Chunks und die physische Datei vom Server.
    """
    mat = db.query(Material).filter_by(id=material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")

    # Datei auf Festplatte löschen falls vorhanden
    try:
        p = Path(mat.file_path)
        if p.exists():
            p.unlink()
    except Exception:
        pass

    db.delete(mat)
    db.commit()
    return None
