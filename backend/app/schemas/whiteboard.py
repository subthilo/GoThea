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

class TutorAskRequest(BaseModel):
    image_base64: str = Field(description="Base64-kodiertes Bild des aktuellen Whiteboards")
    student_question: Optional[str] = Field(default=None, description="Optionale Frage der Schülerin")
    audio_enabled: bool = Field(default=True, description="Ob MP3-Sprachausgabe erzeugt werden soll")
    material_id: Optional[str] = Field(default=None, description="Optional: ID des aktuell auf der Tafel bearbeiteten Materials / Arbeitsblatts")
    topic_id: Optional[str] = Field(default=None, description="Optional: ID des gewählten Themas")

class TutorAskResponse(BaseModel):
    status: str = "success"
    tutor_speech: str
    audio_base64: Optional[str] = None
    actions: List[Dict[str, Any]] = []

class TutorMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str
    board_action_json: Optional[str] = None
    created_at: datetime

class TutorExerciseCreateRequest(BaseModel):
    exercise_type: Optional[str] = Field(default="auto", description="'auto', 'fill_in_the_blank', 'math_problem', 'math_example', 'text_question', 'physics_diagram', 'formula_derivation'")
    topic_id: Optional[str] = None
    topic_name: Optional[str] = None
    custom_prompt: Optional[str] = Field(default=None, description="Zusätzliche Wünsche der Schülerin, z.B. 'Hebelgesetz'")
    difficulty: Optional[str] = Field(default="mittel", description="'leicht', 'mittel', 'knifflig'")
    material_id: Optional[str] = None
    audio_enabled: bool = True
    pos_x: Optional[int] = 60
    pos_y: Optional[int] = 80

class TutorExercisePositionUpdate(BaseModel):
    pos_x: int
    pos_y: int

class TutorExerciseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    exercise_type: str
    title: str
    topic: Optional[str] = None
    content_json: str
    solution_hint: Optional[str] = None
    pos_x: int
    pos_y: int
    created_at: datetime
    audio_base64: Optional[str] = None
    tutor_speech: Optional[str] = None


