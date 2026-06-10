"""Chat router: RAG query, session CRUD, message history."""
import uuid
import json
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from ..models.user import User
from ..models.chat import ChatSession, ChatMessage
from ..schemas.chat import (
    ChatQuery,
    ChatResponse,
    ChatSessionResponse,
    ChatSessionCreate,
    ChatMessageResponse,
)
from ..core.deps import get_current_user
from ..core.logging_config import log_event
from ..services.rag_service import rag_service
from ..services.llm_service import llm_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])


# ── Sessions ───
@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new chat session."""
    session = ChatSession(
        id=uuid.uuid4(),
        user_id=current_user.id,
        title=payload.title or "New Chat",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=List[ChatSessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all chat sessions for the current user."""
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return sessions


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
def get_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a session with its full message history."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    # Eagerly load messages
    session_dict = {
        "id": session.id,
        "user_id": session.user_id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": session.messages,
    }
    return session_dict


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a chat session and all its messages."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    db.delete(session)
    db.commit()


# ── Messages ───
@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
def get_messages(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all messages in a session."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return session.messages


# ── RAG Query ──
@router.post("/query", response_model=ChatResponse)
def query(
    payload: ChatQuery,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """RAG-powered Q&A.  Creates a session if session_id is not provided."""
    # Resolve or create session
    if payload.session_id:
        session = db.query(ChatSession).filter(ChatSession.id == payload.session_id).first()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if session.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        # Auto-create a session titled with the first ~50 chars of the question
        title = payload.question[:50] + ("…" if len(payload.question) > 50 else "")
        session = ChatSession(id=uuid.uuid4(), user_id=current_user.id, title=title)
        db.add(session)
        db.flush()

    # Build chat history from existing messages (for multi-turn context)
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in (session.messages or [])
    ]

    # Persist the user message
    user_msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="user",
        content=payload.question,
        sources=None,
    )
    db.add(user_msg)
    db.flush()

    # Run RAG pipeline
    try:
        result = rag_service.query(
            question=payload.question,
            db=db,
            chat_history=history,
        )
        answer_text = result["answer"]
        sources = result["sources"]
    except Exception as exc:
        logger.exception("RAG pipeline error: %s", exc)
        answer_text = "I'm sorry, an error occurred while processing your question. Please try again."
        sources = []

    # Persist the assistant message
    assistant_msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="assistant",
        content=answer_text,
        sources=sources,
    )
    db.add(assistant_msg)

    # Update session timestamp and title (first message sets title)
    from datetime import datetime
    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(assistant_msg)

    log_event(
        db=db,
        event_type="chat_query",
        message=f"User queried: {payload.question[:100]}",
        level="info",
        user_id=str(current_user.id),
        details={"session_id": str(session.id), "num_sources": len(sources)},
    )

    return ChatResponse(
        session_id=session.id,
        message=ChatMessageResponse.model_validate(assistant_msg),
        sources=sources,
    )


@router.post("/stream")
def stream_query(
    payload: ChatQuery,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Streaming RAG-powered Q&A via Server-Sent Events."""
    # ── Session setup (done before streaming starts) ──
    if payload.session_id:
        session = db.query(ChatSession).filter(ChatSession.id == payload.session_id).first()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if session.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        title = payload.question[:50] + ("…" if len(payload.question) > 50 else "")
        session = ChatSession(id=uuid.uuid4(), user_id=current_user.id, title=title)
        db.add(session)
        db.flush()

    history = [{"role": m.role, "content": m.content} for m in (session.messages or [])]

    user_msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="user",
        content=payload.question,
        sources=None,
    )
    db.add(user_msg)
    db.commit()

    # Capture values needed inside the generator
    session_id = session.id
    question = payload.question
    user_id = str(current_user.id)

    def generate():
        # Retrieve context chunks
        try:
            retrieved = rag_service.search_similar_chunks(question, db=db)
            sources = [
                {
                    "document_id": c["document_id"],
                    "filename": c["filename"],
                    "chunk_index": c["chunk_index"],
                    "page_number": c["page_number"],
                    "score": c["score"],
                }
                for c in retrieved
            ]
        except Exception as exc:
            logger.exception("Retrieval error: %s", exc)
            retrieved, sources = [], []

        if not retrieved:
            no_ctx = "I could not find any relevant information in the uploaded documents to answer your question."
            yield f"data: {json.dumps({'type': 'token', 'content': no_ctx})}\n\n"
            full_answer = no_ctx
        else:
            context_texts = [c["chunk_text"] for c in retrieved]
            tokens = []
            try:
                for token in llm_service.stream_with_context(question, context_texts, history):
                    tokens.append(token)
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            except Exception as exc:
                logger.exception("LLM streaming error: %s", exc)
                err = "An error occurred while generating the response."
                yield f"data: {json.dumps({'type': 'token', 'content': err})}\n\n"
                tokens.append(err)
            full_answer = "".join(tokens)

        # Persist assistant message using a fresh DB session
        persist_db = SessionLocal()
        try:
            assistant_msg = ChatMessage(
                id=uuid.uuid4(),
                session_id=session_id,
                role="assistant",
                content=full_answer,
                sources=sources,
            )
            persist_db.add(assistant_msg)
            persist_db.query(ChatSession).filter(ChatSession.id == session_id).update(
                {"updated_at": datetime.utcnow()}
            )
            persist_db.commit()
            log_event(
                db=persist_db,
                event_type="chat_query",
                message=f"User queried: {question[:100]}",
                level="info",
                user_id=user_id,
                details={"session_id": str(session_id), "num_sources": len(sources)},
            )
            persist_db.commit()
        except Exception as exc:
            logger.exception("Failed to persist streamed message: %s", exc)
        finally:
            persist_db.close()

        yield f"data: {json.dumps({'type': 'done', 'session_id': str(session_id), 'sources': sources})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
