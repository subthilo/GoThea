from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class PreAnalysisResponse(BaseModel):
    upload_token: str
    filename: str
    file_size: int
    mime_type: str
    page_count: int
    predicted_subject_id: Optional[str] = None
    predicted_topic_id: Optional[str] = None
    predicted_title: str
    predicted_kind: str = "Arbeitsblatt"
    preview_snippet: Optional[str] = None
    extracted_text: Optional[str] = None
    solution_pages: List[int] = []
    worked_on_paper: Optional[bool] = None
    teacher_graded: Optional[bool] = None

class MaterialConfirmRequest(BaseModel):
    upload_token: str
    subject_id: str
    topic_id: Optional[str] = None
    dossier_id: Optional[str] = None
    dossier_order: Optional[int] = 1
    parent_id: Optional[str] = None
    title: str
    kind: str = "Arbeitsblatt"
    summary: Optional[str] = None
    solution_pages: List[int] = []
    worked_on_paper: Optional[bool] = None
    teacher_graded: Optional[bool] = None

class MaterialChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chunk_index: int
    content: str
    chunk_type: str
    page_number: Optional[int] = 1

class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    subject_id: str
    topic_id: Optional[str] = None
    dossier_id: Optional[str] = None
    dossier_order: Optional[int] = 1
    parent_id: Optional[str] = None
    title: str
    kind: str
    filename: str
    file_size: int
    mime_type: str
    page_count: int
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    summary: Optional[str] = None
    created_at: datetime
    chunks_count: Optional[int] = 0
    subject_name: Optional[str] = None
    subject_icon: Optional[str] = None
    subject_color: Optional[str] = None
    topic_name: Optional[str] = None
    dossier_title: Optional[str] = None
    solution_pages: List[int] = []
    worked_on_paper: Optional[bool] = None
    teacher_graded: Optional[bool] = None

class MaterialDetailRead(MaterialRead):
    extracted_text: Optional[str] = None
    chunks: List[MaterialChunkRead] = []

class MaterialUpdateRequest(BaseModel):
    subject_id: Optional[str] = None
    topic_id: Optional[str] = None
    title: Optional[str] = None
    kind: Optional[str] = None
    summary: Optional[str] = None

class MaterialMergeRequest(BaseModel):
    material_ids: List[str]
    target_title: Optional[str] = None
    target_subject_id: Optional[str] = None
    target_topic_id: Optional[str] = None
    target_kind: Optional[str] = None
    delete_sources: bool = True

class MaterialReorderPagesRequest(BaseModel):
    page_order: List[int]
