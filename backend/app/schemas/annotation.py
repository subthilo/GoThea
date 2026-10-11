from typing import List, Any, Optional
from pydantic import BaseModel

class PageAnnotationSaveRequest(BaseModel):
    strokes: Optional[List[Any]] = None
    strokes_json: Optional[str] = None

class PageAnnotationResponse(BaseModel):
    material_id: str
    page_number: int
    strokes: List[Any] = []
    strokes_json: Optional[str] = None
