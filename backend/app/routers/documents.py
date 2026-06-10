"""Document management router."""
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.document import Document
from ..models.user import User
from ..schemas.document import DocumentResponse, DocumentListResponse, ProcessingStatusResponse
from ..core.deps import get_current_user, get_current_admin
from ..core.logging_config import log_event
from ..services.document_service import process_document
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_TYPES = {"pdf", "docx", "doc", "txt", "csv", "xlsx", "xls"}


def _file_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document and kick off background processing."""
    ext = _file_extension(file.filename or "")
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    file_bytes = await file.read()
    file_size = len(file_bytes)

    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB",
        )

    doc = Document(
        id=uuid.uuid4(),
        filename=file.filename,
        file_type=ext,
        file_size=file_size,
        uploaded_by=current_user.id,
        processing_status="uploaded",
        num_chunks=0,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_event(
        db=db,
        event_type="document_uploaded",
        message=f"Document uploaded: {file.filename} ({file_size} bytes)",
        level="info",
        user_id=str(current_user.id),
        details={"document_id": str(doc.id), "file_type": ext, "file_size": file_size},
    )

    # Launch background processing (passes a new session so the bg task is independent)
    from ..database import SessionLocal

    def run_processing():
        bg_db = SessionLocal()
        try:
            process_document(str(doc.id), file_bytes, bg_db)
        finally:
            bg_db.close()

    background_tasks.add_task(run_processing)
    return doc


@router.get("", response_model=DocumentListResponse)
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents accessible to the current user (admin sees all)."""
    q = db.query(Document)
    if current_user.role != "admin":
        q = q.filter(Document.uploaded_by == current_user.id)
    if status_filter:
        q = q.filter(Document.processing_status == status_filter)

    total = q.count()
    docs = q.order_by(Document.upload_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return DocumentListResponse(documents=docs, total=total, page=page, page_size=page_size)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a single document's metadata."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if current_user.role != "admin" and doc.uploaded_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return doc


@router.get("/{document_id}/status", response_model=ProcessingStatusResponse)
def get_document_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Poll document processing status."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if current_user.role != "admin" and doc.uploaded_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    status_messages = {
        "uploaded": "Document uploaded, awaiting processing",
        "processing": "Document is being processed",
        "processed": "Document processed and ready for querying",
        "failed": "Document processing failed",
    }
    return ProcessingStatusResponse(
        document_id=doc.id,
        status=doc.processing_status,
        num_chunks=doc.num_chunks,
        error_message=doc.error_message,
        message=status_messages.get(doc.processing_status, "Unknown status"),
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document and all its chunks. Admin or uploader only."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if current_user.role != "admin" and doc.uploaded_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    filename = doc.filename
    db.delete(doc)
    db.commit()

    log_event(
        db=db,
        event_type="document_deleted",
        message=f"Document deleted: {filename}",
        level="info",
        user_id=str(current_user.id),
        details={"document_id": str(document_id)},
    )


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
async def reprocess_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),  # admin only
):
    """Re-trigger document processing (admin only). Useful after pipeline fixes."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Reprocessing requires the original file bytes which are not stored on disk. "
            "Please delete and re-upload the document."
        ),
    )
