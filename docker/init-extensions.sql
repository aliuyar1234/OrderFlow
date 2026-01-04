-- Ensure required PostgreSQL extensions are available
-- This script runs automatically on first container startup

-- UUID generation functions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- gen_random_uuid() for UUID primary keys
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Trigram similarity for fuzzy text matching (SKU matching)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Vector storage and similarity search for embeddings
CREATE EXTENSION IF NOT EXISTS "vector";
