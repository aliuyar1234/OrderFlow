"""Unit tests for DocumentStatus state machine

SSOT Reference: §5.2.3 (DocumentStatus state transitions)
Spec: 007-document-upload
"""

import pytest
from backend.src.domain.documents import (
    DocumentStatus,
    can_transition,
    ALLOWED_TRANSITIONS,
)


class TestDocumentStatusStateMachine:
    """Test DocumentStatus enum and state transition validation"""

    def test_document_status_enum_values(self):
        """Test DocumentStatus enum has all required values"""
        assert DocumentStatus.UPLOADED.value == "UPLOADED"
        assert DocumentStatus.STORED.value == "STORED"
        assert DocumentStatus.PROCESSING.value == "PROCESSING"
        assert DocumentStatus.EXTRACTED.value == "EXTRACTED"
        assert DocumentStatus.FAILED.value == "FAILED"

    def test_initial_state_transition(self):
        """Test new documents can transition to UPLOADED"""
        assert can_transition(None, DocumentStatus.UPLOADED) is True
        assert can_transition(None, DocumentStatus.STORED) is False
        assert can_transition(None, DocumentStatus.PROCESSING) is False
        assert can_transition(None, DocumentStatus.EXTRACTED) is False
        assert can_transition(None, DocumentStatus.FAILED) is False

    def test_uploaded_to_stored(self):
        """Test UPLOADED → STORED transition (happy path)"""
        assert can_transition(DocumentStatus.UPLOADED, DocumentStatus.STORED) is True

    def test_uploaded_to_failed(self):
        """Test UPLOADED → FAILED transition (storage failure)"""
        assert can_transition(DocumentStatus.UPLOADED, DocumentStatus.FAILED) is True

    def test_uploaded_invalid_transitions(self):
        """Test invalid transitions from UPLOADED"""
        assert can_transition(DocumentStatus.UPLOADED, DocumentStatus.UPLOADED) is False
        assert can_transition(DocumentStatus.UPLOADED, DocumentStatus.PROCESSING) is False
        assert can_transition(DocumentStatus.UPLOADED, DocumentStatus.EXTRACTED) is False

    def test_stored_to_processing(self):
        """Test STORED → PROCESSING transition (extraction starts)"""
        assert can_transition(DocumentStatus.STORED, DocumentStatus.PROCESSING) is True

    def test_stored_to_failed(self):
        """Test STORED → FAILED transition (extraction fails to start)"""
        assert can_transition(DocumentStatus.STORED, DocumentStatus.FAILED) is True

    def test_stored_invalid_transitions(self):
        """Test invalid transitions from STORED"""
        assert can_transition(DocumentStatus.STORED, DocumentStatus.UPLOADED) is False
        assert can_transition(DocumentStatus.STORED, DocumentStatus.STORED) is False
        assert can_transition(DocumentStatus.STORED, DocumentStatus.EXTRACTED) is False

    def test_processing_to_extracted(self):
        """Test PROCESSING → EXTRACTED transition (extraction succeeds)"""
        assert can_transition(DocumentStatus.PROCESSING, DocumentStatus.EXTRACTED) is True

    def test_processing_to_failed(self):
        """Test PROCESSING → FAILED transition (extraction fails)"""
        assert can_transition(DocumentStatus.PROCESSING, DocumentStatus.FAILED) is True

    def test_processing_invalid_transitions(self):
        """Test invalid transitions from PROCESSING"""
        assert can_transition(DocumentStatus.PROCESSING, DocumentStatus.UPLOADED) is False
        assert can_transition(DocumentStatus.PROCESSING, DocumentStatus.STORED) is False
        assert can_transition(DocumentStatus.PROCESSING, DocumentStatus.PROCESSING) is False

    def test_extracted_is_terminal(self):
        """Test EXTRACTED is a terminal state (no transitions allowed)"""
        assert can_transition(DocumentStatus.EXTRACTED, DocumentStatus.UPLOADED) is False
        assert can_transition(DocumentStatus.EXTRACTED, DocumentStatus.STORED) is False
        assert can_transition(DocumentStatus.EXTRACTED, DocumentStatus.PROCESSING) is False
        assert can_transition(DocumentStatus.EXTRACTED, DocumentStatus.EXTRACTED) is False
        assert can_transition(DocumentStatus.EXTRACTED, DocumentStatus.FAILED) is False

    def test_failed_to_processing_retry(self):
        """Test FAILED → PROCESSING transition (retry allowed)"""
        assert can_transition(DocumentStatus.FAILED, DocumentStatus.PROCESSING) is True

    def test_failed_invalid_transitions(self):
        """Test invalid transitions from FAILED (only retry to PROCESSING allowed)"""
        assert can_transition(DocumentStatus.FAILED, DocumentStatus.UPLOADED) is False
        assert can_transition(DocumentStatus.FAILED, DocumentStatus.STORED) is False
        assert can_transition(DocumentStatus.FAILED, DocumentStatus.EXTRACTED) is False
        assert can_transition(DocumentStatus.FAILED, DocumentStatus.FAILED) is False

    def test_happy_path_full_flow(self):
        """Test complete happy path: None → UPLOADED → STORED → PROCESSING → EXTRACTED"""
        # None → UPLOADED (file received)
        assert can_transition(None, DocumentStatus.UPLOADED) is True

        # UPLOADED → STORED (file persisted to storage)
        assert can_transition(DocumentStatus.UPLOADED, DocumentStatus.STORED) is True

        # STORED → PROCESSING (extraction starts)
        assert can_transition(DocumentStatus.STORED, DocumentStatus.PROCESSING) is True

        # PROCESSING → EXTRACTED (extraction succeeds)
        assert can_transition(DocumentStatus.PROCESSING, DocumentStatus.EXTRACTED) is True

    def test_retry_flow(self):
        """Test retry flow: STORED → PROCESSING → FAILED → PROCESSING → EXTRACTED"""
        # STORED → PROCESSING (first attempt)
        assert can_transition(DocumentStatus.STORED, DocumentStatus.PROCESSING) is True

        # PROCESSING → FAILED (extraction fails)
        assert can_transition(DocumentStatus.PROCESSING, DocumentStatus.FAILED) is True

        # FAILED → PROCESSING (retry)
        assert can_transition(DocumentStatus.FAILED, DocumentStatus.PROCESSING) is True

        # PROCESSING → EXTRACTED (retry succeeds)
        assert can_transition(DocumentStatus.PROCESSING, DocumentStatus.EXTRACTED) is True

    def test_allowed_transitions_completeness(self):
        """Test ALLOWED_TRANSITIONS dict contains all states"""
        expected_states = [
            None,
            DocumentStatus.UPLOADED,
            DocumentStatus.STORED,
            DocumentStatus.PROCESSING,
            DocumentStatus.EXTRACTED,
            DocumentStatus.FAILED,
        ]

        for state in expected_states:
            assert state in ALLOWED_TRANSITIONS, f"Missing state in ALLOWED_TRANSITIONS: {state}"
