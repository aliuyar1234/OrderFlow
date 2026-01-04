# Implementation Plan: LLM Provider Layer

**Branch**: `011-llm-provider-layer` | **Date**: 2025-12-27 | **Spec**: [specs/011-llm-provider-layer/spec.md](./spec.md)

## Summary

Implement the LLM Provider abstraction layer with OpenAI adapter, comprehensive cost/usage tracking, budget gates, and deduplication. This layer provides a clean interface (`LLMProviderPort`) for all LLM operations, logs every call to `ai_call_log` with tokens/cost/latency, enforces daily budget limits per organization, and implements token/page gates to prevent cost spikes. The layer is provider-agnostic, enabling future provider switches (Anthropic, local models) without changing business logic. All LLM calls are idempotent and observable.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Pydantic, openai (Python SDK v1.x+), SQLAlchemy, Redis (caching)
**Storage**: PostgreSQL 16 (ai_call_log table), Redis (budget tracking cache)
**Testing**: pytest, pytest-mock (mock OpenAI responses), VCR.py (record/replay API calls)
**Target Platform**: Linux server (async API, Celery workers)
**Project Type**: Web application (backend service layer)
**Performance Goals**: Logging overhead <50ms per call, budget check <10ms (cached)
**Constraints**: Track 100% of LLM calls, prevent budget overruns, handle provider failures gracefully
**Scale/Scope**: Support 1000+ LLM calls/day per org, sub-millisecond budget queries

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. SSOT-First** | ✅ PASS | Implements §3.5 (LLMProviderPort), §5.5.1 (ai_call_log), §7.5.1-7.5.2 (Provider Interface), §10.1 (AI Settings) exactly. |
| **II. Hexagonal Architecture** | ✅ PASS | LLMProviderPort is a domain interface. OpenAI adapter is infrastructure. Business logic depends on port, not concrete implementation. |
| **III. Multi-Tenant Isolation** | ✅ PASS | ai_call_log.org_id enforced, budget checks per org_id, no cross-tenant data leakage. |
| **IV. Idempotent Processing** | ✅ PASS | Deduplication via input_hash prevents duplicate LLM calls for same document. Retry-safe logging (upsert semantics). |
| **V. AI-Layer Deterministic Control** | ✅ PASS | Budget gates, token/page limits, cost tracking, structured output validation. All AI outputs validated through Pydantic schemas. |
| **VI. Observability First-Class** | ✅ PASS | 100% of LLM calls logged with provider, model, tokens, cost, latency. Error tracking in error_json. Metrics exposed for monitoring. |
| **VII. Test Pyramid Discipline** | ✅ PASS | Unit tests for port/adapter, budget logic, token estimation. Integration tests with mocked OpenAI. Contract tests for provider interface. |

## Project Structure

### Documentation (this feature)

```text
specs/011-llm-provider-layer/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── contracts/           # Phase 1 output
    └── llm-provider-interface.yaml
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── domain/
│   │   └── ai/
│   │       ├── ports.py                    # LLMProviderPort interface
│   │       ├── models.py                   # LLMExtractionResult, CallType enum
│   │       └── budget.py                   # Budget gate logic
│   ├── adapters/
│   │   └── ai/
│   │       ├── openai_adapter.py           # OpenAI implementation of LLMProviderPort
│   │       ├── token_estimator.py          # Token estimation utils
│   │       └── cost_calculator.py          # Cost calculation from token counts
│   ├── services/
│   │   ├── llm_service.py                  # High-level LLM orchestration with logging
│   │   └── ai_call_logger.py               # ai_call_log persistence
│   └── db/
│       └── models/
│           └── ai_call_log.py              # SQLAlchemy model
└── tests/
    ├── unit/
    │   ├── test_openai_adapter.py
    │   ├── test_budget_gate.py
    │   ├── test_token_estimator.py
    │   └── test_cost_calculator.py
    ├── integration/
    │   └── test_llm_service.py             # End-to-end with mocked OpenAI
    └── fixtures/
        └── openai_responses.json           # Mock API responses
```

**Structure Decision**: Web application backend structure. LLM provider layer is a cross-cutting service used by extraction, customer detection, and other AI features. Port/adapter pattern enables clean testing and future provider swaps.

## Complexity Tracking

No violations detected. All constitution principles are satisfied.
