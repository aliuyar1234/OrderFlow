"""Prometheus metrics for OrderFlow.

Defines and exposes operational metrics for monitoring and alerting.

SSOT Reference: §3.2 (Observability), FR-006 (Prometheus Metrics)
"""

from prometheus_client import Counter, Histogram, Gauge

# Document processing metrics
documents_processed_total = Counter(
    "orderflow_documents_processed_total",
    "Total number of documents processed",
    ["org_id", "source", "status"]  # source: email|upload, status: success|error
)

# Extraction metrics
extraction_duration_seconds = Histogram(
    "orderflow_extraction_duration_seconds",
    "Time spent on document extraction in seconds",
    ["extraction_type"],  # type: pdf|excel|csv
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

extraction_confidence_histogram = Histogram(
    "orderflow_extraction_confidence",
    "Extraction confidence score distribution",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# AI call metrics
ai_calls_total = Counter(
    "orderflow_ai_calls_total",
    "Total AI API calls",
    ["call_type", "provider", "status"]  # type: extraction|embedding, status: success|error
)

ai_latency_ms = Histogram(
    "orderflow_ai_latency_ms",
    "AI API call latency in milliseconds",
    ["call_type", "provider"],
    buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000]
)

ai_tokens_total = Counter(
    "orderflow_ai_tokens_total",
    "Total AI tokens consumed",
    ["call_type", "provider", "direction"]  # direction: input|output
)

ai_cost_micros_total = Counter(
    "orderflow_ai_cost_micros_total",
    "Total AI cost in micros (1 micro = 0.000001 USD)",
    ["call_type", "provider"]
)

# Order processing metrics
orders_pushed_total = Counter(
    "orderflow_orders_pushed_total",
    "Total orders pushed to ERP",
    ["org_id", "erp_type", "status"]  # erp_type: sap|dynamics|custom, status: success|error
)

orders_approval_rate = Histogram(
    "orderflow_orders_approval_rate",
    "Order approval rate (0.0-1.0)",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Matching metrics
matching_accuracy = Histogram(
    "orderflow_matching_accuracy",
    "SKU matching accuracy score",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Queue depth metrics
embedding_queue_depth = Gauge(
    "orderflow_embedding_jobs_queue_depth",
    "Number of pending embedding jobs"
)

extraction_queue_depth = Gauge(
    "orderflow_extraction_jobs_queue_depth",
    "Number of pending extraction jobs"
)

# Validation metrics
validation_issues_total = Counter(
    "orderflow_validation_issues_total",
    "Total validation issues detected",
    ["issue_type", "severity"]  # issue_type: price|quantity|sku, severity: error|warning
)
