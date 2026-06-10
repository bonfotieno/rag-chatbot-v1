# RAG Chatbot

A RAG-powered chatbot with document management and an admin dashboard.

**Stack:** FastAPI · PostgreSQL + pgvector · Streamlit · litellm (Anthropic / OpenAI / Ollama)

---

## Features

- Upload documents (PDF, DOCX, Excel, CSV) and chat with their contents
- Vector similarity search via pgvector
- Multi-provider LLM support (Anthropic, OpenAI, Ollama)
- Multi-provider embedding support (Ollama, OpenAI) with automatic fallback
- JWT authentication with user and admin roles
- Admin dashboard for document management and activity logs

---

## Running the App

### Prerequisites

- Python 3.10+
- PostgreSQL 14+ with the [pgvector](https://github.com/pgvector/pgvector) extension
- [Ollama](https://ollama.com) (if using local models — recommended default)

---

### Option 1: Docker (recommended)

**Requirements:** Docker + Docker Compose

```bash
cp .env.example .env
# Edit .env as needed
docker compose up --build
```

| Service  | URL                        |
|----------|----------------------------|
| Frontend | http://localhost:8501      |
| API docs | http://localhost:8000/docs |

---

### Option 2: Run locally without Docker

#### 1. PostgreSQL + pgvector

```bash
psql -U postgres -c "CREATE DATABASE chatbot;"
psql -U postgres -d chatbot -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**Install pgvector:**
- Fedora/RHEL: `sudo dnf install postgresql-pgvector`
- Ubuntu/Debian: `sudo apt install postgresql-16-pgvector` *(adjust version)*
- macOS (Homebrew): `brew install pgvector`
- From source: see https://github.com/pgvector/pgvector

#### 2. Environment file

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

| Variable            | Description                                                         |
|---------------------|---------------------------------------------------------------------|
| `SECRET_KEY`        | Any long random string for JWT signing                              |
| `DATABASE_URL`      | Defaults to `postgresql://postgres:postgres@localhost:5432/chatbot` |
| `ANTHROPIC_API_KEY` | Required only if `LLM_PROVIDER=anthropic`                           |
| `OPENAI_API_KEY`    | Required only if `LLM_PROVIDER=openai` or `EMBEDDING_PROVIDER=openai` |

#### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

On first startup the app automatically:
- Creates all database tables
- Creates a default admin account (`admin@example.com` / `admin123456`)

#### 4. Frontend

Open a second terminal:

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run app.py
```

| Service  | URL                        |
|----------|----------------------------|
| Frontend | http://localhost:8501      |
| API docs | http://localhost:8000/docs |

---

## LLM Configuration

Set `LLM_PROVIDER` and `LLM_MODEL` in `.env`:

| Provider    | `LLM_PROVIDER` | Example `LLM_MODEL`  | API key needed      |
|-------------|----------------|----------------------|---------------------|
| Anthropic   | `anthropic`    | `claude-opus-4-8`    | `ANTHROPIC_API_KEY` |
| OpenAI      | `openai`       | `gpt-4o`             | `OPENAI_API_KEY`    |
| Local Ollama | `ollama`      | `phi3:mini`, `gemma3:1b` | none (local)   |

**Example — switch to a local model:**
```env
LLM_PROVIDER=ollama
LLM_MODEL=phi3:mini
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Embedding Configuration

Set `EMBEDDING_PROVIDER` and `EMBEDDING_MODEL` in `.env`. Default is local Ollama:

| Provider | `EMBEDDING_PROVIDER` | Example `EMBEDDING_MODEL`  | API key needed   |
|----------|----------------------|----------------------------|------------------|
| Ollama   | `ollama`             | `nomic-embed-text`         | none (local)     |
| OpenAI   | `openai`             | `text-embedding-3-small`   | `OPENAI_API_KEY` |

If the configured provider fails, the service automatically falls back to the other. All embeddings are stored as 768-dimensional vectors.

**Example — switch to OpenAI embeddings:**
```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

---

## Default Admin Credentials

| Field    | Default             |
|----------|---------------------|
| Email    | `admin@example.com` |
| Password | `admin123456`       |

Change these in `.env` before any real deployment.
