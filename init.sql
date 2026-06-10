-- Ensure the pgvector extension is available.
-- This runs inside the POSTGRES_DB database when the container first starts.
CREATE EXTENSION IF NOT EXISTS vector;
