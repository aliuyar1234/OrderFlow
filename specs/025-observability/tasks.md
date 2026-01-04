# Tasks: Observability

**Feature Branch**: `025-observability`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Add OpenTelemetry SDK to backend
- [x] T002 Add structured logging libraries (structlog)
- [x] T003 Configure observability stack (Prometheus, Grafana, Jaeger)

## Phase 2: [US1] Structured Logging

- [x] T004 [US1] Configure structlog for JSON logging
- [x] T005 [US1] Add context processors (org_id, user_id, request_id)
- [x] T006 [US1] Log all API requests with metadata
- [x] T007 [US1] Log extraction events with document_id
- [x] T008 [US1] Log matching decisions with confidence scores
- [x] T009 [US1] Include log levels (DEBUG, INFO, WARNING, ERROR)

## Phase 3: [US2] Metrics Collection

- [x] T010 [US2] Add Prometheus client
- [x] T011 [US2] Track inbound message count by source
- [x] T012 [US2] Track extraction success/failure rates
- [x] T013 [US2] Track matching accuracy metrics
- [x] T014 [US2] Track draft order approval rates
- [x] T015 [US2] Track ERP push success rates
- [x] T016 [US2] Track API response times (p50, p95, p99)

## Phase 4: [US3] Distributed Tracing

- [x] T017 [US3] Configure OpenTelemetry tracing
- [x] T018 [US3] Create spans for API requests
- [x] T019 [US3] Create spans for extraction pipeline
- [x] T020 [US3] Create spans for matching operations
- [x] T021 [US3] Propagate trace context across services
- [x] T022 [US3] Export traces to Jaeger

## Phase 5: [US4] Health Checks

- [x] T023 [US4] Create GET /health endpoint
- [x] T024 [US4] Check database connectivity
- [x] T025 [US4] Check Redis connectivity
- [x] T026 [US4] Check object storage connectivity
- [x] T027 [US4] Return 200 OK if healthy, 503 if unhealthy
- [x] T028 [US4] Include component status details

## Phase 6: Monitoring Dashboards

- [ ] T029 Create Grafana dashboard for API metrics (deferred - infrastructure setup)
- [ ] T030 Create dashboard for extraction pipeline (deferred - infrastructure setup)
- [ ] T031 Create dashboard for matching performance (deferred - infrastructure setup)
- [ ] T032 Create dashboard for ERP push metrics (deferred - infrastructure setup)
- [ ] T033 Set up alerts for error rate spikes (deferred - infrastructure setup)

## Phase 7: Polish

- [x] T034 Add request ID correlation across logs
- [x] T035 Add performance profiling for slow operations
- [x] T036 Document observability setup
- [x] T037 Create runbook for common issues
