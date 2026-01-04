"""
Base Connector - Common functionality for all ERP connectors

Provides shared utilities for validation, logging, and error handling
that all connector implementations can use.
"""

import logging
from typing import Any, Dict, Optional
from abc import ABC
from datetime import datetime
import time

from .ports import ERPConnectorPort, ConnectorError, TestResult


logger = logging.getLogger(__name__)


class BaseConnector(ERPConnectorPort, ABC):
    """
    Base class for ERP connector implementations.

    Provides common functionality:
    - Config validation helpers
    - Timing/latency measurement
    - Standard error handling
    - Logging utilities

    Subclasses must implement:
    - export(draft_order, config) -> ExportResult
    - test_connection(config) -> TestResult
    - _validate_config(config) - connector-specific validation
    """

    def validate_required_fields(self, config: Dict[str, Any], required_fields: list[str]) -> None:
        """
        Validate that all required fields are present in config.

        Args:
            config: Configuration dictionary to validate
            required_fields: List of required field names

        Raises:
            ConnectorError: If any required field is missing or empty
        """
        missing_fields = []
        for field in required_fields:
            if field not in config:
                missing_fields.append(field)
            elif isinstance(config[field], str) and not config[field].strip():
                missing_fields.append(f"{field} (empty)")

        if missing_fields:
            raise ConnectorError(
                f"Missing or empty required configuration fields: {', '.join(missing_fields)}"
            )

    def validate_config_enum(
        self,
        config: Dict[str, Any],
        field: str,
        valid_values: list[str],
        required: bool = True
    ) -> None:
        """
        Validate that a config field has one of the allowed values.

        Args:
            config: Configuration dictionary
            field: Field name to validate
            valid_values: List of allowed values
            required: Whether the field is required (default: True)

        Raises:
            ConnectorError: If field is required but missing, or has invalid value
        """
        if field not in config:
            if required:
                raise ConnectorError(f"Required field '{field}' is missing")
            return

        value = config[field]
        if value not in valid_values:
            raise ConnectorError(
                f"Invalid value for '{field}': {value}. "
                f"Must be one of: {', '.join(valid_values)}"
            )

    def measure_latency(self, operation_name: str):
        """
        Context manager for measuring operation latency.

        Usage:
            with self.measure_latency("sftp_connection"):
                # perform operation
                pass

        Returns a context manager that yields the start time and logs the duration.
        """
        class LatencyMeasurer:
            def __init__(self, name: str):
                self.name = name
                self.start_time = None
                self.latency_ms = 0

            def __enter__(self):
                self.start_time = time.time()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.latency_ms = int((time.time() - self.start_time) * 1000)
                if exc_type is None:
                    logger.info(f"{self.name} completed in {self.latency_ms}ms")
                else:
                    logger.warning(
                        f"{self.name} failed after {self.latency_ms}ms: {exc_val}"
                    )
                return False  # Don't suppress exceptions

        return LatencyMeasurer(operation_name)

    def build_test_result(
        self,
        success: bool,
        error_message: Optional[str] = None,
        latency_ms: int = 0
    ) -> TestResult:
        """
        Build a TestResult with consistent structure.

        Args:
            success: Whether the test succeeded
            error_message: Error message if test failed
            latency_ms: Time taken for the test in milliseconds

        Returns:
            TestResult instance
        """
        return TestResult(
            success=success,
            error_message=error_message,
            latency_ms=latency_ms,
            test_timestamp=datetime.utcnow()
        )

    def log_export_attempt(
        self,
        draft_order_id: Any,
        connector_type: str,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """
        Log an export attempt for observability.

        Args:
            draft_order_id: ID of the draft order being exported
            connector_type: Type of connector used
            success: Whether export succeeded
            error: Error message if failed
        """
        if success:
            logger.info(
                f"Export succeeded",
                extra={
                    "draft_order_id": str(draft_order_id),
                    "connector_type": connector_type,
                    "status": "success"
                }
            )
        else:
            logger.error(
                f"Export failed: {error}",
                extra={
                    "draft_order_id": str(draft_order_id),
                    "connector_type": connector_type,
                    "status": "failed",
                    "error": error
                }
            )

    def log_test_attempt(
        self,
        connector_type: str,
        success: bool,
        latency_ms: int,
        error: Optional[str] = None
    ) -> None:
        """
        Log a connection test attempt for observability.

        Args:
            connector_type: Type of connector tested
            success: Whether test succeeded
            latency_ms: Test duration in milliseconds
            error: Error message if failed
        """
        if success:
            logger.info(
                f"Connection test succeeded",
                extra={
                    "connector_type": connector_type,
                    "latency_ms": latency_ms,
                    "status": "success"
                }
            )
        else:
            logger.warning(
                f"Connection test failed: {error}",
                extra={
                    "connector_type": connector_type,
                    "latency_ms": latency_ms,
                    "status": "failed",
                    "error": error
                }
            )
