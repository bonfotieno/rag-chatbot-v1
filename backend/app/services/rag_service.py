"""RAG service: vector similarity search + LLM answer generation."""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models.document import DocumentChunk, Document
from ..config import settings
from .embedding_service import embedding_service
from .llm_service import llm_service

logger = logging.getLogger(__name__)


class RAGService:
    """Retrieval-Augmented Generation pipeline."""

    def search_similar_chunks(
        self,
        query: str,
        db: Session,
        top_k: int = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Find the most semantically similar document chunks for *query*.

        Uses pgvector cosine distance for nearest-neighbour search.

        Args:
            query: The user's natural-language question.
            db: SQLAlchemy session.
            top_k: Number of chunks to retrieve (defaults to settings.MAX_CHUNKS_FOR_RAG).
            document_ids: If set, restrict search to these document IDs.

        Returns:
            List of dicts with keys: chunk_id, document_id, filename, chunk_text,
            chunk_index, page_number, score (cosine similarity, higher = more similar).
        """
        top_k = top_k or settings.MAX_CHUNKS_FOR_RAG

        query_embedding = embedding_service.get_embedding(query)

        # pgvector cosine_distance returns 0 (identical) → 2 (opposite);
        # similarity = 1 - cosine_distance.
        q = (
            db.query(
                DocumentChunk,
                DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .filter(Document.processing_status == "processed")
            .filter(DocumentChunk.embedding.isnot(None))
        )

        if document_ids:
            q = q.filter(DocumentChunk.document_id.in_(document_ids))

        results = q.order_by("distance").limit(top_k).all()

        chunks = []
        for chunk, distance in results:
            chunks.append(
                {
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "filename": chunk.document.filename,
                    "chunk_text": chunk.chunk_text,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "score": round(1.0 - float(distance), 4),
                }
            )

        logger.info("Retrieved %d chunks for query (top_k=%d)", len(chunks), top_k)
        return chunks

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Generate a grounded answer from retrieved chunks using the LLM.

        Args:
            question: The user's question.
            retrieved_chunks: Output of search_similar_chunks.
            chat_history: Previous conversation turns for multi-turn context.

        Returns:
            The LLM-generated answer string.
        """
        if not retrieved_chunks:
            return (
                "I could not find any relevant information in the uploaded documents "
                "to answer your question. Please try rephrasing or upload relevant documents."
            )

        context_texts = [chunk["chunk_text"] for chunk in retrieved_chunks]
        answer = llm_service.complete_with_context(
            question=question,
            context_chunks=context_texts,
            chat_history=chat_history,
        )
        return answer

    def query(
        self,
        question: str,
        db: Session,
        chat_history: Optional[List[Dict[str, str]]] = None,
        document_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """End-to-end RAG: retrieve + generate.

        Returns:
            Dict with keys: answer (str), sources (List[Dict]).
        """
        retrieved = self.search_similar_chunks(
            query=question,
            db=db,
            document_ids=document_ids,
        )
        answer = self.generate_answer(
            question=question,
            retrieved_chunks=retrieved,
            chat_history=chat_history,
        )

        # Build source references (without raw chunk text to keep payload small)
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

        return {"answer": answer, "sources": sources}


# Module-level singleton
rag_service = RAGService()
