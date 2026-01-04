# Data Model: Observability & AI Monitoring

## Entity Definitions

### AICallLog

Tracks all LLM and embedding API calls for cost monitoring and quality analysis.

**Schema**:
```python
class AICallLog(Base):
    __tablename__ = "ai_call_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organization.id"), nullable=False, index=True)

    # Call classification
    call_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: extraction | embedding | validation | customer_detect

    # Provider details
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    # Providers: openai | anthropic | local

    model: Mapped[str] = mapped_column(String(100), nullable=False)
    # Models: gpt-4o | gpt-4o-mini | claude-3-5-sonnet | text-embedding-ada-002

    # Usage metrics
    tokens_in: Mapped[int] = mapped_column(nullable=True)
    tokens_out: Mapped[int] = mapped_column(nullable=True)
    cost_micros: Mapped[int] = mapped_column(nullable=True)  # Cost in micros (1 micro = $0.000001)

    # Performance
    latency_ms: Mapped[int] = mapped_column(nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Status: success | error

    error_type: Mapped[str] = mapped_column(String(100), nullable=True)
    # Error types: rate_limit | timeout | invalid_request | api_error

    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Tracing
    request_id: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(100), nullable=True)  # OpenTelemetry trace ID

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
```

**Indexes**:
```sql
CREATE INDEX idx_ai_call_log_org_date ON ai_call_log(org_id, created_at DESC);
CREATE INDEX idx_ai_call_log_type ON ai_call_log(org_id, call_type, created_at DESC);
CREATE INDEX idx_ai_call_log_request ON ai_call_log(request_id);
```

---

### Cost Calculation

**Pricing Table** (configurable):
```python
AI_PRICING = {
    ("openai", "gpt-4o"): {"input": 2.5, "output": 10.0},  # per 1M tokens (USD)
    ("openai", "gpt-4o-mini"): {"input": 0.15, "output": 0.60},
    ("openai", "text-embedding-ada-002"): {"input": 0.10, "output": 0.0},
    ("anthropic", "claude-3-5-sonnet-20241022"): {"input": 3.0, "output": 15.0}
}

def calculate_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> int:
    """Calculate cost in micros."""
    rates = AI_PRICING.get((provider, model), {"input": 0, "output": 0})
    cost_usd = (tokens_in * rates["input"] + tokens_out * rates["output"]) / 1_000_000
    return int(cost_usd * 1_000_000)  # Convert to micros
```

---

## Migration

```python
"""Add ai_call_log table

Revision ID: 025_observability
Revises: 024_feedback_learning
Create Date: 2025-12-27
"""

def upgrade():
    op.create_table(
        'ai_call_log',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('org_id', UUID, sa.ForeignKey('organization.id'), nullable=False),
        sa.Column('call_type', sa.String(50), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('tokens_in', sa.Integer, nullable=True),
        sa.Column('tokens_out', sa.Integer, nullable=True),
        sa.Column('cost_micros', sa.BigInteger, nullable=True),
        sa.Column('latency_ms', sa.Integer, nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('trace_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False)
    )

    op.create_index('idx_ai_call_log_org_date', 'ai_call_log', ['org_id', 'created_at'])
    op.create_index('idx_ai_call_log_type', 'ai_call_log', ['org_id', 'call_type', 'created_at'])
```
