"""System logs router (admin only)."""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import uuid
from ..database import get_db
from ..models.log import SystemLog
from ..models.user import User
from ..core.deps import get_current_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/logs", tags=["Logs"])


class LogResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    event_type: str
    message: str
    details: Optional[dict]
    level: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LogListResponse(BaseModel):
    logs: List[LogResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=LogListResponse)
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """List system logs with optional filtering. Admin only."""
    q = db.query(SystemLog)

    if event_type:
        q = q.filter(SystemLog.event_type == event_type)
    if level:
        q = q.filter(SystemLog.level == level)
    if user_id:
        q = q.filter(SystemLog.user_id == user_id)
    if from_date:
        q = q.filter(SystemLog.created_at >= from_date)
    if to_date:
        q = q.filter(SystemLog.created_at <= to_date)

    total = q.count()
    logs = (
        q.order_by(SystemLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return LogListResponse(logs=logs, total=total, page=page, page_size=page_size)
