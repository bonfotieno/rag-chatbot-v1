from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime
import uuid


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    upload_date: datetime
    uploaded_by: uuid.UUID
    processing_status: str
    error_message: Optional[str]
    num_chunks: Optional[int]
    doc_metadata: Optional[Dict[str, Any]]

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class ProcessingStatusResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    num_chunks: Optional[int]
    error_message: Optional[str]
    message: str
