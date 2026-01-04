# Data Model: LLM Provider Layer

**Feature**: 011-llm-provider-layer
**Date**: 2025-12-27

## Entity Definitions

### ai_call_log

Immutable log of all LLM and embedding provider calls with cost, token, and latency tracking.

**Purpose**: Complete audit trail of AI usage for cost control, debugging, and compliance.

**Key Fields**:
- `id` (UUID, PK): Unique identifier
- `org_id` (UUID, FK → organization, NOT NULL): Multi-tenant isolation
- `call_type` (AICallType ENUM, NOT NULL): LLM_EXTRACT_PDF_TEXT, LLM_EXTRACT_PDF_VISION, LLM_REPAIR_JSON, etc.
- `document_id` (UUID, FK → document, nullable): Associated document if applicable
- `provider` (VARCHAR(50), NOT NULL): "openai", "anthropic", "local"
- `model` (VARCHAR(100), NOT NULL): "gpt-4o-mini", "gpt-4o", "claude-3-5-sonnet"
- `tokens_in` (INT, nullable): Input tokens (prompt)
- `tokens_out` (INT, nullable): Output tokens (completion)
- `latency_ms` (INT, NOT NULL): API call duration in milliseconds
- `cost_micros` (BIGINT, NOT NULL): Cost in micros (1 EUR = 1,000,000 micros)
- `status` (VARCHAR(20), NOT NULL): "SUCCEEDED", "FAILED"
- `error_json` (JSONB, nullable): Error details if status=FAILED
- `input_hash` (VARCHAR(64), nullable): SHA256 hash of input for deduplication
- `created_at` (TIMESTAMP, NOT NULL): Call timestamp

**Constraints**:
- Index on (org_id, created_at) for cost queries
- Index on (org_id, call_type, status) for monitoring
- Index on (org_id, input_hash, status) for deduplication
- Unique constraint on (org_id, document_id, call_type, status) WHERE status='SUCCEEDED' (deduplication)

## SQLAlchemy Model Structures

### AICallLog Model

```python
from sqlalchemy import Column, String, Integer, BigInteger, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import relationship
import uuid
from enum import Enum

class AICallType(str, Enum):
    LLM_EXTRACT_PDF_TEXT = "LLM_EXTRACT_PDF_TEXT"
    LLM_EXTRACT_PDF_VISION = "LLM_EXTRACT_PDF_VISION"
    LLM_REPAIR_JSON = "LLM_REPAIR_JSON"
    LLM_CUSTOMER_HINT = "LLM_CUSTOMER_HINT"
    EMBEDDING_GENERATE = "EMBEDDING_GENERATE"
    EMBEDDING_BATCH = "EMBEDDING_BATCH"

class AICallLog(Base):
    __tablename__ = "ai_call_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True)
    call_type = Column(String(50), nullable=False)  # AICallType enum
    document_id = Column(UUID(as_uuid=True), ForeignKey("document.id", ondelete="SET NULL"), nullable=True)

    provider = Column(String(50), nullable=False)  # "openai", "anthropic"
    model = Column(String(100), nullable=False)  # "gpt-4o-mini"

    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=False)
    cost_micros = Column(BigInteger, nullable=False, default=0)

    status = Column(String(20), nullable=False)  # "SUCCEEDED" | "FAILED"
    error_json = Column(JSONB, nullable=True)

    input_hash = Column(String(64), nullable=True, index=True)  # SHA256 for deduplication

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()")

    # Relationships
    organization = relationship("Organization", back_populates="ai_call_logs")
    document = relationship("Document", back_populates="ai_call_logs")

    __table_args__ = (
        Index("idx_ai_call_log_cost", "org_id", "created_at"),
        Index("idx_ai_call_log_monitoring", "org_id", "call_type", "status"),
        Index("idx_ai_call_log_dedup", "org_id", "input_hash", "status"),
        # Deduplication: one successful call per (org, document, call_type)
        UniqueConstraint("org_id", "document_id", "call_type", "status",
                        name="uq_ai_call_success", postgresql_where="status = 'SUCCEEDED'"),
    )
```

### LLMExtractionResult (Data Class)

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class LLMExtractionResult:
    """Result of an LLM extraction call"""
    raw_output: str  # Raw JSON string from LLM
    parsed_json: Optional[dict]  # Parsed JSON or None if invalid
    provider: str  # "openai"
    model: str  # "gpt-4o-mini"
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    latency_ms: int
    cost_micros: int
    warnings: list[str]  # Non-critical issues
```

## Relationships and Constraints

### Multi-Tenant Isolation
- All queries MUST filter by `org_id`
- Budget checks aggregate cost_micros per org_id per day

### Document → AICallLog
- Nullable FK (some calls not document-specific, e.g., customer lookup)
- ON DELETE SET NULL (preserve logs even if document deleted)

### Deduplication Logic
- Unique constraint prevents multiple successful calls for same (org_id, document_id, call_type)
- `input_hash` allows deduplication across document reuploads (same SHA256)

### Immutability
- ai_call_log records are INSERT-only (never UPDATE/DELETE)
- Provides complete audit trail

## Indexes and Performance

### Cost Aggregation Query
```sql
-- Daily cost per org
SELECT
    org_id,
    DATE(created_at) AS date,
    SUM(cost_micros) AS total_cost_micros,
    COUNT(*) AS call_count
FROM ai_call_log
WHERE org_id = $1
  AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY org_id, DATE(created_at)
ORDER BY date DESC;

-- Uses index: idx_ai_call_log_cost (org_id, created_at)
```

### Budget Check Query (Cached in Redis)
```sql
-- Today's usage
SELECT SUM(cost_micros)
FROM ai_call_log
WHERE org_id = $1
  AND created_at >= DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC');

-- Uses index: idx_ai_call_log_cost
```

### Deduplication Query
```sql
-- Find existing successful extraction
SELECT *
FROM ai_call_log
WHERE org_id = $1
  AND input_hash = $2
  AND status = 'SUCCEEDED'
  AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC
LIMIT 1;

-- Uses index: idx_ai_call_log_dedup
```

## Migration Scripts

```sql
-- Create ai_call_log table
CREATE TABLE ai_call_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(id),
    call_type VARCHAR(50) NOT NULL,
    document_id UUID REFERENCES document(id) ON DELETE SET NULL,

    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,

    tokens_in INTEGER,
    tokens_out INTEGER,
    latency_ms INTEGER NOT NULL,
    cost_micros BIGINT NOT NULL DEFAULT 0,

    status VARCHAR(20) NOT NULL,
    error_json JSONB,

    input_hash VARCHAR(64),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_ai_call_log_org ON ai_call_log(org_id);
CREATE INDEX idx_ai_call_log_cost ON ai_call_log(org_id, created_at);
CREATE INDEX idx_ai_call_log_monitoring ON ai_call_log(org_id, call_type, status);
CREATE INDEX idx_ai_call_log_dedup ON ai_call_log(org_id, input_hash, status);

-- Deduplication constraint
CREATE UNIQUE INDEX uq_ai_call_success
ON ai_call_log(org_id, document_id, call_type, status)
WHERE status = 'SUCCEEDED';
```

## Validation Rules

### Pydantic Models

```python
from pydantic import BaseModel, Field, validator

class AICallLogCreate(BaseModel):
    org_id: UUID
    call_type: AICallType
    document_id: Optional[UUID] = None
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100)
    tokens_in: Optional[int] = Field(None, ge=0)
    tokens_out: Optional[int] = Field(None, ge=0)
    latency_ms: int = Field(ge=0)
    cost_micros: int = Field(ge=0)
    status: str = Field(pattern="^(SUCCEEDED|FAILED)$")
    error_json: Optional[dict] = None
    input_hash: Optional[str] = Field(None, min_length=64, max_length=64)

    @validator("error_json")
    def error_required_if_failed(cls, v, values):
        if values.get("status") == "FAILED" and not v:
            raise ValueError("error_json required when status=FAILED")
        return v
```
