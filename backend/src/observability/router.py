"""Observability API endpoints.

Provides metrics, health checks, and readiness probes for monitoring.

SSOT Reference: §3.2 (Observability)
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from ..database import get_db
from .health import (
    check_database_health,
    check_redis_health,
    check_object_storage_health,
    get_overall_health,
    HealthStatus,
)
from .logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Observability"])


@router.get(
    "/metrics",
    summary="Prometheus metrics endpoint",
    description="Exposes Prometheus metrics for monitoring and alerting",
    include_in_schema=False,  # Hide from OpenAPI docs
)
def metrics():
    """Expose Prometheus metrics.

    Returns metrics in Prometheus exposition format for scraping by
    Prometheus server. Includes all registered metrics from the metrics module.

    Returns:
        Response: Metrics in Prometheus text format
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@router.get(
    "/health",
    summary="Health check endpoint",
    description="Returns health status of system components (database, Redis, object storage)",
    status_code=200,
)
def health_check(db: Session = Depends(get_db)):
    """Check health of all system components.

    Performs connectivity checks for:
    - PostgreSQL database
    - Redis cache
    - S3-compatible object storage

    Returns 200 OK if all components are healthy, 503 if any are unhealthy.

    Args:
        db: Database session

    Returns:
        dict: Health status of each component and overall status
    """
    # Check all components
    components = {
        "database": check_database_health(db),
        "redis": check_redis_health(),
        "object_storage": check_object_storage_health(),
    }

    # Determine overall health
    overall_status = get_overall_health(components)

    # Build response
    response_data = {
        "status": overall_status.value,
        "components": {
            name: {
                "status": comp.status.value,
                "message": comp.message,
                "latency_ms": comp.latency_ms,
            }
            for name, comp in components.items()
        }
    }

    # Return 503 if unhealthy
    status_code = 200 if overall_status != HealthStatus.UNHEALTHY else 503

    return JSONResponse(
        content=response_data,
        status_code=status_code
    )


@router.get(
    "/ready",
    summary="Readiness check endpoint",
    description="Returns readiness status (for Kubernetes readiness probes)",
    status_code=200,
)
def readiness_check(db: Session = Depends(get_db)):
    """Check if application is ready to serve traffic.

    Performs lightweight checks to determine if the application can
    handle requests. Used by Kubernetes readiness probes.

    Args:
        db: Database session

    Returns:
        dict: Readiness status
    """
    # Check database connectivity (minimum requirement)
    db_health = check_database_health(db)

    if db_health.status == HealthStatus.HEALTHY:
        return {
            "status": "ready",
            "message": "Application is ready to serve traffic"
        }
    else:
        return JSONResponse(
            content={
                "status": "not_ready",
                "message": db_health.message
            },
            status_code=503
        )
