"""
Mock Connector - In-memory connector for testing

Provides a simple connector implementation that simulates ERP operations
without requiring external systems. Used for unit tests and development.
"""

import logging
from typing import Any, Dict
from uuid import uuid4

from ..ports import ExportResult, TestResult, ConnectorError
from ..base_connector import BaseConnector


logger = logging.getLogger(__name__)


class MockConnector(BaseConnector):
    """
    Mock ERP connector for testing and development.

    Simulates ERP operations in memory without requiring actual ERP systems.
    Supports configuration options to simulate success, failure, and delays.

    Configuration:
        - mode: "success" | "failure" | "timeout" (default: "success")
        - simulate_delay_ms: Delay in milliseconds to simulate network latency (default: 0)
        - error_message: Custom error message when mode="failure"

    Usage:
        # Success case
        config = {"mode": "success"}
        result = connector.export(draft_order, config)
        assert result.success is True

        # Failure case
        config = {"mode": "failure", "error_message": "Connection refused"}
        result = connector.export(draft_order, config)
        # Raises ConnectorError
    """

    def export(self, draft_order: Any, config: Dict[str, Any]) -> ExportResult:
        """
        Simulate exporting a draft order.

        Args:
            draft_order: DraftOrder to export
            config: Configuration with mode, simulate_delay_ms, error_message

        Returns:
            ExportResult with simulated success or failure

        Raises:
            ConnectorError: If mode="failure"
        """
        mode = config.get("mode", "success")
        simulate_delay_ms = config.get("simulate_delay_ms", 0)
        error_message = config.get("error_message", "Mock connector simulated failure")

        # Simulate delay if configured
        if simulate_delay_ms > 0:
            import time
            time.sleep(simulate_delay_ms / 1000.0)

        # Simulate different modes
        if mode == "failure":
            logger.info(f"MockConnector: Simulating export failure")
            raise ConnectorError(error_message)

        if mode == "timeout":
            logger.info(f"MockConnector: Simulating timeout")
            raise ConnectorError("Connection timeout")

        # Success case
        export_id = uuid4()
        storage_key = f"mock/exports/{export_id}.json"

        logger.info(
            f"MockConnector: Successfully exported draft_order {draft_order.id}",
            extra={
                "draft_order_id": str(draft_order.id),
                "export_id": str(export_id),
                "mode": mode
            }
        )

        return ExportResult(
            success=True,
            export_id=export_id,
            storage_key=storage_key,
            connector_metadata={
                "mock": True,
                "mode": mode,
                "simulated_delay_ms": simulate_delay_ms
            }
        )

    def test_connection(self, config: Dict[str, Any]) -> TestResult:
        """
        Simulate testing the connection.

        Args:
            config: Configuration with mode, simulate_delay_ms, error_message

        Returns:
            TestResult with simulated success or failure
        """
        mode = config.get("mode", "success")
        simulate_delay_ms = config.get("simulate_delay_ms", 0)
        error_message = config.get("error_message", "Mock connector simulated test failure")

        # Simulate delay if configured
        if simulate_delay_ms > 0:
            import time
            time.sleep(simulate_delay_ms / 1000.0)

        # Simulate different modes
        if mode == "failure":
            logger.info(f"MockConnector: Simulating test failure")
            return self.build_test_result(
                success=False,
                error_message=error_message,
                latency_ms=simulate_delay_ms
            )

        if mode == "timeout":
            logger.info(f"MockConnector: Simulating timeout")
            return self.build_test_result(
                success=False,
                error_message="Connection timeout",
                latency_ms=simulate_delay_ms
            )

        # Success case
        logger.info(f"MockConnector: Test connection succeeded")
        return self.build_test_result(
            success=True,
            latency_ms=simulate_delay_ms
        )

    def get_connector_type(self) -> str:
        """Return the connector type identifier."""
        return "MOCK"


# Auto-register the mock connector
from ..registry import ConnectorRegistry
try:
    ConnectorRegistry.register("MOCK", MockConnector)
    logger.debug("MockConnector registered successfully")
except RuntimeError:
    # Already registered (e.g., in tests)
    pass
