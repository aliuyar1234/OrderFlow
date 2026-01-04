"""Validation models and enums per SSOT §5.2.6, §5.2.7, §7.3"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class ValidationIssueSeverity(str, Enum):
    """Validation issue severity levels (SSOT §5.2.6)"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ValidationIssueStatus(str, Enum):
    """Validation issue status (SSOT §5.2.7)"""
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    OVERRIDDEN = "OVERRIDDEN"


class ValidationIssueType(str, Enum):
    """Validation issue types (SSOT §7.3)"""
    # Header issues
    MISSING_CUSTOMER = "MISSING_CUSTOMER"
    MISSING_CURRENCY = "MISSING_CURRENCY"

    # Line issues
    MISSING_SKU = "MISSING_SKU"
    UNKNOWN_PRODUCT = "UNKNOWN_PRODUCT"
    MISSING_QTY = "MISSING_QTY"
    INVALID_QTY = "INVALID_QTY"
    MISSING_UOM = "MISSING_UOM"
    UNKNOWN_UOM = "UNKNOWN_UOM"
    UOM_INCOMPATIBLE = "UOM_INCOMPATIBLE"
    MISSING_PRICE = "MISSING_PRICE"
    PRICE_MISMATCH = "PRICE_MISMATCH"
    DUPLICATE_LINE = "DUPLICATE_LINE"
    LOW_CONFIDENCE_EXTRACTION = "LOW_CONFIDENCE_EXTRACTION"
    LOW_CONFIDENCE_MATCH = "LOW_CONFIDENCE_MATCH"
    CUSTOMER_AMBIGUOUS = "CUSTOMER_AMBIGUOUS"
    LLM_OUTPUT_INVALID = "LLM_OUTPUT_INVALID"


@dataclass
class ValidationIssue:
    """Represents a single validation rule violation.

    This is the domain model (not the database model). It represents
    validation issues before they are persisted.
    """
    type: ValidationIssueType
    severity: ValidationIssueSeverity
    message: str
    draft_order_id: Optional[UUID] = None
    draft_order_line_id: Optional[UUID] = None
    line_no: Optional[int] = None
    details: dict[str, Any] = field(default_factory=dict)
    status: ValidationIssueStatus = ValidationIssueStatus.OPEN
    id: Optional[UUID] = None
    org_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by_user_id: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by_user_id: Optional[UUID] = None


@dataclass
class ReadyCheckResult:
    """Result of ready-check computation (SSOT §6.3).

    Determines if a draft order can transition to READY status.
    Stored in draft_order.ready_check_json JSONB field.
    """
    is_ready: bool
    blocking_reasons: list[str] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSONB storage"""
        return {
            "is_ready": self.is_ready,
            "blocking_reasons": self.blocking_reasons,
            "checked_at": self.checked_at
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReadyCheckResult":
        """Create from dictionary loaded from JSONB"""
        return cls(
            is_ready=data.get("is_ready", False),
            blocking_reasons=data.get("blocking_reasons", []),
            checked_at=data.get("checked_at", datetime.utcnow().isoformat())
        )


@dataclass
class ValidationContext:
    """Context object passed to validation rules.

    Contains all data needed for validation rules to execute,
    including references to products, customer prices, org settings, etc.
    """
    org_id: UUID
    products_by_sku: dict[str, Any] = field(default_factory=dict)
    customer_prices: list[Any] = field(default_factory=list)
    org_settings: dict[str, Any] = field(default_factory=dict)
    canonical_uoms: set[str] = field(default_factory=lambda: {
        "ST", "M", "CM", "MM", "KG", "G", "L", "ML", "KAR", "PAL", "SET"
    })
