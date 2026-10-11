from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class BookChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chapter_number: int
    title: str
    kind: str = "Buchauszug"
    topic_id: Optional[str] = None
    topic_name: Optional[str] = None
    start_page: int
    end_page: int
    page_count: int
    focus: Optional[str] = None
    filename: str
    file_size: int = 0
    file_url: str
    preview_url: str

class BookOverviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    authors: Optional[str] = None
    grade_level: int = 7
    subject_id: str
    subject_name: str
    subject_icon: str = "📚"
    subject_color: str = "#2563eb"
    total_pages: int
    chapters_count: int
    summary: Optional[str] = None
    cover_preview_url: Optional[str] = None

class BookDetailRead(BookOverviewRead):
    dossier_id: Optional[str] = None
    chapters: List[BookChapterRead] = []
