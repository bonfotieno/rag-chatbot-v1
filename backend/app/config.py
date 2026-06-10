from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

# Walk up from backend/app/ to the project root so .env is found
# regardless of which directory uvicorn is launched from.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/chatbotmodern"

    # JWT / Auth
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # LLM
    LLM_PROVIDER: str = "anthropic"  # anthropic | openai | ollama
    LLM_MODEL: str = "claude-opus-4-8"
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Embeddings
    EMBEDDING_PROVIDER: str = "ollama"  # ollama | openai
    EMBEDDING_MODEL: str = "nomic-embed-text"

    # RAG / Chunking
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    MAX_CHUNKS_FOR_RAG: int = 5

    # File upload limits
    MAX_FILE_SIZE_MB: int = 80

    # Frontend
    BACKEND_URL: str = "http://localhost:8000"

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
