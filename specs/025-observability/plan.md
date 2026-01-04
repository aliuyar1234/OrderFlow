# Implementation Plan: Observability & AI Monitoring

**Branch**: `025-observability` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

This feature implements production-grade observability infrastructure. Every API request receives a unique request_id propagated through logs and background jobs for tracing. All logs are structured JSON format. A `/metrics` endpoint exposes Prometheus metrics for monitoring (AI calls, latency, confidence scores). Every LLM and embedding API call is logged to ai_call_log with provider, model, tokens, cost, and latency for cost tracking and quality monitoring. An AI Monitor UI dashboard provides administrators visibility into AI costs, error rates, and performance trends. Optional OpenTelemetry integration enables distributed tracing across services.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, prometheus_client, OpenTelemetry SDK (optional), contextvars
**Storage**: PostgreSQL 16 (ai_call_log, audit_log tables)
**Testing**: pytest
**Target Platform**: Linux server
**Project Type**: web (backend API + frontend dashboard)
**Performance Goals**: /metrics responds < 100ms, log overhead < 5ms per request, ai_call_log inserts < 10ms
**Constraints**: Structured logs required, 90-day AI log retention, cost accuracy within 5%
**Scale/Scope**: 100k req/day, 10k AI calls/day, 10GB logs/day

## Constitution Check

| Principle | Status | Compliance Notes |
|-----------|--------|------------------|
| **I. SSOT-First** | ✅ PASS | Metrics per §3.2, ai_call_log schema per §5.4.16, AI Monitor UI per §9.7 |
| **II. Hexagonal Architecture** | ✅ PASS | Observability is cross-cutting concern (middleware), no domain coupling |
| **III. Multi-Tenant Isolation** | ✅ PASS | All logs/metrics filter by org_id, AI Monitor shows only org's data |
| **IV. Idempotent Processing** | ✅ PASS | Log capture is additive, metrics are counters/histograms (idempotent increment) |
| **V. AI-Layer Deterministic Control** | ✅ PASS | AI call logging captures input_hash (not full prompt) per §11.3, cost calculated deterministically |
| **VI. Observability First-Class** | ✅ PASS | Core feature, implements structured logging, Prometheus metrics, tracing |
| **VII. Test Pyramid Discipline** | ✅ PASS | Unit tests for cost calculation, component tests for logging, integration tests for metrics scrape |

**GATE STATUS**: ✅ APPROVED

## Project Structure

```text
specs/025-observability/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── openapi.yaml

backend/
├── src/
│   ├── middleware/
│   │   ├── request_id.py          # Request ID generation
│   │   └── logging_middleware.py  # Structured logging
│   ├── services/
│   │   ├── ai_logger.py            # AI call logging
│   │   └── metrics_service.py      # Prometheus metrics
│   ├── api/
│   │   ├── metrics.py              # GET /metrics
│   │   └── ai_calls.py             # GET /ai/calls
│   └── models/
│       └── ai_call_log.py          # AICallLog entity
└── tests/

frontend/
├── src/
│   └── pages/
│       └── AIMonitor.tsx           # AI cost dashboard
```

**Structure Decision**: Web application for API + UI dashboard.
