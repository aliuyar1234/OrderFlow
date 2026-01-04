"""
AI Call Logger - Service for logging AI calls with deduplication.

Tracks all LLM/embedding API calls to ai_call_log table with cost, tokens, latency.
Implements deduplication via input_hash to prevent redundant calls.

SSOT Reference: §5.5.1 (ai_call_log), §7.5.7 (Deduplication), FR-007
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ...models.ai_call_log import AICallLog, AICallStatus
from ...domain.ai.models import AICallType


class AICallLogger:
    """
    Service for logging and deduplicating AI API calls.

    SSOT: §5.5.1, FR-003, FR-007
    """

    @staticmethod
    def compute_input_hash(
        call_type: str,
        input_text: str,
        org_id: UUID
    ) -> str:
        """
        Compute SHA256 hash of call inputs for deduplication.

        Args:
            call_type: AICallType enum value
            input_text: Input text/prompt
            org_id: Organization ID (part of hash for multi-tenant isolation)

        Returns:
            Hex SHA256 hash

        SSOT: FR-007 - Deduplication via input_hash
        """
        # Combine inputs for deterministic hash
        hash_input = f"{org_id}|{call_type}|{input_text}"
        return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

    @staticmethod
    def find_cached_result(
        db: Session,
        input_hash: str,
        org_id: UUID,
        max_age_days: int = 7
    ) -> Optional[AICallLog]:
        """
        Find cached AI call result by input_hash.

        Args:
            db: Database session
            input_hash: SHA256 hash of inputs
            org_id: Organization ID
            max_age_days: Maximum age of cached result (default: 7 days)

        Returns:
            AICallLog if found and not expired, None otherwise

        SSOT: FR-007 - Reuse result if <7 days old
        """
        cache_cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        cached_call = db.query(AICallLog).filter(
            AICallLog.input_hash == input_hash,
            AICallLog.org_id == org_id,
            AICallLog.status == AICallStatus.SUCCEEDED,
            AICallLog.created_at >= cache_cutoff
        ).order_by(AICallLog.created_at.desc()).first()

        return cached_call

    @staticmethod
    def log_call(
        db: Session,
        org_id: UUID,
        call_type: AICallType,
        provider: str,
        model: str,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        cost_usd: int,
        latency_ms: int,
        status: AICallStatus,
        input_hash: Optional[str] = None,
        document_id: Optional[UUID] = None,
        draft_order_id: Optional[UUID] = None,
        request_id: Optional[str] = None,
        error_json: Optional[dict] = None
    ) -> AICallLog:
        """
        Log an AI API call to ai_call_log table.

        Args:
            db: Database session
            org_id: Organization ID
            call_type: AICallType enum value
            provider: Provider name (e.g., 'openai')
            model: Model name (e.g., 'gpt-4o-mini')
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            cost_usd: Cost in micro-USD
            latency_ms: Latency in milliseconds
            status: SUCCEEDED or FAILED
            input_hash: Optional SHA256 hash for deduplication
            document_id: Optional document reference
            draft_order_id: Optional draft order reference
            request_id: Optional provider request ID
            error_json: Optional error details if FAILED

        Returns:
            Created AICallLog instance

        SSOT: FR-003 - Log every LLM call with complete metadata
        """
        total_tokens = None
        if prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        call_log = AICallLog(
            org_id=org_id,
            call_type=call_type.value,
            provider=provider,
            model=model,
            request_id=request_id,
            input_hash=input_hash,
            document_id=document_id,
            draft_order_id=draft_order_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=status,
            error_json=error_json
        )

        db.add(call_log)
        db.commit()
        db.refresh(call_log)

        return call_log

    @staticmethod
    def log_success(
        db: Session,
        org_id: UUID,
        call_type: AICallType,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: int,
        latency_ms: int,
        input_hash: Optional[str] = None,
        document_id: Optional[UUID] = None,
        draft_order_id: Optional[UUID] = None,
        request_id: Optional[str] = None
    ) -> AICallLog:
        """
        Log successful AI call.

        Convenience wrapper around log_call() for success cases.
        """
        return AICallLogger.log_call(
            db=db,
            org_id=org_id,
            call_type=call_type,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=AICallStatus.SUCCEEDED,
            input_hash=input_hash,
            document_id=document_id,
            draft_order_id=draft_order_id,
            request_id=request_id
        )

    @staticmethod
    def log_failure(
        db: Session,
        org_id: UUID,
        call_type: AICallType,
        provider: str,
        model: str,
        latency_ms: int,
        error_json: dict,
        input_hash: Optional[str] = None,
        document_id: Optional[UUID] = None,
        draft_order_id: Optional[UUID] = None
    ) -> AICallLog:
        """
        Log failed AI call.

        Convenience wrapper around log_call() for failure cases.
        """
        return AICallLogger.log_call(
            db=db,
            org_id=org_id,
            call_type=call_type,
            provider=provider,
            model=model,
            prompt_tokens=None,
            completion_tokens=None,
            cost_usd=0,  # No cost for failed calls
            latency_ms=latency_ms,
            status=AICallStatus.FAILED,
            input_hash=input_hash,
            document_id=document_id,
            draft_order_id=draft_order_id,
            error_json=error_json
        )
