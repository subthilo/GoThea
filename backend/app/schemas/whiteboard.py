from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class StrokePoint(BaseModel):
    x: float
    y: float
    pressure: Optional[float] = 0.5

class WhiteboardStroke(BaseModel):
    tool: str = Field(default="pen", description="'pen', 'highlighter', 'eraser'")
    color: str = Field(default="#f8fafc")
    width: float = Field(default=3.0)
    points: List[StrokePoint]

class TutorSessionCreate(BaseModel):
    subject_id: str
    topic_id: Optional[str] = None
    test_id: Optional[str] = None
    title: Optional[str] = "Tafelsitzung"
    grade_level: Optional[int] = 7

class TutorSessionUpdateState(BaseModel):
    board_state_json: str
    snapshot_data_url: Optional[str] = None
    summary_notes: Optional[str] = None

class TutorSessionClose(BaseModel):
    summary_notes: Optional[str] = None

class TutorSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    test_id: Optional[str] = None
    subject_id: str
    subject_name: Optional[str] = None
    subject_icon: Optional[str] = None
    subject_color: Optional[str] = None
    topic_id: Optional[str] = None
    topic_name: Optional[str] = None
    title: Optional[str] = None
    grade_level: int
    start_time: datetime
    end_time: Optional[datetime] = None
    board_state_json: Optional[str] = None
    snapshot_data_url: Optional[str] = None
    summary_notes: Optional[str] = None

class OverlayAction(BaseModel):
    action: str = Field(description="'highlight_box', 'arrow', 'latex_hint', 'clear'")
    coords: Optional[Dict[str, float]] = None
    color: Optional[str] = "#f59e0b"
    latex: Optional[str] = None
    text: Optional[str] = None
