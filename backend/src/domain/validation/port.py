"""ValidatorPort interface (SSOT Hexagonal Architecture)"""

from abc import ABC, abstractmethod
from typing import Any

from .models import ValidationIssue, ReadyCheckResult, ValidationContext


class ValidatorPort(ABC):
    """Port interface for validation services.

    Defines the contract for validation engines. This allows different
    validation implementations while keeping domain logic isolated.
    """

    @abstractmethod
    def validate(self, draft_order: Any, context: ValidationContext) -> list[ValidationIssue]:
        """Validate a draft order and return list of issues.

        Args:
            draft_order: The draft order to validate (domain model or DB model)
            context: Validation context with products, prices, settings

        Returns:
            List of ValidationIssue objects (not yet persisted)
        """
        pass

    @abstractmethod
    def compute_ready_check(self, draft_order: Any, issues: list[ValidationIssue]) -> ReadyCheckResult:
        """Compute ready-check status from current issues.

        Args:
            draft_order: The draft order being checked
            issues: Current validation issues (OPEN status)

        Returns:
            ReadyCheckResult indicating if draft can be approved
        """
        pass
