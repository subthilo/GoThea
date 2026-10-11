from typing import List, Any
from pydantic import BaseModel

class PageAnnotationSaveRequest(BaseModel):
    strokes: List[Any]  # Liste von Stroke-Objekten: [{tool, color, size, points, ...}]

class PageAnnotationResponse(BaseModel):
    material_id: str
    page_number: int
    strokes: List[Any]
