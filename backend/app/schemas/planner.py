from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

# --- Test / Prüfung Schemas ---

class TestBase(BaseModel):
    subject_id: str
    kind: str = Field(default="Klassenarbeit", pattern="^(Test|Klassenarbeit|Klausur)$")
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD
    note: Optional[str] = None

class TestCreate(TestBase):
    pass

class TestRead(TestBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    source_origin: str
    external_uid: Optional[str] = None
    created_at: datetime
    subject_name: Optional[str] = None
    subject_icon: Optional[str] = None
    subject_color: Optional[str] = None


# --- StudyBlock / Sperrtag Schemas ---

class StudyBlockBase(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    subject_id: Optional[str] = None
    type: str = Field(default="all", pattern="^(all|subject)$")

class StudyBlockCreate(StudyBlockBase):
    pass

class StudyBlockRead(StudyBlockBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    subject_name: Optional[str] = None


# --- Plan & Aufgaben Schemas ---

class TaskToggleRequest(BaseModel):
    test_id: str
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    completed: bool = True

class PlanTaskItem(BaseModel):
    task_identifier: str
    test_id: str
    subject_id: str
    subject_name: str
    subject_icon: str
    subject_color: str
    test_kind: str
    test_date: str
    test_note: Optional[str] = None
    days_until_test: int
    phase_number: int  # 0 (Ruhemodus/Prüfungstag), 1 (Grundlagen), 2 (Üben), 3 (Generalprobe)
    phase_name: str
    phase_description: str
    target_minutes: int
    is_completed: bool = False
    is_exam_day: bool = False

class DayPlan(BaseModel):
    date: str
    day_name: str  # z. B. "Montag, 12. Okt."
    is_blocked: bool = False
    block_info: Optional[str] = None
    tasks: List[PlanTaskItem] = []
    total_minutes: int = 0

class PlanOverviewResponse(BaseModel):
    today_date: str
    grade_level: int
    today_plan: DayPlan
    upcoming_tests: List[TestRead] = []
    next_7_days: List[DayPlan] = []
