<!--
================================================================================
SYNC IMPACT REPORT
================================================================================
Version Change: 0.0.0 → 1.0.0 (MAJOR - Initial constitution from SSOT_SPEC.md)

Modified Principles: N/A (initial creation)

Added Sections:
  - 7 Core Principles derived from SSOT_SPEC.md §0, §3.1, §7, §11, §13
  - Technology Stack section from SSOT_SPEC.md §3.2
  - Quality Gates section from SSOT_SPEC.md §13

Removed Sections: N/A (initial creation)

Templates Status:
  - .specify/templates/plan-template.md: ✅ Compatible (Constitution Check section exists)
  - .specify/templates/spec-template.md: ✅ Compatible (Requirements section aligns)
  - .specify/templates/tasks-template.md: ✅ Compatible (Phase structure matches)

Follow-up TODOs: None
================================================================================
-->

# OrderFlow Constitution

## Core Principles

### I. SSOT-First (Single Source of Truth)

The `SSOT_SPEC.md` document is the **only** authoritative source for implementation,
tests, deployment, and operations. All system requirements, data models, endpoints,
states, rules, test cases, and acceptance criteria are defined there.

**Non-Negotiable Rules:**
- SSOT document > Code > Comments > Tickets (conflict resolution order)
- System changes MUST be versioned through SSOT document updates (Changelog §0.1)
- No external references are required to build OrderFlow
- Libraries/frameworks may be used, but all specs are SSOT-defined

**Rationale:** Eliminates ambiguity, ensures single point of truth for all stakeholders.

### II. Hexagonal Architecture (Ports & Adapters)

Domain and Use-Cases MUST remain independent of infrastructure. Every external
dependency is accessed through defined Port interfaces with swappable Adapters.

**Non-Negotiable Rules:**
- Domain logic MUST NOT import infrastructure code directly
- All external integrations MUST implement defined Port interfaces (§3.5):
  - `InboundChannelPort`: Email, Upload, EDI/API
  - `ExtractorPort`: PDF/Excel/CSV Extractor (Rule-Based + LLM)
  - `LLMProviderPort`: LLM provider adapters (OpenAI/Anthropic/Local)
  - `EmbeddingProviderPort`: Embedding provider adapters
  - `MatcherPort`: SKU Matching strategies (trigram/embedding/hybrid)
  - `ValidatorPort`: Validation rule sets
  - `ERPConnectorPort`: Export/Push/Status-Sync
- Adapters MUST be testable in isolation with mocked dependencies

**Rationale:** Enables provider swapping, testability, and future extensibility.

### III. Multi-Tenant Isolation

Data MUST be strictly separated via `org_id` from day one. Cross-tenant data
access is a critical security violation.

**Non-Negotiable Rules:**
- Every database table (except global system tables) MUST include `org_id UUID NOT NULL`
- Every query MUST filter by `org_id` (server-side enforced, never client-trusted)
- API endpoints MUST enforce `org_id` from authenticated JWT, not request params
- ID guessing attacks MUST return 404 (not 403) to prevent enumeration

**Rationale:** B2B SaaS requires absolute tenant isolation for compliance and trust.

### IV. Idempotent Processing

All background jobs, workers, and processing pipelines MUST be idempotent.
Running a job multiple times with the same input MUST produce the same result.

**Non-Negotiable Rules:**
- `process_document(document_id)` MUST NOT create duplicate drafts on retry
- `ai_call_log` uses `input_hash` for deduplication (§5.5.1)
- ERP Push MUST respect `Idempotency-Key` header (§8.6)
- Celery tasks MUST handle retries gracefully without side effects

**Rationale:** Distributed systems fail; idempotency ensures reliability and
prevents data corruption during retries.

### V. AI-Layer Deterministic Control

Every LLM/Embedding component MUST be encapsulated via Provider interfaces,
validated, and fallback-capable. AI is a tool, not magic.

**Non-Negotiable Rules:**
- LLM outputs MUST be parsed through strict Pydantic models (§7.5.4)
- Invalid JSON gets exactly 1 repair attempt, then fails gracefully
- Hallucination guards MUST run: Anchor Check, Range Check, Lines Count Check
- Budget/cost gates MUST be enforced (daily budget, max pages, max tokens)
- All AI calls MUST be logged to `ai_call_log` with latency/tokens/cost
- Rule-based extraction is default; LLM only when necessary (§7.2)
- Confidence scores MUST follow defined formulas (§7.8)

**Rationale:** AI unpredictability is managed through strict validation, fallbacks,
cost controls, and observability.

### VI. Observability First-Class

Logs, Tracing, and Metrics are not afterthoughts. They are core features that
MUST be implemented alongside functionality.

**Non-Negotiable Rules:**
- All logs MUST be structured JSON format
- OpenTelemetry tracing MUST cover API + Worker paths
- Prometheus metrics endpoint MUST expose:
  - `orderflow_ai_calls_total{type,status}`
  - `orderflow_ai_latency_ms_bucket{type}`
  - `orderflow_embedding_jobs_queue_depth`
  - `orderflow_extraction_confidence_histogram`
- Every API request MUST have a `request_id` for correlation
- Sentry-compatible error tracking MUST be available (optional activation)

**Rationale:** Production debugging without observability is blind troubleshooting.

### VII. Test Pyramid Discipline

Testing follows a strict pyramid with defined coverage gates. No feature ships
without passing all test levels.

**Non-Negotiable Rules:**
- **Unit Tests**: 90%+ coverage for domain modules (extraction, matching, validation)
- **Component Tests**: Extractor/Matcher/Validator/CustomerDetect with fixtures
- **Integration Tests**: API + DB + ObjectStorage + Redis + pgvector
- **Contract Tests**: API schemas (Pydantic) snapshot-tested for stability
- **E2E Tests**: Happy path (Inbox → Draft → Customer → Mapping → Approve → Push)
- AI components MUST be tested with mocked providers (determinism)
- LLM tests use fixture responses; Embedding tests use fixture vectors

**Rationale:** B2B order processing has low tolerance for errors; comprehensive
testing prevents costly mistakes.

## Technology Stack

The following stack is mandated by SSOT_SPEC.md §3.2:

**Backend:**
- Python 3.12 + FastAPI (Pydantic for validation)
- SQLAlchemy 2.x + Alembic (migrations)
- Celery + Redis (background jobs)
- PostgreSQL 16 with `pg_trgm` + `pgvector` extensions
- S3-compatible Object Storage (MinIO locally, S3 in prod)

**Frontend:**
- Next.js (React) + TypeScript
- TanStack Query (cache/retry/invalidation)
- DataGrid + PDF Viewer components

**Rationale:** Stack minimizes risk for document processing, enables clear module
separation, is cloud-ready, and delivers MVP quickly without blocking scale.

## Quality Gates

Before any feature is considered complete, it MUST pass:

| Gate | Criteria | Source |
|------|----------|--------|
| Unit Coverage | ≥90% for domain modules | §13.3 |
| Integration | All API endpoints tested | §13.3 |
| E2E | Happy path green | §13.3 |
| Linting | Zero errors from configured linters | §13.3 |
| Type Check | Zero type errors | §13.3 |
| CI Pipeline | All checks pass | §13.3 |
| API Contract | Pydantic schemas unchanged or versioned | §13.3 |

**Definition of Done (Global):**
- Code reviewed and merged
- All test levels pass
- Documentation updated if public API changed
- SSOT_SPEC.md updated if behavior changed

## Governance

### Authority
This Constitution derives authority from `SSOT_SPEC.md` and codifies its
architectural principles for development guidance. The SSOT document remains
the ultimate authority.

### Amendments
1. Constitution changes MUST be documented with version bump rationale
2. MAJOR: Principle removal or redefinition (backward incompatible)
3. MINOR: New principle/section added or materially expanded
4. PATCH: Clarifications, wording, typos

### Compliance
- All PRs MUST verify compliance with Core Principles
- Constitution Check in `plan-template.md` MUST pass before implementation
- Violations require explicit justification in Complexity Tracking table

### Runtime Guidance
For day-to-day development decisions, refer to:
- `SSOT_SPEC.md` for detailed specifications
- `.specify/templates/` for workflow templates
- `docs/` for operational documentation

**Version**: 1.0.0 | **Ratified**: 2025-12-27 | **Last Amended**: 2025-12-27
