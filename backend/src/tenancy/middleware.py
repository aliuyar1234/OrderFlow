"""Middleware for tenant context extraction and validation.

This module provides middleware components for automatic org_id extraction
from JWT tokens and request context management.

While most endpoints use get_org_id dependency directly, this middleware
can be useful for cross-cutting concerns like logging, metrics, or tracing
where org_id should be available in request context.

SSOT Reference: §11.2 (Automatic Tenant Scoping)
"""

from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import UUID
import jwt

from auth.jwt import decode_token


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and attach org_id to request state.

    This middleware:
    1. Extracts Bearer token from Authorization header
    2. Decodes JWT and extracts org_id claim
    3. Attaches org_id to request.state for access in handlers
    4. Handles missing/invalid tokens gracefully (sets None)

    Note: This middleware is OPTIONAL. Most endpoints should use get_org_id
    dependency instead. Use this only if you need org_id available in
    middleware chain (e.g., for logging, metrics correlation).

    The middleware does NOT validate the token - that's done by get_current_user.
    It only extracts org_id for context. Actual authentication/authorization
    happens in dependencies.

    Usage:
        app.add_middleware(TenantContextMiddleware)

        @app.get("/documents")
        def list_documents(request: Request):
            org_id = request.state.org_id  # UUID or None
            # ... use org_id for logging/metrics ...
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and attach org_id to request.state.

        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in chain

        Returns:
            Response: FastAPI response object
        """
        # Initialize request state
        request.state.org_id = None

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            # No auth header - continue without org_id
            return await call_next(request)

        # Parse Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            # Invalid format - continue without org_id
            return await call_next(request)

        token = parts[1]

        try:
            # Decode token and extract org_id
            payload = decode_token(token)
            org_id_str = payload.get("org_id")

            if org_id_str:
                request.state.org_id = UUID(org_id_str)

        except (jwt.InvalidTokenError, ValueError):
            # Invalid token or org_id - continue without org_id
            # Actual validation happens in get_current_user dependency
            pass

        # Continue to next handler
        return await call_next(request)


def get_org_id_from_request(request: Request) -> UUID | None:
    """Extract org_id from request state (set by TenantContextMiddleware).

    Convenience function for accessing org_id from request.state.
    Returns None if middleware not installed or org_id not available.

    Args:
        request: FastAPI request object

    Returns:
        UUID or None: Organization ID if available

    Example:
        @app.get("/documents")
        def list_documents(request: Request):
            org_id = get_org_id_from_request(request)
            if org_id:
                logger.info(f"Listing documents for org {org_id}")
            ...
    """
    return getattr(request.state, "org_id", None)
