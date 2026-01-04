"""
Budget Gate - Enforce daily LLM budget limits per organization.

Prevents cost overruns by blocking LLM calls when daily budget is exceeded.

SSOT Reference: §7.2.3 (Cost/Latency Gates), FR-005 (Daily Budget Enforcement)
"""

from datetime import datetime, timezone
from typing import Tuple, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.ai_call_log import AICallLog


class BudgetGateError(Exception):
    """Raised when budget gate blocks an LLM call"""
    pass


class BudgetGate:
    """
    Budget gate service for enforcing daily LLM spending limits.

    SSOT: §7.2.3, FR-005
    - Check daily budget before each LLM call
    - Block if daily_budget_micros exceeded
    - Budget = 0 means unlimited
    """

    @staticmethod
    def check_budget_gate(
        db: Session,
        org_id: UUID,
        settings_json: dict
    ) -> Tuple[bool, int, int]:
        """
        Check if organization has remaining budget for LLM calls today.

        Args:
            db: Database session
            org_id: Organization ID
            settings_json: Org settings JSON (contains ai.llm.daily_budget_micros)

        Returns:
            Tuple of (allowed: bool, current_usage_micros: int, budget_micros: int)

        SSOT: Query sum(cost_usd) WHERE org_id=X AND created_at >= today_utc
        """
        # Get budget from org settings
        budget_micros = BudgetGate._get_daily_budget(settings_json)

        # If budget is 0 or not set, unlimited
        if budget_micros == 0:
            return True, 0, 0

        # Calculate today's start (UTC midnight)
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Query current usage
        usage_micros = db.query(func.sum(AICallLog.cost_usd)).filter(
            AICallLog.org_id == org_id,
            AICallLog.created_at >= today_start
        ).scalar() or 0

        # Check if under budget
        allowed = usage_micros < budget_micros

        return allowed, usage_micros, budget_micros

    @staticmethod
    def enforce_budget_gate(
        db: Session,
        org_id: UUID,
        settings_json: dict
    ) -> None:
        """
        Enforce budget gate - raise exception if budget exceeded.

        Args:
            db: Database session
            org_id: Organization ID
            settings_json: Org settings JSON

        Raises:
            BudgetGateError: If daily budget exceeded

        SSOT: FR-005 - Block call if total >= daily_budget_micros
        """
        allowed, usage_micros, budget_micros = BudgetGate.check_budget_gate(
            db, org_id, settings_json
        )

        if not allowed:
            usage_usd = usage_micros / 1_000_000
            budget_usd = budget_micros / 1_000_000
            raise BudgetGateError(
                f"Daily LLM budget exceeded: ${usage_usd:.4f} / ${budget_usd:.4f} used today"
            )

    @staticmethod
    def _get_daily_budget(settings_json: dict) -> int:
        """
        Extract daily budget from org settings.

        Args:
            settings_json: Org settings JSON

        Returns:
            Budget in micro-USD (0 = unlimited)

        SSOT: §10.1 - ai.llm.daily_budget_micros (default 0)
        """
        try:
            ai_settings = settings_json.get("ai", {})
            llm_settings = ai_settings.get("llm", {})
            budget = llm_settings.get("daily_budget_micros", 0)
            return int(budget) if budget else 0
        except (KeyError, TypeError, ValueError):
            return 0  # Default to unlimited on parse error
