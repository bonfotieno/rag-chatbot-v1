"""Document processing pipeline: extract → clean → chunk → embed → persist."""
import logging
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from ..models.document import Document, DocumentChunk
from ..core.logging_config import log_event
from .processing.extractor import extract_text
from .processing.cleaner import clean_text
from .processing.chunker import chunk_text
from .embedding_service import embedding_service

logger = logging.getLogger(__name__)


def process_document(document_id: str, file_bytes: bytes, db: Session) -> None:
    """Full processing pipeline for an uploaded document.

    This function is designed to be called as a FastAPI BackgroundTask.
    It updates the Document row's processing_status throughout execution so
    the frontend can poll for progress.

    Stages:
    1. Mark document as "processing".
    2. Extract text from the binary file.
    3. Clean the extracted text.
    4. Chunk the cleaned text.
    5. Embed all chunks in a batch call.
    6. Persist DocumentChunk rows.
    7. Mark document as "processed".

    On any failure the document is marked "failed" with the error message.
    """
    doc: Optional[Document] = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        logger.error("process_document: document %s not found", document_id)
        return

    try:
        # ── Stage 1: mark as processing
        doc.processing_status = "processing"
        doc.error_message = None
        db.commit()
        logger.info("Processing document %s (%s)", document_id, doc.filename)

        # ── Stage 2: text extraction
        full_text, _pages = extract_text(file_bytes, doc.file_type)

        # ── Stage 3: cleaning
        cleaned = clean_text(full_text)
        if not cleaned:
            raise ValueError("Document produced no extractable text after cleaning.")

        # ── Stage 4: chunking
        chunks = chunk_text(cleaned)
        if not chunks:
            raise ValueError("Document produced zero text chunks.")
        logger.info("Document %s: %d chunks created", document_id, len(chunks))

        # ── Stage 5: batch embedding
        embeddings = embedding_service.get_embeddings_batch(chunks)
        assert len(embeddings) == len(chunks), "Embedding count mismatch"

        # ── Stage 6: persist chunks
        # Delete any old chunks (reprocessing scenario)
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()

        for idx, (chunk_text_str, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_text=chunk_text_str,
                chunk_index=idx,
                page_number=None,  # page mapping not threaded through yet
                embedding=embedding,
            )
            db.add(chunk)

        # ── Stage 7: mark processed
        doc.processing_status = "processed"
        doc.num_chunks = len(chunks)
        db.commit()

        logger.info(
            "Document %s processed successfully: %d chunks embedded",
            document_id,
            len(chunks),
        )

        log_event(
            db=db,
            event_type="document_processed",
            message=f"Document '{doc.filename}' processed successfully ({len(chunks)} chunks)",
            level="info",
            user_id=str(doc.uploaded_by),
            details={"document_id": document_id, "num_chunks": len(chunks)},
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to process document %s: %s", document_id, exc)
        try:
            doc.processing_status = "failed"
            doc.error_message = str(exc)
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()

        log_event(
            db=db,
            event_type="document_processing_failed",
            message=f"Document '{doc.filename}' processing failed: {exc}",
            level="error",
            user_id=str(doc.uploaded_by) if doc else None,
            details={"document_id": document_id, "error": str(exc)},
        )
