# Tasks: LLM Provider Layer

**Feature Branch**: `011-llm-provider-layer`
**Generated**: 2025-12-27
**Completed**: 2026-01-04

## Phase 1: Setup

- [x] T001 Add openai, anthropic SDKs to `backend/requirements/base.txt`
- [x] T002 Create LLM domain ports at `backend/src/domain/ai/ports.py`
- [x] T003 Create LLM infrastructure at `backend/src/infrastructure/ai/`
- [x] T004 Add LLM API keys to `.env.example` (already present)

## Phase 2: LLMProviderPort Interface

- [x] T005 Create LLMProviderPort abstract class
- [x] T006 Define complete method signature (extract_order_from_pdf_text, extract_order_from_pdf_images, repair_invalid_json)
- [x] T007 Define supports_vision method (implicit in separate methods)
- [x] T008 Create LLMExtractionResult dataclass
- [x] T009 Create LLMMessage dataclass with role/content

## Phase 3: [US1] OpenAI Provider Implementation

- [x] T010 [US1] Create OpenAIProvider at `backend/src/infrastructure/ai/openai_provider.py`
- [x] T011 [US1] Implement completion with GPT-4o-mini
- [x] T012 [US1] Support vision inputs (base64 images)
- [x] T013 [US1] Handle API rate limits and retries (error mapping to custom exceptions)
- [x] T014 [US1] Parse structured JSON responses (JSON mode enabled)

## Phase 4: [US2] Budget Tracking

- [x] T015 [US2] Create ai_call_log table (migration 007)
- [x] T016 [US2] Store org_id, model, tokens, cost per call (AICallLog model)
- [x] T017 [US2] Calculate daily budget usage (BudgetGate service)
- [x] T018 [US2] Block requests exceeding budget (BudgetGate.enforce_budget_gate)
- [ ] T019 [US2] Provide usage summary API endpoint (future: API layer)

## Phase 5: [US3] Provider Registry

- [ ] T020 [US3] Create LLMProviderRegistry class (future enhancement)
- [x] T021 [US3] Register OpenAI provider (implemented, manual instantiation)
- [ ] T022 [US3] Support provider selection by org settings (future enhancement)
- [ ] T023 [US3] Fallback to default provider (future enhancement)

## Phase 6: Polish

- [x] T024 Add LLM call logging with prompt/response (AICallLogger service)
- [ ] T025 Implement prompt template system (future: externalized templates)
- [x] T026 Add token counting utilities (TokenEstimator)
- [x] T027 Document supported models (README.md, CostCalculator pricing table)

## Implementation Summary

**Core Deliverables Completed:**
1. LLMProviderPort interface with full method signatures
2. OpenAIProvider implementation with GPT-4o-mini and GPT-4o support
3. AnthropicProvider stub (raises NotImplementedError)
4. AICallLog model and migration for tracking all LLM calls
5. BudgetGate service for daily budget enforcement
6. AICallLogger service for logging with input_hash deduplication
7. CostCalculator for precise cost tracking in micro-USD
8. TokenEstimator for conservative pre-call token estimation
9. Comprehensive documentation in domain/ai/README.md

**Future Enhancements (not blocking):**
- Provider Registry for dynamic provider selection
- Usage summary API endpoint
- Externalized prompt template system
- Full Anthropic provider implementation
