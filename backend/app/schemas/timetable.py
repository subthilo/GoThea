from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class TimetableSlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    day_of_week: str
    period: int
    period_label: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    subject_id: Optional[str] = None
    subject_code: Optional[str] = None
    subject_name: str
    subject_icon: Optional[str] = None
    subject_color: Optional[str] = None
    custom_title: Optional[str] = None
    teacher: Optional[str] = None
    room: Optional[str] = None
    week_type: str = "both"
    is_double_period: bool = False
    is_break: bool = False
    note: Optional[str] = None

class TimetableSlotCreateUpdate(BaseModel):
    day_of_week: str
    period: int
    period_label: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    subject_id: Optional[str] = None
    subject_code: Optional[str] = None
    subject_name: str
    custom_title: Optional[str] = None
    teacher: Optional[str] = None
    room: Optional[str] = None
    week_type: str = "both"
    is_double_period: bool = False
    is_break: bool = False
    note: Optional[str] = None

class PeriodMeta(BaseModel):
    period: int
    label: str
    start_time: str
    end_time: str
    is_break: bool = False

class TimetableOverviewResponse(BaseModel):
    school_name: str
    class_name: str
    school_year: str
    current_week_type: str
    scan_material_id: Optional[str] = None
    scan_material_title: Optional[str] = None
    periods: List[PeriodMeta]
    slots: List[TimetableSlotRead]
    week_differences: List[str]
