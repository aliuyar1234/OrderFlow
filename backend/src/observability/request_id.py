"""Request ID management for request correlation.

Provides context-aware request ID generation and propagation across async operations.

SSOT Reference: §3.2 (Observability)
"""

import uuid
from contextvars import ContextVar
from typing import Optional

# Context variable for request_id (async-safe)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def generate_request_id() -> str:
    """Generate a new unique request ID.

    Returns:
        str: UUID v4 request ID
    """
    return str(uuid.uuid4())


def get_request_id() -> str:
    """Get current request ID from context.

    Returns:
        str: Current request ID or "no-request-id" if not set
    """
    return request_id_var.get() or "no-request-id"


def set_request_id(request_id: str) -> None:
    """Set request ID in current context.

    Args:
        request_id: Request ID to set
    """
    request_id_var.set(request_id)
