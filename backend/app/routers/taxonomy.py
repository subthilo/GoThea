import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from backend.app.config import TEMP_UPLOADS_DIR, MATERIALS_DIR
from backend.app.database import get_db
from backend.app.models.taxonomy import Subject, Topic
from backend.app.schemas.taxonomy import (
    SubjectCreate,
    SubjectRead,
    TopicCreate,
    TopicRead,
    TimetableImportResponse
)
from backend.app.services.timetable_analyzer import process_and_import_timetable
from backend.app.services.parent_auth import require_parent

router = APIRouter(prefix="/api/v1/taxonomy", tags=["Taxonomy"])

# --- Subjects ---

@router.get("/subjects", response_model=List[SubjectRead])
def list_subjects(
    grade_level: Optional[int] = Query(None, ge=1, le=13),
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    query = db.query(Subject)
    if is_active is not None:
        query = query.filter(Subject.is_active == is_active)
    if grade_level is not None:
        query = query.filter(Subject.min_grade <= grade_level, Subject.max_grade >= grade_level)
    return query.order_by(Subject.name).all()

@router.post("/subjects", response_model=SubjectRead, status_code=201, dependencies=[Depends(require_parent)])
def create_subject(subject_in: SubjectCreate, db: Session = Depends(get_db)):
    existing = db.query(Subject).filter(Subject.name == subject_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Fach '{subject_in.name}' existiert bereits.")
    subject = Subject(**subject_in.model_dump(exclude_unset=True))
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject

@router.post("/import-timetable", response_model=TimetableImportResponse, status_code=200, dependencies=[Depends(require_parent)])
async def import_timetable_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Importiert einen Stundenplan (PDF oder Bild), erkennt alle Fächer und fügt
    fehlende Fächer automatisch mit passenden Icons, Farben und Themen zur Fächerliste hinzu.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Keine Datei übergeben.")

    temp_path = TEMP_UPLOADS_DIR / f"temp_{uuid.uuid4().hex[:8]}_{file.filename}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Datei ist leer (0 Bytes).")
        temp_path.write_bytes(content)

        res = process_and_import_timetable(
            db=db,
            file_path=temp_path,
            materials_dir=MATERIALS_DIR
        )

        created_count = len(res.created_subjects)
        msg = (
            f"Stundenplan erfolgreich erfasst. {created_count} neue Fächer wurden angelegt und aktiviert."
            if created_count > 0
            else "Stundenplan erfolgreich erfasst. Alle Fächer waren bereits vorhanden."
        )
        if res.slots_imported:
            msg += f" {res.slots_imported} Stunden wurden in den Stundenplan übernommen."
        else:
            msg += " Das Wochenraster konnte nicht gelesen werden, der bisherige Stundenplan bleibt unverändert."

        return TimetableImportResponse(
            status="success",
            message=msg,
            detected_subjects=res.detected_subjects,
            created_subjects=res.created_subjects,
            existing_subjects=res.existing_subjects,
            material_id=res.material_id,
            material_title=res.material_title,
            filename=res.filename,
            dossier_id=res.dossier_id,
            dossier_title=res.dossier_title,
            timetable_grid=res.timetable_grid,
            summary=res.summary,
            slots_imported=res.slots_imported
        )
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

# --- Topics ---

@router.get("/topics", response_model=List[TopicRead])
def list_topics(
    subject_id: Optional[str] = None,
    grade_level: Optional[int] = Query(None, ge=1, le=13),
    db: Session = Depends(get_db)
):
    query = db.query(Topic)
    if subject_id:
        query = query.filter(Topic.subject_id == subject_id)
    if grade_level is not None:
        query = query.filter(Topic.grade_level == grade_level)
    return query.order_by(Topic.name).all()

@router.post("/topics", response_model=TopicRead, status_code=201, dependencies=[Depends(require_parent)])
def create_topic(topic_in: TopicCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == topic_in.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail=f"Fach mit ID '{topic_in.subject_id}' nicht gefunden.")

    existing = db.query(Topic).filter(
        Topic.subject_id == topic_in.subject_id,
        Topic.grade_level == topic_in.grade_level,
        Topic.name == topic_in.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Thema '{topic_in.name}' existiert bereits für dieses Fach und die Klassenstufe.")

    topic = Topic(**topic_in.model_dump())
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic
