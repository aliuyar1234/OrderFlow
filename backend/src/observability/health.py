"""Health check utilities for OrderFlow.

Provides health and readiness checks for monitoring infrastructure components.

SSOT Reference: §3.2 (Observability)
"""

import os
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session
import redis

from .logging_config import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health check status enum."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


@dataclass
class ComponentHealth:
    """Health status for a single component."""
    status: HealthStatus
    message: Optional[str] = None
    latency_ms: Optional[float] = None


def check_database_health(db: Session) -> ComponentHealth:
    """Check PostgreSQL database connectivity and health.

    Args:
        db: Database session

    Returns:
        ComponentHealth: Database health status
    """
    import time
    try:
        start = time.time()
        # Simple query to verify connectivity
        db.execute(text("SELECT 1"))
        latency_ms = (time.time() - start) * 1000

        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Database connection OK",
            latency_ms=round(latency_ms, 2)
        )
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=f"Database error: {str(e)}"
        )


def check_redis_health() -> ComponentHealth:
    """Check Redis connectivity and health.

    Returns:
        ComponentHealth: Redis health status
    """
    import time
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(redis_url, decode_responses=True)

        start = time.time()
        client.ping()
        latency_ms = (time.time() - start) * 1000

        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Redis connection OK",
            latency_ms=round(latency_ms, 2)
        )
    except Exception as e:
        logger.error(f"Redis health check failed: {e}", exc_info=True)
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=f"Redis error: {str(e)}"
        )


def check_object_storage_health() -> ComponentHealth:
    """Check S3-compatible object storage connectivity.

    Returns:
        ComponentHealth: Object storage health status
    """
    import time
    try:
        import boto3
        from botocore.exceptions import ClientError

        s3_endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
        s3_access_key = os.getenv("S3_ACCESS_KEY_ID", "minioadmin")
        s3_secret_key = os.getenv("S3_SECRET_ACCESS_KEY", "minioadmin")

        s3_client = boto3.client(
            's3',
            endpoint_url=s3_endpoint,
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key,
        )

        start = time.time()
        # List buckets to verify connectivity
        s3_client.list_buckets()
        latency_ms = (time.time() - start) * 1000

        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Object storage connection OK",
            latency_ms=round(latency_ms, 2)
        )
    except Exception as e:
        logger.error(f"Object storage health check failed: {e}", exc_info=True)
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=f"Object storage error: {str(e)}"
        )


def get_overall_health(components: Dict[str, ComponentHealth]) -> HealthStatus:
    """Determine overall health from component statuses.

    Args:
        components: Dictionary of component health statuses

    Returns:
        HealthStatus: Overall system health
    """
    if all(c.status == HealthStatus.HEALTHY for c in components.values()):
        return HealthStatus.HEALTHY

    if any(c.status == HealthStatus.UNHEALTHY for c in components.values()):
        return HealthStatus.UNHEALTHY

    return HealthStatus.DEGRADED
