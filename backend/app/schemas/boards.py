from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BoardCreate(BaseModel):
    subject_id: str


class BoardRename(BaseModel):
    title: str = Field(min_length=1, max_length=60)


class BoardSummary(BaseModel):
    id: str
    subject_id: str
    subject_name: Optional[str] = None
    subject_icon: Optional[str] = None
    title: Optional[str] = None
    title_source: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_opened_at: Optional[datetime] = None
    archived: bool
    stroke_count: int
    has_thumbnail: bool


class BoardDetail(BoardSummary):
    board_state_json: Optional[str] = None


class BoardCloseResult(BaseModel):
    deleted: bool
    board: Optional[BoardSummary] = None
