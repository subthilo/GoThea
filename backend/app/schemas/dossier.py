from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from backend.app.schemas.material import MaterialRead

class DossierBase(BaseModel):
    title: str
    kind: str = "hefter"  # 'hefter', 'lehrbuch', 'testsammlung', 'uebungsmappe'
    color_code: str = "#2563eb"
    icon: str = "📁"
    description: Optional[str] = None
    subject_id: str
    topic_id: Optional[str] = None

class DossierCreate(DossierBase):
    pass

class DossierUpdate(BaseModel):
    title: Optional[str] = None
    kind: Optional[str] = None
    color_code: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    topic_id: Optional[str] = None

class DossierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    subject_id: str
    topic_id: Optional[str] = None
    title: str
    kind: str
    color_code: str
    icon: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    materials_count: Optional[int] = 0
    subject_name: Optional[str] = None
    topic_name: Optional[str] = None

class DossierDetailRead(DossierRead):
    materials: List[MaterialRead] = []
