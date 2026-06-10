from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime
import uuid


class ChatQuery(BaseModel):
    question: str
    session_id: Optional[uuid.UUID] = None  # if None, create new session


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    sources: Optional[List[Dict[str, Any]]]
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    message: ChatMessageResponse
    sources: Optional[List[Dict[str, Any]]]


class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New Chat"


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[ChatMessageResponse]] = None

    model_config = {"from_attributes": True}
