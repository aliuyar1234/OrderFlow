"""Observability module for OrderFlow.

Provides structured logging, metrics, tracing, and health checks.

SSOT Reference: §3.2 (Observability), §8.10 (AI Observability)
"""

from .logging_config import configure_logging, get_logger
from .metrics import (
    ai_calls_total,
    ai_latency_ms,
    ai_tokens_total,
    ai_cost_micros_total,
    documents_processed_total,
    extraction_duration_seconds,
    extraction_confidence_histogram,
    orders_pushed_total,
    orders_approval_rate,
    embedding_queue_depth,
    extraction_queue_depth,
    matching_accuracy,
    validation_issues_total,
)
from .request_id import request_id_var, get_request_id, set_request_id, generate_request_id
from .health import HealthStatus, ComponentHealth
from .middleware import RequestIDMiddleware

__all__ = [
    # Logging
    "configure_logging",
    "get_logger",
    # Metrics
    "ai_calls_total",
    "ai_latency_ms",
    "ai_tokens_total",
    "ai_cost_micros_total",
    "documents_processed_total",
    "extraction_duration_seconds",
    "extraction_confidence_histogram",
    "orders_pushed_total",
    "orders_approval_rate",
    "embedding_queue_depth",
    "extraction_queue_depth",
    "matching_accuracy",
    "validation_issues_total",
    # Request ID
    "request_id_var",
    "get_request_id",
    "set_request_id",
    "generate_request_id",
    # Health
    "HealthStatus",
    "ComponentHealth",
    # Middleware
    "RequestIDMiddleware",
]
