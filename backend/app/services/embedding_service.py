"""Embedding service: configurable provider (ollama | openai) with ollama fallback."""
import logging
import requests
from typing import List
from openai import OpenAI
from ..config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 768  # matches Vector(768) in the DB model


class EmbeddingService:
    def __init__(self) -> None:
        self.provider = settings.EMBEDDING_PROVIDER
        self.model = settings.EMBEDDING_MODEL
        self._ollama_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self._openai = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    # ── public API ─────

    def get_embedding(self, text: str) -> List[float]:
        text = text.strip()
        if not text:
            raise ValueError("Cannot embed empty text")
        return self._embed([text])[0]

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return self._embed(texts)

    # ── routing ───

    def _embed(self, texts: List[str]) -> List[List[float]]:
        if self.provider == "openai":
            try:
                return self._openai_embed_batched(texts)
            except Exception as exc:
                logger.warning("OpenAI embedding failed (%s), falling back to ollama", exc)
                return self._ollama_embed(texts)
        else:
            try:
                return self._ollama_embed(texts)
            except Exception as exc:
                logger.warning("Ollama embedding failed (%s), falling back to OpenAI", exc)
                return self._openai_embed_batched(texts)

    # ── OpenAI ───

    def _openai_embed_batched(self, texts: List[str]) -> List[List[float]]:
        if not self._openai:
            raise RuntimeError("OPENAI_API_KEY is not set")
        max_batch = 2048
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), max_batch):
            batch = [t.strip() for t in texts[i : i + max_batch]]
            logger.info("OpenAI embedding batch %d-%d of %d", i, i + len(batch), len(texts))
            response = self._openai.embeddings.create(
                input=batch,
                model=self.model if self.provider == "openai" else "text-embedding-3-small",
                dimensions=EMBEDDING_DIMENSIONS,
            )
            batch_embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
            all_embeddings.extend(batch_embeddings)
        return all_embeddings

    # ── Ollama ────

    def _ollama_embed(self, texts: List[str]) -> List[List[float]]:
        # Call one at a time — nomic-embed-text does not support batch input.
        model = self.model if self.provider == "ollama" else "nomic-embed-text"
        logger.info("Ollama embedding (%s) for %d text(s)", model, len(texts))
        embeddings = []
        for text in texts:
            resp = requests.post(
                f"{self._ollama_url}/api/embeddings",
                json={"model": model, "prompt": text},
                timeout=60,
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["embedding"])
        return embeddings


# Module-level singleton
embedding_service = EmbeddingService()
