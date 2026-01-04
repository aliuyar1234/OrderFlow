# Tasks: LLM Extractors

**Feature Branch**: `012-extractors-llm`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Create LLM extractor at `backend/src/extraction/extractors/llm_extractor.py`
- [x] T002 Create extraction prompts directory

## Phase 2: [US1] LLM Fallback for Low Confidence

- [x] T003 [US1] Check extraction_confidence threshold (<0.60)
- [x] T004 [US1] Trigger LLM extraction when rule-based fails
- [x] T005 [US1] Pass rule-based output as context to LLM
- [x] T006 [US1] Use LLM to fill missing fields

## Phase 3: [US2] Vision-Based PDF Extraction

- [x] T007 [US2] Convert PDF first N pages to images
- [x] T008 [US2] Encode images as base64
- [x] T009 [US2] Send to vision-enabled LLM
- [x] T010 [US2] Parse structured response
- [x] T011 [US2] Set extractor_version to 'llm_v1' (covers both text and vision)

## Phase 4: [US3] Structured JSON Output

- [x] T012 [US3] Create extraction prompt template
- [x] T013 [US3] Request JSON output in canonical schema
- [x] T014 [US3] Validate LLM response against schema
- [x] T015 [US3] Handle invalid JSON responses
- [x] T016 [US3] Retry with clarification on parse errors

## Phase 5: Decision Logic Integration

- [x] T017 Implement decision tree per SSOT §7.2
- [x] T018 Check text_coverage_ratio for PDF
- [x] T019 Route to rule-based or LLM based on criteria
- [x] T020 Track which extractor was used
- [x] T021 Calculate combined confidence score

## Phase 6: Polish

- [x] T022 Add LLM extraction metrics (cost, tokens)
- [x] T023 Implement vision page limit (max pages configurable)
- [x] T024 Add extraction quality feedback loop (layout fingerprinting)
- [x] T025 Document prompt engineering guidelines
