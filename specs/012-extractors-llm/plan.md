# Implementation Plan: LLM-Based Extractors (Text + Vision)

**Branch**: `012-extractors-llm` | **Date**: 2025-12-27 | **Spec**: [specs/012-extractors-llm/spec.md](./spec.md)

## Summary

Implement LLM-based extraction for unstructured and scanned PDFs using OpenAI text and vision models. This extractor handles cases where rule-based extraction fails (confidence <0.60, 0 lines, scanned PDFs). Features include: vision LLM for scanned/image PDFs, text LLM for irregular layouts, JSON repair for malformed outputs, hallucination guards (anchor checks, range checks), layout fingerprinting for few-shot learning, and graceful fallback chains. Achieves extraction_confidence ≥0.70 for scanned PDFs, ≥0.75 for text PDFs with complex layouts.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Pydantic, openai, pdfplumber, Pillow (image processing), hashlib (fingerprinting)
**Storage**: PostgreSQL 16 (extraction_run, feedback_event, doc_layout_profile), S3 (page images, extracted text)
**Testing**: pytest, fixtures with mock LLM responses, VCR.py for API replay
**Target Platform**: Linux server (Celery workers)
**Project Type**: Web application (backend extraction service)
**Performance Goals**: Text LLM p95 <12s, vision LLM p95 <25s
**Constraints**: Max 20 pages for LLM, max 40k estimated tokens, budget gates enforced
**Scale/Scope**: Process 500+ LLM extractions/day per org

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. SSOT-First** | ✅ PASS | Implements §7.5 (LLM Extraction), §7.5.3 (Prompt Templates), §7.5.4 (Parsing/Validation), §7.5.5 (Fallback Chain). |
| **II. Hexagonal Architecture** | ✅ PASS | Uses LLMProviderPort from spec 011. Extractor is adapter. Domain logic independent. |
| **III. Multi-Tenant Isolation** | ✅ PASS | All extraction_run, ai_call_log filtered by org_id. |
| **IV. Idempotent Processing** | ✅ PASS | Deduplication via input_hash. Re-running same extraction yields same result. |
| **V. AI-Layer Deterministic Control** | ✅ PASS | Budget/token/page gates, Pydantic validation, hallucination guards (anchor/range checks), fallback chain. |
| **VI. Observability First-Class** | ✅ PASS | All LLM calls logged via ai_call_log. Extraction metrics tracked. |
| **VII. Test Pyramid Discipline** | ✅ PASS | Unit tests for anchor checks, parsing, confidence. Integration tests with mocked LLM. |

## Project Structure

```text
specs/012-extractors-llm/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── openapi.yaml

backend/
├── src/
│   ├── adapters/
│   │   └── extraction/
│   │       ├── llm_text_extractor.py     # Text-based PDF extraction
│   │       ├── llm_vision_extractor.py   # Vision-based PDF extraction
│   │       ├── json_repair.py            # JSON repair via LLM
│   │       ├── anchor_check.py           # Hallucination detection
│   │       └── layout_fingerprint.py     # Layout fingerprinting
│   ├── services/
│   │   └── extraction_decision.py        # Decision logic (§7.2)
│   └── workers/
│       └── llm_extraction_worker.py      # Celery task
└── tests/
    ├── unit/
    │   ├── test_llm_extractor.py
    │   ├── test_anchor_check.py
    │   └── test_layout_fingerprint.py
    └── integration/
        └── test_llm_extraction_e2e.py
```

**Structure Decision**: Extends extraction module from spec 010. LLM extractors implement same ExtractorPort interface. Decision service orchestrates rule-based → LLM fallback chain.

## Complexity Tracking

No violations detected.
