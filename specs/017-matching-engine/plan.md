# Implementation Plan: Matching Engine (Hybrid SKU Matching)

**Branch**: `017-matching-engine` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

Matching Engine provides hybrid SKU matching combining confirmed mappings, trigram similarity, and vector embeddings with UoM/price penalties. The pipeline checks confirmed sku_mapping first (0.99 confidence), then runs trigram search (pg_trgm on customer_sku vs internal_sku) and vector search (pgvector cosine similarity) in parallel, merges candidates, calculates match_confidence per §7.7.6 formula (0.62*trigram + 0.38*embedding * P_uom * P_price), and auto-applies if confidence ≥0.92 with ≥0.10 gap to second candidate. Ops can confirm/reject matches, creating/updating sku_mapping entries with support_count tracking. Mappings with reject_count ≥ threshold are auto-deprecated. Top 5 candidates stored in match_debug_json for UI display and debugging.

**Technical Approach**: Python service with hybrid scorer, trigram + vector search, penalty calculators. Celery job for async matching. Feedback events logged for learning loop analytics.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: SQLAlchemy, pg_trgm, pgvector, Celery
**Storage**: PostgreSQL 16 (pg_trgm + pgvector extensions)
**Testing**: pytest with accuracy tests (200 test queries, Top 1/3/5 accuracy)
**Target Platform**: Linux server
**Project Type**: Backend service (matching pipeline)
**Performance Goals**: Match line <500ms p95, trigram search <50ms, vector search <50ms
**Constraints**: Multi-tenant, confidence formula exactness, idempotent mapping updates
**Scale/Scope**: 10k products, 100k sku_mappings, 1000 concurrent matches

## Constitution Check

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | Hybrid formula §7.7.6, sku_mapping schema §5.4.12, thresholds §7.7.7 |
| **II. Hexagonal Architecture** | ✅ Pass | MatcherPort with trigram/embedding/hybrid implementations |
| **III. Multi-Tenant Isolation** | ✅ Pass | All queries filter by org_id, sku_mapping per org |
| **IV. Idempotent Processing** | ✅ Pass | Mapping upsert (increment support_count), matching deterministic |
| **V. AI-Layer Deterministic Control** | ✅ Pass | Embedding search is deterministic (same vector → same results) |
| **VI. Observability First-Class** | ✅ Pass | match_debug_json logging, feedback_event tracking, metrics |
| **VII. Test Pyramid Discipline** | ✅ Pass | Unit (scoring formula), Integration (E2E matching), Accuracy (semantic tests) |

## Project Structure

### Documentation

```text
specs/017-matching-engine/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
└── spec.md
```

### Source Code

```text
backend/
├── src/
│   ├── models/
│   │   └── sku_mapping.py          # SkuMapping model (§5.4.12)
│   ├── services/
│   │   └── matching/
│   │       ├── matcher_port.py     # Abstract matcher interface
│   │       ├── trigram_matcher.py  # pg_trgm search
│   │       ├── embedding_matcher.py # pgvector search
│   │       ├── hybrid_matcher.py   # Main hybrid pipeline
│   │       ├── scorer.py           # Match confidence calculator
│   │       ├── penalty_calculator.py # UoM/price penalties
│   │       ├── mapping_feedback.py # Confirm/reject logic
│   │       └── __tests__/
│   ├── workers/
│   │   └── tasks/
│   │       └── match_draft_lines.py # Celery job
│   └── api/
│       └── v1/
│           └── matching.py         # Endpoints (confirm, rerun)
└── tests/
    ├── unit/
    │   ├── test_scorer.py
    │   └── test_penalty_calculator.py
    ├── integration/
    │   └── test_hybrid_matching.py
    └── accuracy/
        └── test_match_accuracy.py  # 200 test queries, accuracy metrics
```

**Structure Decision**: Matching service separated into discrete components (trigram, embedding, hybrid scorer) for testability. Penalty calculations isolated for formula verification.

## Complexity Tracking

> **No violations to justify**
