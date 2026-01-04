"""Example FastAPI application with observability integration.

This file demonstrates how to integrate OrderFlow's observability features
into a FastAPI application. Use this as a reference when setting up your
application startup.

SSOT Reference: §3.2 (Observability)
"""

import os
from fastapi import FastAPI
from contextlib import asynccontextmanager

from .logging_config import configure_logging, get_logger
from .middleware import RequestIDMiddleware
from .router import router as observability_router
from .tracing import configure_tracing, instrument_fastapi, instrument_sqlalchemy

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info("Application starting up")

    # Configure OpenTelemetry tracing (optional)
    tracer_provider = configure_tracing(service_name="orderflow")
    if tracer_provider:
        instrument_fastapi(app)
        # Instrument SQLAlchemy (if you have an engine reference)
        # from ..database import engine
        # instrument_sqlalchemy(engine)

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Application shutting down")


def create_app() -> FastAPI:
    """Create and configure FastAPI application with observability.

    Returns:
        FastAPI: Configured application instance
    """
    # Configure structured logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    json_format = os.getenv("LOG_JSON", "true").lower() == "true"
    configure_logging(level=log_level, json_format=json_format)

    logger.info("Creating FastAPI application")

    # Create FastAPI app
    app = FastAPI(
        title="OrderFlow",
        description="B2B Order Automation Platform",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add request ID middleware (MUST be first for proper correlation)
    app.add_middleware(RequestIDMiddleware)

    # Include observability endpoints (/metrics, /health, /ready)
    app.include_router(observability_router)

    # Include your other routers here
    # from ..auth.router import router as auth_router
    # from ..audit.router import router as audit_router
    # app.include_router(auth_router)
    # app.include_router(audit_router)

    logger.info("FastAPI application created successfully")

    return app


# Example usage
if __name__ == "__main__":
    import uvicorn

    app = create_app()

    # Run with uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=None,  # Disable uvicorn logging, use our structured logging
    )
