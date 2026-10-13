from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.config import IS_STAGING
from backend.app.models.test import Test
from backend.app.models.study_block import StudyBlock
from backend.app.models.completed_task import CompletedTask
from backend.app.models.taxonomy import Subject
from backend.app.schemas.planner import (
    TestCreate,
    TestRead,
    StudyBlockCreate,
    StudyBlockRead,
    TaskToggleRequest,
    PlanOverviewResponse
)
from backend.app.services.planner import compute_plan_overview
from backend.app.services.parent_auth import require_parent

router = APIRouter(prefix="/api/v1", tags=["Planner & Tests"])

# --- 1. Tests (Prüfungstermine) ---

@router.get("/tests", response_model=List[TestRead])
def list_tests(db: Session = Depends(get_db)):
    tests = db.query(Test).order_by(Test.date.asc()).all()
    results = []
    for t in tests:
        results.append(TestRead(
            id=t.id,
            user_id=t.user_id,
            subject_id=t.subject_id,
            kind=t.kind,
            date=t.date,
            note=t.note,
            source_origin=t.source_origin,
            external_uid=t.external_uid,
            created_at=t.created_at,
            subject_name=t.subject.name if t.subject else "Fach",
            subject_icon=t.subject.icon if t.subject else "📚",
            subject_color=t.subject.color_code if t.subject else "#2563eb"
        ))
    return results

@router.post("/tests", response_model=TestRead, status_code=201, dependencies=[Depends(require_parent)])
def create_test(test_in: TestCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == test_in.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail=f"Fach mit ID '{test_in.subject_id}' nicht gefunden.")

    test = Test(**test_in.model_dump())
    db.add(test)
    db.commit()
    db.refresh(test)

    return TestRead(
        id=test.id,
        user_id=test.user_id,
        subject_id=test.subject_id,
        kind=test.kind,
        date=test.date,
        note=test.note,
        source_origin=test.source_origin,
        external_uid=test.external_uid,
        created_at=test.created_at,
        subject_name=subject.name,
        subject_icon=subject.icon,
        subject_color=subject.color_code
    )

@router.delete("/tests/{test_id}", dependencies=[Depends(require_parent)])
def delete_test(test_id: str, db: Session = Depends(get_db)):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Prüfungstermin nicht gefunden.")
    db.delete(test)
    db.commit()
    return {"status": "success", "message": "Prüfungstermin gelöscht."}


# --- 2. Study Blocks (Sperrtage) ---

@router.get("/plan/blocks", response_model=List[StudyBlockRead])
def list_study_blocks(db: Session = Depends(get_db)):
    blocks = db.query(StudyBlock).order_by(StudyBlock.date.asc()).all()
    results = []
    for b in blocks:
        results.append(StudyBlockRead(
            id=b.id,
            date=b.date,
            subject_id=b.subject_id,
            type=b.type,
            created_at=b.created_at,
            subject_name=b.subject.name if b.subject else "Alle Fächer"
        ))
    return results

@router.post("/plan/block", response_model=StudyBlockRead, status_code=201, dependencies=[Depends(require_parent)])
def create_study_block(block_in: StudyBlockCreate, db: Session = Depends(get_db)):
    # Prüfen, ob bereits gesperrt
    existing = db.query(StudyBlock).filter(
        StudyBlock.date == block_in.date,
        StudyBlock.subject_id == block_in.subject_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Für dieses Datum und Fach existiert bereits ein Sperrtag.")

    block = StudyBlock(**block_in.model_dump())
    db.add(block)
    db.commit()
    db.refresh(block)

    return StudyBlockRead(
        id=block.id,
        date=block.date,
        subject_id=block.subject_id,
        type=block.type,
        created_at=block.created_at,
        subject_name=block.subject.name if block.subject else "Alle Fächer"
    )

@router.delete("/plan/block/{block_id}", dependencies=[Depends(require_parent)])
def delete_study_block(block_id: str, db: Session = Depends(get_db)):
    block = db.query(StudyBlock).filter(StudyBlock.id == block_id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Sperrtag nicht gefunden.")
    db.delete(block)
    db.commit()
    return {"status": "success", "message": "Sperrtag aufgehoben."}


# --- 3. Lernplan-Berechnung & Aufgaben-Abhaken ---

@router.get("/plan", response_model=PlanOverviewResponse)
def get_plan(ref_date: Optional[str] = Query(None), db: Session = Depends(get_db)):
    r_date = date.today()
    if ref_date:
        try:
            from datetime import datetime
            r_date = datetime.strptime(ref_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    return compute_plan_overview(db, ref_date=r_date)

@router.post("/plan/complete-task")
def toggle_task_completion(req: TaskToggleRequest, db: Session = Depends(get_db)):
    task_id = f"{req.test_id}_{req.date}"
    existing = db.query(CompletedTask).filter(CompletedTask.task_identifier == task_id).first()

    if req.completed and not existing:
        completed_task = CompletedTask(test_id=req.test_id, task_identifier=task_id)
        db.add(completed_task)
        db.commit()
    elif not req.completed and existing:
        db.delete(existing)
        db.commit()

    return {"status": "success", "task_identifier": task_id, "completed": req.completed}


# --- 4. Staging Dummy Seeder (Nur im Staging-Modus) ---

@router.post("/staging/seed-dummy-tests", dependencies=[Depends(require_parent)])
def seed_dummy_tests(db: Session = Depends(get_db)):
    if not IS_STAGING:
        raise HTTPException(status_code=403, detail="Dummy-Tests sind nur in der Staging-Umgebung erlaubt!")

    today = date.today()
    # 1. Mathe-Klassenarbeit in 6 Tagen
    math = db.query(Subject).filter(Subject.id == "sub_math").first()
    bio = db.query(Subject).filter(Subject.id == "sub_bio").first()
    german = db.query(Subject).filter(Subject.id == "sub_german").first()

    dummies = []
    if math:
        dummies.append(Test(
            subject_id=math.id,
            kind="Klassenarbeit",
            date=(today + timedelta(days=6)).isoformat(),
            note="Rationale Zahlen, Rechenregeln, Betrag & Vorzeichen"
        ))
    if bio:
        dummies.append(Test(
            subject_id=bio.id,
            kind="Test",
            date=(today + timedelta(days=3)).isoformat(),
            note="Fotosynthese, Blattquerschnitt & Chloroplasten"
        ))
    if german:
        dummies.append(Test(
            subject_id=german.id,
            kind="Klassenarbeit",
            date=(today + timedelta(days=12)).isoformat(),
            note="Balladenanalyse: Goethe 'Der Zauberlehrling'"
        ))

    # Vorherige Dummy-Tests bereinigen
    db.query(Test).filter(Test.source_origin == "manual").delete()
    for d in dummies:
        db.add(d)
    db.commit()

    return {
        "status": "success",
        "created_count": len(dummies),
        "message": "3 realistische Dummy-Prüfungen für Staging erfolgreich angelegt."
    }
