"""FastAPI middleware for observability.

Provides request ID generation and logging for all HTTP requests.

SSOT Reference: §3.2 (Observability), FR-001 (Request ID Generation)
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .request_id import generate_request_id, set_request_id, get_request_id
from .logging_config import get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and inject request IDs."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with request ID.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response: HTTP response with X-Request-ID header
        """
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID") or generate_request_id()
        set_request_id(request_id)

        # Log request start
        start_time = time.time()
        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None,
            }
        )

        # Process request
        try:
            response = await call_next(request)

            # Log request completion
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Request completed: {response.status_code}",
                extra={
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Log error
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {str(e)}",
                extra={
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True
            )
            raise
