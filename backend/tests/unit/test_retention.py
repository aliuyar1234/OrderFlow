"""Unit tests for retention module.

Tests retention settings validation, cutoff date calculation, and service logic.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from pydantic import ValidationError

from src.retention.schemas import (
    RetentionSettings,
    RetentionSettingsUpdate,
    RetentionStatistics,
    RetentionReport,
)


class TestRetentionSettings:
    """Test RetentionSettings schema validation."""

    def test_default_values(self):
        """Test that default retention periods match SSOT §11.5."""
        settings = RetentionSettings()

        assert settings.document_retention_days == 365
        assert settings.ai_log_retention_days == 90
        assert settings.feedback_event_retention_days == 365
        assert settings.draft_order_retention_days == 730
        assert settings.inbound_message_retention_days == 90
        assert settings.soft_delete_grace_period_days == 90

    def test_minimum_retention_validation(self):
        """Test that retention periods cannot be less than 30 days."""
        with pytest.raises(ValidationError) as exc:
            RetentionSettings(document_retention_days=29)

        assert "greater than or equal to 30" in str(exc.value)

    def test_maximum_retention_validation(self):
        """Test that retention periods cannot exceed 3650 days (10 years)."""
        with pytest.raises(ValidationError) as exc:
            RetentionSettings(document_retention_days=3651)

        assert "less than or equal to 3650" in str(exc.value)

    def test_grace_period_minimum(self):
        """Test that grace period cannot be less than 1 day."""
        with pytest.raises(ValidationError) as exc:
            RetentionSettings(soft_delete_grace_period_days=0)

        assert "greater than or equal to 1" in str(exc.value)

    def test_grace_period_maximum(self):
        """Test that grace period cannot exceed 365 days."""
        with pytest.raises(ValidationError) as exc:
            RetentionSettings(soft_delete_grace_period_days=366)

        assert "less than or equal to 365" in str(exc.value)

    def test_custom_valid_values(self):
        """Test that valid custom retention periods are accepted."""
        settings = RetentionSettings(
            document_retention_days=180,
            ai_log_retention_days=60,
            feedback_event_retention_days=730,
            draft_order_retention_days=1825,  # 5 years
            inbound_message_retention_days=30,
            soft_delete_grace_period_days=30,
        )

        assert settings.document_retention_days == 180
        assert settings.ai_log_retention_days == 60
        assert settings.soft_delete_grace_period_days == 30


class TestRetentionStatistics:
    """Test RetentionStatistics schema."""

    def test_total_records_deleted(self):
        """Test calculation of total records deleted."""
        now = datetime.utcnow()
        stats = RetentionStatistics(
            job_started_at=now,
            job_completed_at=now + timedelta(seconds=120),
            duration_seconds=120.0,
            documents_soft_deleted=100,
            documents_hard_deleted=50,
            ai_logs_deleted=1000,
            feedback_events_deleted=200,
            draft_orders_soft_deleted=30,
            draft_orders_hard_deleted=10,
            inbound_messages_soft_deleted=150,
            inbound_messages_hard_deleted=75,
        )

        assert stats.total_records_deleted == 1615

    def test_has_errors(self):
        """Test error detection."""
        now = datetime.utcnow()

        # No errors
        stats = RetentionStatistics(
            job_started_at=now,
            job_completed_at=now,
            duration_seconds=0,
            storage_errors=0,
            database_errors=0,
        )
        assert not stats.has_errors

        # Storage errors
        stats = RetentionStatistics(
            job_started_at=now,
            job_completed_at=now,
            duration_seconds=0,
            storage_errors=5,
            database_errors=0,
        )
        assert stats.has_errors

        # Database errors
        stats = RetentionStatistics(
            job_started_at=now,
            job_completed_at=now,
            duration_seconds=0,
            storage_errors=0,
            database_errors=3,
        )
        assert stats.has_errors

    def test_is_anomaly(self):
        """Test anomaly detection (>10k records deleted)."""
        now = datetime.utcnow()

        # Normal volume
        stats = RetentionStatistics(
            job_started_at=now,
            job_completed_at=now,
            duration_seconds=0,
            documents_soft_deleted=5000,
        )
        assert not stats.is_anomaly

        # Anomaly - exceeds threshold
        stats = RetentionStatistics(
            job_started_at=now,
            job_completed_at=now,
            duration_seconds=0,
            ai_logs_deleted=10001,
        )
        assert stats.is_anomaly


class TestRetentionReport:
    """Test RetentionReport schema."""

    def test_total_eligible_for_deletion(self):
        """Test calculation of total eligible records."""
        report = RetentionReport(
            org_id=str(uuid4()),
            org_name="Test Org",
            retention_settings=RetentionSettings(),
            documents_eligible_for_soft_delete=100,
            documents_eligible_for_hard_delete=50,
            ai_logs_eligible_for_delete=500,
            feedback_events_eligible_for_delete=200,
            draft_orders_eligible_for_soft_delete=30,
            draft_orders_eligible_for_hard_delete=10,
            inbound_messages_eligible_for_soft_delete=75,
            inbound_messages_eligible_for_hard_delete=25,
        )

        assert report.total_eligible_for_deletion == 990


class TestRetentionService:
    """Test RetentionService logic.

    Note: These are unit tests for service logic.
    Full integration tests require database and models.
    """

    def test_calculate_cutoff_dates(self):
        """Test cutoff date calculation based on retention settings."""
        from src.retention.service import RetentionService
        from src.models.org import Org

        # This test will be completed when database fixtures are available
        # For now, test the logic conceptually

        settings = RetentionSettings(
            document_retention_days=365,
            ai_log_retention_days=90,
            soft_delete_grace_period_days=90,
        )

        now = datetime.utcnow()
        expected_doc_cutoff = now - timedelta(days=365)
        expected_ai_cutoff = now - timedelta(days=90)
        expected_grace_cutoff = now - timedelta(days=90)

        # Cutoff dates should be approximately these values (within 1 second)
        # Actual implementation will be tested in integration tests
        pass


class TestRetentionSettingsUpdate:
    """Test partial updates to retention settings."""

    def test_partial_update(self):
        """Test that partial updates only include provided fields."""
        update = RetentionSettingsUpdate(
            document_retention_days=180,
        )

        data = update.dict(exclude_unset=True)

        assert 'document_retention_days' in data
        assert data['document_retention_days'] == 180

        # Other fields should not be in dict
        assert 'ai_log_retention_days' not in data
        assert 'grace_period_days' not in data

    def test_validation_on_update(self):
        """Test that validation still applies to partial updates."""
        with pytest.raises(ValidationError) as exc:
            RetentionSettingsUpdate(document_retention_days=29)

        assert "greater than or equal to 30" in str(exc.value)
