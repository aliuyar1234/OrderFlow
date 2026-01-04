"""Structured JSON logging configuration.

Provides centralized logging setup with request ID correlation and JSON formatting.

SSOT Reference: §3.2 (Observability), FR-003 (Structured JSON Logging)
"""

import logging
import json
import sys
from datetime import datetime
from typing import Optional

from .request_id import get_request_id


class RequestIDFilter(logging.Filter):
    """Add request_id to all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request_id attribute to log record.

        Args:
            record: Log record to enhance

        Returns:
            bool: Always True (don't filter out records)
        """
        record.request_id = get_request_id()
        return True


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string.

        Args:
            record: Log record to format

        Returns:
            str: JSON-formatted log message
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "request_id": getattr(record, "request_id", "no-request-id"),
            "module": record.module,
            "function": record.funcName,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["error"] = str(record.exc_info[1])
            log_data["traceback"] = self.formatException(record.exc_info)

        # Add any extra fields
        if hasattr(record, "org_id"):
            log_data["org_id"] = str(record.org_id)
        if hasattr(record, "user_id"):
            log_data["user_id"] = str(record.user_id)
        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id

        return json.dumps(log_data)


def configure_logging(level: str = "INFO", json_format: bool = True) -> None:
    """Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: If True, use JSON formatter; otherwise use simple format
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    # Set formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(request_id)s - %(module)s.%(funcName)s - %(message)s'
        )

    handler.setFormatter(formatter)

    # Add request ID filter
    handler.addFilter(RequestIDFilter())

    # Add handler to root logger
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with request ID filtering.

    Args:
        name: Logger name (typically __name__)

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    return logger
