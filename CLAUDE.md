# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OrderFlow is a B2B order automation platform for the DACH wholesale/distribution market. It automates the intake of purchase orders (PDF/Excel/CSV) from email or upload, extracts line items, maps customer SKUs to internal product codes, validates against pricing/catalog, and pushes approved orders to ERP systems.

**Architecture:** Modular Monolith with Workers + SMTP Ingest, following Hexagonal Architecture (Ports & Adapters).

## SSOT-First Development

The `SSOT_SPEC.md` file is the **single source of truth** for all system requirements, data models, endpoints, states, rules, and test cases. When conflicts arise: **SSOT_SPEC.md > Code > Comments > Tickets**.

All changes must align with the SSOT document. Reference specific sections (e.g., §5.4.1 for org table schema, §7 for extraction logic) when implementing features.

## Technology Stack

**Backend:**
- Python 3.12 + FastAPI (Pydantic validation)
- SQLAlchemy 2.x + Alembic (migrations)
- Celery + Redis (background jobs)
- PostgreSQL 16 with `pg_trgm` + `pgvector` extensions
- S3-compatible Object Storage (MinIO locally)

**Frontend:**
- Next.js (React) + TypeScript
- TanStack Query

## Core Architectural Constraints

1. **Multi-Tenant Isolation:** Every table includes `org_id UUID NOT NULL`. Every query filters by `org_id` (server-side enforced). Return 404 (not 403) for cross-tenant access attempts.

2. **Hexagonal Architecture:** Domain logic must not import infrastructure code. All external integrations use Port interfaces:
   - `InboundChannelPort`, `ExtractorPort`, `LLMProviderPort`, `EmbeddingProviderPort`, `MatcherPort`, `ValidatorPort`, `ERPConnectorPort`

3. **Idempotent Processing:** All background jobs must be idempotent. Use `input_hash` for AI call deduplication (§5.5.1), `Idempotency-Key` for ERP push (§8.6).

4. **AI Determinism:** LLM outputs parsed through strict Pydantic models. Invalid JSON gets 1 repair attempt, then fails gracefully. Hallucination guards required (Anchor Check, Range Check, Lines Count Check).

## Database Conventions (§5.1)

Every table must include:
- `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- `org_id UUID NOT NULL REFERENCES org(id)` (except global tables)
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

Use TIMESTAMPTZ (not TIMESTAMP), JSONB for flexible config, soft-delete via `deleted_at` where needed.

## Domain Modules

1. **tenancy** - Organizations, multi-tenant settings
2. **auth** - Login, tokens, roles (ADMIN, INTEGRATOR, OPS, VIEWER)
3. **inbox** - InboundMessages (email/upload), dedup
4. **documents** - File storage, rendering, hashing
5. **extraction** - Extraction runs, parsers, LLM fallback
6. **draft_orders** - Draft header/lines, state machine, approvals
7. **catalog** - Products, UoM, customers, price lists
8. **matching** - SKU mapping, suggestions, hybrid search
9. **validation** - Issues, rules, overrides
10. **connectors** - ERP export, dropzone
11. **ai** - Provider ports, call logs, embedding jobs
12. **customer_detection** - Signal ranking, candidate handling
13. **feedback** - Feedback events, learning loop

## Speckit Workflow

This project uses Speckit for specification-driven development. Key commands:

- `/speckit.specify <description>` - Create feature spec from description
- `/speckit.plan` - Generate implementation plan from spec
- `/speckit.tasks` - Break plan into actionable tasks
- `/speckit.clarify` - Clarify underspecified areas
- `/speckit.implement` - Execute implementation

Feature specs live in `specs/<number>-<short-name>/` directories with:
- `spec.md` - Feature specification
- `plan.md` - Implementation plan
- `research.md` - Research findings
- `data-model.md` - Entity definitions
- `contracts/` - API schemas

## Quality Gates

- Unit coverage ≥90% for domain modules
- All API endpoints integration tested
- E2E happy path green
- Zero linting/type errors
- Pydantic schemas unchanged or versioned

## Key State Machines

**DraftOrderStatus:** NEW → EXTRACTED → NEEDS_REVIEW|READY → APPROVED → PUSHING → PUSHED|ERROR

**MappingStatus:** SUGGESTED → CONFIRMED|REJECTED|DEPRECATED

## Observability

- Structured JSON logs
- OpenTelemetry tracing (API + Worker)
- Prometheus metrics: `orderflow_ai_calls_total`, `orderflow_ai_latency_ms_bucket`, etc.
- Every request must have `request_id` for correlation
