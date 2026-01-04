# Tasks: Matching Engine

**Feature Branch**: `017-matching-engine`
**Generated**: 2025-12-27
**Status**: ✅ Complete

## Phase 1: Setup

- [x] T001 Create matching module at `backend/src/matching/`
- [x] T002 Add pgvector extension support (migration ready, deferred to embedding feature)

## Phase 2: Database Schema

- [x] T003 Add sku_mapping table with migration (005_create_sku_mapping_table.py)
- [x] T004 Create SKUMapping SQLAlchemy model
- [x] T005 Add indexes for efficient lookup (org_id, customer_id, customer_sku_norm)
- [x] T006 Add match confidence and status tracking

## Phase 3: Core Matching Implementation

- [x] T007 Create MatcherPort interface (ports.py)
- [x] T008 Implement HybridMatcher with trigram search
- [x] T009 Implement confirmed mapping lookup (learning loop)
- [x] T010 Return top N matches with confidence scores

## Phase 4: Scoring and Penalties

- [x] T011 Implement MatchScorer with hybrid formula (§7.7.6)
- [x] T012 Calculate UoM compatibility penalty
- [x] T013 Calculate price mismatch penalty (stub for future customer_price table)
- [x] T014 Combine trigram + embedding scores with penalties

## Phase 5: Auto-Apply Logic

- [x] T015 Check match confidence >= auto_apply_threshold (0.92)
- [x] T016 Check confidence gap >= auto_apply_gap (0.10)
- [x] T017 Set status to SUGGESTED for auto-applied matches
- [x] T018 Set status to UNMATCHED for low-confidence matches

## Phase 6: API Endpoints

- [x] T019 Create POST /api/v1/mappings/suggest endpoint
- [x] T020 Create POST /api/v1/mappings/confirm endpoint (learning loop)
- [x] T021 Create GET /api/v1/mappings endpoint with filters
- [x] T022 Add Pydantic schemas for request/response validation

## Phase 7: Documentation

- [x] T023 Document matching algorithm in ALGORITHM.md
- [x] T024 Document hybrid scoring formula
- [x] T025 Document learning loop and feedback mechanism
- [x] T026 Document performance characteristics and database requirements

## Implementation Summary

**Completed**:
- ✅ Full hybrid matching pipeline (confirmed mappings → trigram → vector stub)
- ✅ Scoring with UoM and price penalties
- ✅ Learning loop (confirm/reject mappings)
- ✅ Auto-apply logic with thresholds
- ✅ Three REST endpoints (suggest, confirm, list)
- ✅ Comprehensive documentation

**Deferred** (to future features):
- Vector embeddings integration (requires embedding feature 016)
- Price penalty implementation (requires customer_price table)
- Feedback event logging (requires feedback_event table)
- Batch optimization and caching
- Matching worker for async processing

**Files Created**:
1. `backend/src/matching/__init__.py` - Module exports
2. `backend/src/matching/ports.py` - MatcherPort interface
3. `backend/src/matching/hybrid_matcher.py` - Hybrid matching implementation
4. `backend/src/matching/scorer.py` - Confidence scoring with penalties
5. `backend/src/matching/schemas.py` - Pydantic schemas
6. `backend/src/matching/router.py` - API endpoints
7. `backend/src/matching/ALGORITHM.md` - Algorithm documentation
8. `backend/src/models/sku_mapping.py` - SQLAlchemy model
9. `backend/migrations/versions/005_create_sku_mapping_table.py` - Database migration
