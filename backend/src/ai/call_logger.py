"""AI call logging service for tracking LLM/embedding usage."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


class AICallType(str, Enum):
    """AI call types per SSOT §5.2.10."""

    LLM_EXTRACT_PDF_TEXT = "LLM_EXTRACT_PDF_TEXT"
    LLM_EXTRACT_PDF_VISION = "LLM_EXTRACT_PDF_VISION"
    LLM_REPAIR_JSON = "LLM_REPAIR_JSON"
    EMBED_PRODUCT = "EMBED_PRODUCT"
    EMBED_QUERY = "EMBED_QUERY"
    LLM_CUSTOMER_HINT = "LLM_CUSTOMER_HINT"


class AICallLogger:
    """Service for logging AI provider calls.

    Per SSOT §7.5: All LLM calls must be logged with:
    - Deduplication via input_hash
    - Cost/latency tracking
    - Error logging
    """

    def __init__(self, db: Session):
        """Initialize call logger.

        Args:
            db: Database session
        """
        self.db = db

    def log_llm_call(
        self,
        org_id: str,
        call_type: AICallType,
        input_hash: str,
        provider: str,
        model: str,
        status: str,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        latency_ms: int | None = None,
        cost_micros: int | None = None,
        error_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> None:
        """Log LLM call to ai_call_log table.

        Args:
            org_id: Organization ID
            call_type: Type of AI call
            input_hash: SHA256 hash of input for deduplication
            provider: Provider name (e.g., 'openai')
            model: Model name (e.g., 'gpt-4o-mini')
            status: 'SUCCEEDED' or 'FAILED'
            tokens_in: Input tokens
            tokens_out: Output tokens
            latency_ms: Latency in milliseconds
            cost_micros: Cost in micros (1/1,000,000 currency unit)
            error_json: Error details if failed
            metadata_json: Additional metadata
        """
        # Note: In a real implementation, this would insert into ai_call_log table
        # For now, just log to logger as a placeholder

        log_entry = {
            "org_id": org_id,
            "call_type": call_type.value,
            "input_hash": input_hash,
            "provider": provider,
            "model": model,
            "status": status,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
            "cost_micros": cost_micros,
            "error_json": error_json,
            "metadata_json": metadata_json,
            "called_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"AI call logged: {json.dumps(log_entry)}")

        # TODO: Insert into database when ai_call_log table exists
        # from ..models.ai_call_log import AICallLog
        # call_log = AICallLog(
        #     org_id=org_id,
        #     call_type=call_type.value,
        #     input_hash=input_hash,
        #     provider=provider,
        #     model=model,
        #     status=status,
        #     tokens_in=tokens_in,
        #     tokens_out=tokens_out,
        #     latency_ms=latency_ms,
        #     cost_micros=cost_micros,
        #     error_json=error_json,
        #     metadata_json=metadata_json,
        # )
        # self.db.add(call_log)
        # self.db.commit()

    def calculate_input_hash(self, *args: Any) -> str:
        """Calculate deterministic hash for call deduplication.

        Args:
            *args: Input arguments to hash

        Returns:
            SHA256 hex string
        """
        hash_input = json.dumps([str(arg) for arg in args], sort_keys=True)
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def check_daily_budget(
        self,
        org_id: str,
        daily_budget_micros: int,
    ) -> tuple[bool, int]:
        """Check if organization has budget remaining for today.

        Args:
            org_id: Organization ID
            daily_budget_micros: Daily budget limit in micros

        Returns:
            Tuple of (has_budget, used_micros)
        """
        # TODO: Query ai_call_log for today's spend
        # For now, return placeholder
        used_micros = 0  # Query sum of cost_micros for today

        has_budget = used_micros < daily_budget_micros if daily_budget_micros > 0 else True

        return has_budget, used_micros
