from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class UserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    grade_level: int
    school_type: str
    federal_state: str
    created_at: datetime

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    grade_level: Optional[int] = Field(None, ge=1, le=13)
    school_type: Optional[str] = None
    federal_state: Optional[str] = None
