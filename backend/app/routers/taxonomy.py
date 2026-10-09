from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.taxonomy import Subject, Topic
from backend.app.schemas.taxonomy import SubjectCreate, SubjectRead, TopicCreate, TopicRead

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

@router.post("/subjects", response_model=SubjectRead, status_code=201)
def create_subject(subject_in: SubjectCreate, db: Session = Depends(get_db)):
    existing = db.query(Subject).filter(Subject.name == subject_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Fach '{subject_in.name}' existiert bereits.")
    subject = Subject(**subject_in.model_dump(exclude_unset=True))
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject

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

@router.post("/topics", response_model=TopicRead, status_code=201)
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
