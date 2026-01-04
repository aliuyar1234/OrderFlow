"""OpenTelemetry distributed tracing (optional).

Provides optional distributed tracing integration for advanced debugging.

SSOT Reference: §3.2 (Observability), FR-018 (OpenTelemetry Support)
"""

import os
from typing import Optional

from .logging_config import get_logger

logger = get_logger(__name__)

# Optional OpenTelemetry imports
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("OpenTelemetry not installed. Tracing disabled.")


def is_tracing_enabled() -> bool:
    """Check if OpenTelemetry tracing is enabled.

    Returns:
        bool: True if OTEL_ENABLED=true and dependencies available
    """
    return OTEL_AVAILABLE and os.getenv("OTEL_ENABLED", "false").lower() == "true"


def configure_tracing(service_name: str = "orderflow") -> Optional[object]:
    """Configure OpenTelemetry tracing if enabled.

    Args:
        service_name: Service name for traces

    Returns:
        Optional[TracerProvider]: Tracer provider if enabled, None otherwise
    """
    if not is_tracing_enabled():
        logger.info("OpenTelemetry tracing is disabled")
        return None

    try:
        # Configure tracer provider
        tracer_provider = TracerProvider()
        trace.set_tracer_provider(tracer_provider)

        # Configure OTLP exporter
        otlp_endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "http://localhost:4317"
        )

        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)

        logger.info(
            f"OpenTelemetry tracing configured",
            extra={
                "service_name": service_name,
                "otlp_endpoint": otlp_endpoint,
            }
        )

        return tracer_provider

    except Exception as e:
        logger.error(
            f"Failed to configure OpenTelemetry: {e}",
            exc_info=True
        )
        return None


def instrument_fastapi(app) -> None:
    """Instrument FastAPI application with OpenTelemetry.

    Args:
        app: FastAPI application instance
    """
    if not is_tracing_enabled():
        return

    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}", exc_info=True)


def instrument_sqlalchemy(engine) -> None:
    """Instrument SQLAlchemy engine with OpenTelemetry.

    Args:
        engine: SQLAlchemy engine instance
    """
    if not is_tracing_enabled():
        return

    try:
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("SQLAlchemy instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument SQLAlchemy: {e}", exc_info=True)


def get_tracer(name: str):
    """Get an OpenTelemetry tracer.

    Args:
        name: Tracer name (typically __name__)

    Returns:
        Tracer instance or NoOp tracer if disabled
    """
    if not is_tracing_enabled():
        # Return NoOp tracer
        return trace.get_tracer(name)

    return trace.get_tracer(name)


def get_current_trace_id() -> Optional[str]:
    """Get current trace ID from active span.

    Returns:
        Optional[str]: Trace ID if available, None otherwise
    """
    if not is_tracing_enabled():
        return None

    try:
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            trace_id = format(span.get_span_context().trace_id, '032x')
            return trace_id
    except Exception:
        pass

    return None
