"""OrderFlow Backend - Main FastAPI Application

Multi-Tenant B2B Order Automation Platform

This module creates and configures the main FastAPI application, including:
- All API routers (auth, users, tenancy, customers, products, etc.)
- Middleware (request ID correlation, tenant scoping, CORS)
- Exception handlers
- Health and observability endpoints

SSOT Reference: §2 (System Architecture), §8 (API Design)
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

# Observability
from .observability.logging_config import configure_logging
from .observability.middleware import RequestIDMiddleware
from .observability.router import router as observability_router

# Authentication & Authorization
from .auth.router import router as auth_router
from .users.router import router as users_router

# Tenancy
from .tenancy.router import router as tenancy_router
from .tenancy.middleware import TenantContextMiddleware

# Domain Routers
from .customers.router import router as customers_router
from .customers.router import import_router as customer_import_router
from .catalog.router import router as products_router
from .inbox.router import router as inbox_router
from .uploads.router import router as uploads_router
from .draft_orders.router import router as draft_orders_router
from .draft_orders.router_approve import router as draft_orders_approve_router
from .pricing.router import router as pricing_router
from .matching.router import router as matching_router
from .audit.router import router as audit_router
from .retention.router import router as retention_router

# API v1 Routers
from .api.v1.documents.router import router as documents_router
from .api.v1.extraction.router import router as extraction_router
from .api.v1.validation.router import router as validation_router
from .api.v1.customer_detection.routes import router as customer_detection_router

# Feedback & Analytics
from .feedback.endpoints import router as feedback_router
from .feedback.analytics import router as analytics_router

# Configure logging
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_format=os.getenv("LOG_JSON", "true").lower() == "true"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Handles startup and shutdown events for the application.
    - Startup: Initialize connections, warm caches
    - Shutdown: Close connections, cleanup resources
    """
    # Startup
    logger.info("OrderFlow API starting up...")
    logger.info(f"Environment: {os.getenv('ENV', 'development')}")
    logger.info(f"Debug mode: {os.getenv('DEBUG', 'false')}")

    yield

    # Shutdown
    logger.info("OrderFlow API shutting down...")


# Create FastAPI application
app = FastAPI(
    title="OrderFlow API",
    description="Multi-Tenant B2B Order Automation Platform for DACH Region",
    version="0.1.0",
    docs_url="/docs" if os.getenv("ENV", "development") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENV", "development") != "production" else None,
    openapi_url="/openapi.json" if os.getenv("ENV", "development") != "production" else None,
    lifespan=lifespan,
)


# =============================================================================
# MIDDLEWARE CONFIGURATION
# =============================================================================

# Request ID Middleware (must be first for proper correlation)
app.add_middleware(RequestIDMiddleware)

# CORS Middleware
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Tenant Context Middleware (extracts org_id from JWT for logging/metrics)
app.add_middleware(TenantContextMiddleware)


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors.

    Returns a structured error response with field-level details.
    """
    logger.warning(
        f"Validation error on {request.method} {request.url.path}",
        extra={"errors": exc.errors()}
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": exc.errors(),
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(
    request: Request,
    exc: SQLAlchemyError
) -> JSONResponse:
    """Handle database errors.

    Logs the full error but returns a generic message to prevent
    information leakage.
    """
    logger.error(
        f"Database error on {request.method} {request.url.path}",
        exc_info=exc
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "database_error",
            "message": "A database error occurred. Please try again later.",
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handle uncaught exceptions.

    Catches all unhandled exceptions and returns a generic error response.
    Full details are logged but not exposed to the client.
    """
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}",
        exc_info=exc
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


# =============================================================================
# ROUTER REGISTRATION
# =============================================================================

# Observability (health, metrics, ready)
app.include_router(observability_router)

# Authentication & Authorization
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")

# Tenancy Management
app.include_router(tenancy_router, prefix="/api/v1")

# Customer Management
app.include_router(customers_router, prefix="/api/v1")
app.include_router(customer_import_router, prefix="/api/v1/customers")

# Product Catalog
app.include_router(products_router, prefix="/api/v1")

# Inbox & Document Handling
app.include_router(inbox_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")

# Extraction Pipeline
app.include_router(extraction_router, prefix="/api/v1")

# Draft Orders
app.include_router(draft_orders_router, prefix="/api/v1")
app.include_router(draft_orders_approve_router, prefix="/api/v1")

# Matching & SKU Mapping
app.include_router(matching_router)

# Pricing
app.include_router(pricing_router, prefix="/api/v1")

# Validation
app.include_router(validation_router, prefix="/api/v1")

# Customer Detection
app.include_router(customer_detection_router, prefix="/api/v1")

# Feedback & Learning
app.include_router(feedback_router)
app.include_router(analytics_router)

# Audit & Compliance
app.include_router(audit_router, prefix="/api/v1")
app.include_router(retention_router, prefix="/api/v1")


# =============================================================================
# ROOT ENDPOINTS
# =============================================================================

@app.get("/", include_in_schema=False)
async def root() -> dict[str, Any]:
    """Root endpoint - API information."""
    return {
        "name": "OrderFlow API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs" if os.getenv("ENV", "development") != "production" else None,
    }


@app.get("/api/v1", include_in_schema=False)
async def api_root() -> dict[str, Any]:
    """API v1 root endpoint."""
    return {
        "version": "v1",
        "status": "active",
        "endpoints": {
            "auth": "/api/v1/auth",
            "users": "/api/v1/users",
            "customers": "/api/v1/customers",
            "products": "/api/v1/products",
            "inbox": "/api/v1/inbox",
            "documents": "/api/v1/documents",
            "draft_orders": "/api/v1/draft-orders",
            "extractions": "/api/v1/extractions",
            "validation": "/api/v1/validation",
        }
    }


# =============================================================================
# APPLICATION FACTORY (for testing)
# =============================================================================

def create_app() -> FastAPI:
    """Application factory for creating test instances.

    Returns the configured FastAPI application instance.
    Useful for testing and ASGI server configuration.
    """
    return app


# =============================================================================
# DEVELOPMENT SERVER
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENV", "development") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
