from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

class InboxFileItem(BaseModel):
    filename: str
    file_size: int
    mime_type: str
    modified_at: datetime

class InboxStatusResponse(BaseModel):
    inbox_dir: str
    pending_count: int
    files: List[InboxFileItem]
    errors_count: int

class ProcessedItemDetail(BaseModel):
    material_id: str
    title: str
    filename: Optional[str] = None
    kind: str
    subject_id: str
    subject_name: Optional[str] = None
    topic_id: Optional[str] = None
    topic_name: Optional[str] = None
    dossier_id: Optional[str] = None
    dossier_title: Optional[str] = None
    page_count: int

class QuarantinedItemDetail(BaseModel):
    filename: str
    error_message: str

class InboxProcessResult(BaseModel):
    total_detected: int
    processed_count: int
    errors_count: int
    processed_items: List[ProcessedItemDetail] = []
    quarantined_items: List[QuarantinedItemDetail] = []
