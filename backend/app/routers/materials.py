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
    MaterialUpdateRequest,
    MaterialMergeRequest,
    MaterialReorderPagesRequest,
)
from backend.app.services.material_ingestion import (
    pre_analyze_upload,
    confirm_and_save_material,
    render_material_page_as_image,
    update_material,
    merge_materials,
    reorder_material_pages,
)

router = APIRouter(prefix="/api/v1/materials", tags=["materials"])

def _to_material_read(mat: Material, db: Session) -> MaterialRead:
    sub = mat.subject or db.query(Subject).filter_by(id=mat.subject_id).first()
    return MaterialRead(
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
        subject_name=sub.name if sub else None,
        subject_icon=sub.icon if sub else None,
        subject_color=sub.color_code if sub else None,
        topic_name=mat.topic.name if mat.topic else None,
        dossier_id=mat.dossier_id,
        dossier_order=mat.dossier_order,
        parent_id=mat.parent_id,
        start_page=mat.start_page,
        end_page=mat.end_page,
        dossier_title=mat.dossier.title if mat.dossier else None
    )

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
    if request.subject_id == "sub_orga" or request.kind == "Stundenplan":
        from backend.app.services.timetable_analyzer import get_or_create_organisation_subject
        get_or_create_organisation_subject(db)

    # Validierung Fach
    subject = db.query(Subject).filter_by(id=request.subject_id).first()
    if not subject:
        if request.subject_id == "sub_orga" or request.kind == "Stundenplan":
            from backend.app.services.timetable_analyzer import get_or_create_organisation_subject
            subject = get_or_create_organisation_subject(db)
        else:
            raise HTTPException(status_code=404, detail=f"Schulfach '{request.subject_id}' nicht gefunden.")

    # Validierung Thema
    if request.topic_id and request.kind != "Stundenplan":
        topic = db.query(Topic).filter_by(id=request.topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail=f"Thema '{request.topic_id}' nicht gefunden.")

    try:
        material = confirm_and_save_material(db, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Speichern: {str(e)}")

    actual_sub = db.query(Subject).filter_by(id=material.subject_id).first() or subject
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
        subject_name=actual_sub.name,
        subject_icon=actual_sub.icon,
        subject_color=actual_sub.color_code,
        topic_name=material.topic.name if material.topic else None,
        dossier_id=material.dossier_id,
        dossier_order=material.dossier_order,
        parent_id=material.parent_id,
        start_page=material.start_page,
        end_page=material.end_page,
        dossier_title=material.dossier.title if material.dossier else None
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
            topic_name=mat.topic.name if mat.topic else None,
            dossier_id=mat.dossier_id,
            dossier_order=mat.dossier_order,
            parent_id=mat.parent_id,
            start_page=mat.start_page,
            end_page=mat.end_page,
            dossier_title=mat.dossier.title if mat.dossier else None
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
        dossier_id=mat.dossier_id,
        dossier_order=mat.dossier_order,
        parent_id=mat.parent_id,
        start_page=mat.start_page,
        end_page=mat.end_page,
        dossier_title=mat.dossier.title if mat.dossier else None,
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
        image_bytes, out_mime = render_material_page_as_image(
            file_path=mat.file_path,
            mime_type=mat.mime_type,
            page_num=page,
            material_id=mat.id
        )
        return Response(
            content=image_bytes,
            media_type=out_mime,
            headers={
                "Cache-Control": "public, max-age=86400, stale-while-revalidate=3600"
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Datei auf dem Speichermedium nicht gefunden.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Rendern der Dokumentseite: {str(e)}")

@router.post("/{material_id}/prefetch")
def prefetch_material_pages(
    material_id: str,
    page: int = 1,
    db: Session = Depends(get_db)
):
    """
    Stößt das vorausschauende Rendern der nächsten Seiten im Hintergrund mit hoher Priorität (2) an.
    """
    mat = db.query(Material).filter_by(id=material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")

    from backend.app.services.page_renderer import page_renderer
    page_renderer.prefetch_adjacent_pages(mat.id, mat.file_path, mat.mime_type, page)
    return {"status": "ok", "prefetched_around_page": page}

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

@router.patch("/{material_id}", response_model=MaterialRead)
def update_material_endpoint(
    material_id: str,
    request: MaterialUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Aktualisiert Metadaten eines Materials (z. B. Fach neu zuordnen, Thema, Titel, Art).
    """
    try:
        mat = update_material(db, material_id, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Aktualisieren: {str(e)}")

    return _to_material_read(mat, db)

@router.post("/merge", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
def merge_materials_endpoint(
    request: MaterialMergeRequest,
    db: Session = Depends(get_db)
):
    """
    Führt mehrere Dokumente in der gewünschten Reihenfolge zu einem einzigen PDF zusammen.
    """
    try:
        mat = merge_materials(db, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Zusammenführen: {str(e)}")

    return _to_material_read(mat, db)

@router.post("/{material_id}/reorder-pages", response_model=MaterialRead)
def reorder_material_pages_endpoint(
    material_id: str,
    request: MaterialReorderPagesRequest,
    db: Session = Depends(get_db)
):
    """
    Ändert die Reihenfolge der Seiten eines PDF-Dokuments (und erlaubt das Löschen einzelner Seiten).
    """
    try:
        mat = reorder_material_pages(db, material_id, request.page_order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Ändern der Seitenreihenfolge: {str(e)}")

    return _to_material_read(mat, db)
