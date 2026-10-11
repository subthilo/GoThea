from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class TopicBase(BaseModel):
    name: str
    grade_level: int = Field(default=7, ge=1, le=13)
    rlp_level_code: Optional[str] = None
    standard_competencies: Optional[str] = None

class TopicCreate(TopicBase):
    subject_id: str

class TopicRead(TopicBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subject_id: str
    created_at: datetime


class SubjectBase(BaseModel):
    name: str
    color_code: str = "#2563eb"
    icon: str = "📚"
    min_grade: int = 1
    max_grade: int = 13
    is_active: bool = True

class SubjectCreate(SubjectBase):
    id: Optional[str] = None

class SubjectRead(SubjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    topics: List[TopicRead] = []

class TimetableImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    message: str
    detected_subjects: List[str]
    created_subjects: List[SubjectRead]
    existing_subjects: List[SubjectRead]
    material_id: str
    material_title: str
    filename: str
    dossier_id: str
    dossier_title: str
    timetable_grid: dict = {}
    summary: str

