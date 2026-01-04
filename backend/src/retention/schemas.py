"""Pydantic schemas for retention settings and statistics.

This module defines retention-related schemas:
- RetentionSettings: Nested within OrgSettings for retention periods
- RetentionStatistics: Statistics about retention cleanup operations
- RetentionReport: Summary of eligible records for cleanup

SSOT Reference: §11.5 (Data Retention)
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class RetentionSettings(BaseModel):
    """Retention period configuration for different data types.

    All retention periods are in days. Minimum 30 days, maximum 3650 days (10 years).
    Audit logs have a minimum retention of 365 days regardless of setting.

    Default retention periods per SSOT §11.5:
    - Documents: 365 days (1 year)
    - AI call logs: 90 days
    - Feedback events: 365 days
    - Audit logs: 365 days (minimum, non-configurable)
    - Draft orders: 730 days (2 years)
    - Inbound messages: 90 days
    """

    document_retention_days: int = Field(
        default=365,
        ge=30,
        le=3650,
        description="Document retention period in days (30-3650)"
    )

    ai_log_retention_days: int = Field(
        default=90,
        ge=30,
        le=3650,
        description="AI call log retention period in days (30-3650)"
    )

    feedback_event_retention_days: int = Field(
        default=365,
        ge=30,
        le=3650,
        description="Feedback event retention period in days (30-3650)"
    )

    draft_order_retention_days: int = Field(
        default=730,
        ge=30,
        le=3650,
        description="Draft order retention period in days (30-3650)"
    )

    inbound_message_retention_days: int = Field(
        default=90,
        ge=30,
        le=3650,
        description="Inbound message retention period in days (30-3650)"
    )

    soft_delete_grace_period_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Grace period before hard-deleting soft-deleted records (1-365)"
    )

    @field_validator('*')
    @classmethod
    def validate_positive(cls, v: int) -> int:
        """Ensure all retention periods are positive integers."""
        if v < 1:
            raise ValueError("Retention period must be at least 1 day")
        return v


class RetentionStatistics(BaseModel):
    """Statistics from a retention cleanup job execution.

    Tracks how many records were processed, deleted, and any errors encountered.
    Used for monitoring and alerting on retention job health.
    """

    job_started_at: datetime = Field(
        description="When the retention job started"
    )

    job_completed_at: datetime = Field(
        description="When the retention job completed"
    )

    duration_seconds: float = Field(
        ge=0.0,
        description="Job execution duration in seconds"
    )

    documents_soft_deleted: int = Field(
        default=0,
        ge=0,
        description="Number of documents soft-deleted"
    )

    documents_hard_deleted: int = Field(
        default=0,
        ge=0,
        description="Number of documents permanently deleted"
    )

    ai_logs_deleted: int = Field(
        default=0,
        ge=0,
        description="Number of AI call logs deleted"
    )

    feedback_events_deleted: int = Field(
        default=0,
        ge=0,
        description="Number of feedback events deleted"
    )

    draft_orders_soft_deleted: int = Field(
        default=0,
        ge=0,
        description="Number of draft orders soft-deleted"
    )

    draft_orders_hard_deleted: int = Field(
        default=0,
        ge=0,
        description="Number of draft orders permanently deleted"
    )

    inbound_messages_soft_deleted: int = Field(
        default=0,
        ge=0,
        description="Number of inbound messages soft-deleted"
    )

    inbound_messages_hard_deleted: int = Field(
        default=0,
        ge=0,
        description="Number of inbound messages permanently deleted"
    )

    storage_errors: int = Field(
        default=0,
        ge=0,
        description="Number of object storage deletion errors"
    )

    database_errors: int = Field(
        default=0,
        ge=0,
        description="Number of database deletion errors"
    )

    orgs_processed: int = Field(
        default=0,
        ge=0,
        description="Number of organizations processed"
    )

    @property
    def total_records_deleted(self) -> int:
        """Total number of records deleted across all types."""
        return (
            self.documents_soft_deleted +
            self.documents_hard_deleted +
            self.ai_logs_deleted +
            self.feedback_events_deleted +
            self.draft_orders_soft_deleted +
            self.draft_orders_hard_deleted +
            self.inbound_messages_soft_deleted +
            self.inbound_messages_hard_deleted
        )

    @property
    def has_errors(self) -> bool:
        """Whether any errors occurred during execution."""
        return self.storage_errors > 0 or self.database_errors > 0

    @property
    def is_anomaly(self) -> bool:
        """Whether deletion volume exceeds normal thresholds (alert condition)."""
        return self.total_records_deleted > 10000


class RetentionReport(BaseModel):
    """Report of records eligible for retention cleanup.

    Provides counts of records that would be deleted if retention job runs.
    Used for preview/estimation before actually running cleanup.
    """

    org_id: str = Field(
        description="Organization UUID"
    )

    org_name: str = Field(
        description="Organization name"
    )

    retention_settings: RetentionSettings = Field(
        description="Current retention settings"
    )

    documents_eligible_for_soft_delete: int = Field(
        default=0,
        ge=0,
        description="Documents older than retention period"
    )

    documents_eligible_for_hard_delete: int = Field(
        default=0,
        ge=0,
        description="Soft-deleted documents past grace period"
    )

    ai_logs_eligible_for_delete: int = Field(
        default=0,
        ge=0,
        description="AI logs older than retention period"
    )

    feedback_events_eligible_for_delete: int = Field(
        default=0,
        ge=0,
        description="Feedback events older than retention period"
    )

    draft_orders_eligible_for_soft_delete: int = Field(
        default=0,
        ge=0,
        description="Draft orders older than retention period"
    )

    draft_orders_eligible_for_hard_delete: int = Field(
        default=0,
        ge=0,
        description="Soft-deleted drafts past grace period"
    )

    inbound_messages_eligible_for_soft_delete: int = Field(
        default=0,
        ge=0,
        description="Inbound messages older than retention period"
    )

    inbound_messages_eligible_for_hard_delete: int = Field(
        default=0,
        ge=0,
        description="Soft-deleted messages past grace period"
    )

    estimated_storage_freed_bytes: Optional[int] = Field(
        default=None,
        description="Estimated storage space to be freed (if calculable)"
    )

    @property
    def total_eligible_for_deletion(self) -> int:
        """Total records eligible for deletion."""
        return (
            self.documents_eligible_for_soft_delete +
            self.documents_eligible_for_hard_delete +
            self.ai_logs_eligible_for_delete +
            self.feedback_events_eligible_for_delete +
            self.draft_orders_eligible_for_soft_delete +
            self.draft_orders_eligible_for_hard_delete +
            self.inbound_messages_eligible_for_soft_delete +
            self.inbound_messages_eligible_for_hard_delete
        )


class RetentionSettingsUpdate(BaseModel):
    """Schema for updating retention settings (partial updates allowed).

    All fields optional. Used for PATCH /admin/retention-settings.
    """

    document_retention_days: Optional[int] = Field(
        None,
        ge=30,
        le=3650,
        description="Document retention period in days"
    )

    ai_log_retention_days: Optional[int] = Field(
        None,
        ge=30,
        le=3650,
        description="AI log retention period in days"
    )

    feedback_event_retention_days: Optional[int] = Field(
        None,
        ge=30,
        le=3650,
        description="Feedback event retention period in days"
    )

    draft_order_retention_days: Optional[int] = Field(
        None,
        ge=30,
        le=3650,
        description="Draft order retention period in days"
    )

    inbound_message_retention_days: Optional[int] = Field(
        None,
        ge=30,
        le=3650,
        description="Inbound message retention period in days"
    )

    soft_delete_grace_period_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Grace period before hard-delete"
    )
