"""DraftOrder status state machine.

Implements status transitions and validation per SSOT §5.2.5.

State Flow:
    NEW → EXTRACTED → NEEDS_REVIEW|READY → APPROVED → PUSHING → PUSHED|ERROR

Terminal States: REJECTED, PUSHED
"""

from enum import Enum
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class DraftOrderStatus(str, Enum):
    """Draft order status enumeration.

    SSOT Reference: §5.2.5 (Status State Machine)
    """
    NEW = "NEW"
    EXTRACTED = "EXTRACTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    READY = "READY"
    APPROVED = "APPROVED"
    PUSHING = "PUSHING"
    PUSHED = "PUSHED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


# Allowed state transitions per SSOT §5.2.5
ALLOWED_TRANSITIONS = {
    DraftOrderStatus.NEW: [DraftOrderStatus.EXTRACTED],
    DraftOrderStatus.EXTRACTED: [
        DraftOrderStatus.NEEDS_REVIEW,
        DraftOrderStatus.READY
    ],
    DraftOrderStatus.NEEDS_REVIEW: [
        DraftOrderStatus.READY,
        DraftOrderStatus.REJECTED
    ],
    DraftOrderStatus.READY: [
        DraftOrderStatus.APPROVED,
        DraftOrderStatus.NEEDS_REVIEW
    ],
    DraftOrderStatus.APPROVED: [DraftOrderStatus.PUSHING],
    DraftOrderStatus.PUSHING: [
        DraftOrderStatus.PUSHED,
        DraftOrderStatus.ERROR
    ],
    DraftOrderStatus.ERROR: [
        DraftOrderStatus.NEEDS_REVIEW,
        DraftOrderStatus.PUSHING
    ],
    DraftOrderStatus.REJECTED: [],  # Terminal state
    DraftOrderStatus.PUSHED: [],  # Terminal state (MVP)
}


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


def validate_transition(
    current_status: DraftOrderStatus,
    new_status: DraftOrderStatus
) -> None:
    """Validate that a state transition is allowed.

    Args:
        current_status: Current draft order status
        new_status: Target status to transition to

    Raises:
        StateTransitionError: If transition is not allowed

    SSOT Reference: §5.2.5 (FR-004)
    """
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise StateTransitionError(
            f"Invalid transition: {current_status.value} -> {new_status.value}. "
            f"Allowed transitions from {current_status.value}: "
            f"{[s.value for s in allowed]}"
        )


def can_transition(
    current_status: DraftOrderStatus,
    new_status: DraftOrderStatus
) -> bool:
    """Check if a state transition is allowed without raising exception.

    Args:
        current_status: Current draft order status
        new_status: Target status to transition to

    Returns:
        True if transition is allowed, False otherwise
    """
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    return new_status in allowed


def get_allowed_transitions(status: DraftOrderStatus) -> List[DraftOrderStatus]:
    """Get list of allowed transitions from a given status.

    Args:
        status: Current status

    Returns:
        List of allowed target statuses
    """
    return ALLOWED_TRANSITIONS.get(status, [])
