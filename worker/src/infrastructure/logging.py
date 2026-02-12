"""
Enterprise logging configuration for Worker service.

Centralized logging setup with:
- Structured JSON output
- Correlation ID tracking
- Performance timing helpers
- Security-aware logging (no PII)
"""

import logging
import sys
import time
from contextvars import ContextVar

import structlog

# Context variable for message correlation
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def configure_logging(service_name: str) -> None:
    """
    Configure structured logging for a service.

    Args:
        service_name: Name of the service for log context
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _add_service_name(service_name),
            _add_correlation_id,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def _add_service_name(service_name: str):
    """Processor to add service name to all logs."""

    def processor(logger, method_name, event_dict):
        event_dict["service"] = service_name
        return event_dict

    return processor


def _add_correlation_id(logger, method_name, event_dict):
    """Processor to add correlation ID if present."""
    cid = correlation_id.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current context (e.g., from Kinesis record)."""
    correlation_id.set(cid)


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return correlation_id.get()


class Timer:
    """
    Context manager for timing operations.

    Usage:
        with Timer() as t:
            await expensive_operation()
        logger.info("Operation completed", duration_ms=t.duration_ms)
    """

    def __init__(self):
        self._start: float = 0
        self._end: float = 0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:
        self._end = time.perf_counter()

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds, rounded to 2 decimal places."""
        return round((self._end - self._start) * 1000, 2)


def sanitize_for_logging(value: str, visible_chars: int = 8) -> str:
    """Sanitize sensitive values for logging."""
    if not value:
        return ""
    if len(value) <= visible_chars:
        return value
    return value[:visible_chars] + "..."
