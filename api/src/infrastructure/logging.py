"""
Enterprise logging configuration.

Centralized logging setup with:
- Structured JSON output
- Correlation ID tracking
- Performance timing helpers
- Security-aware logging (no PII)
"""

import logging
import sys
import time
from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any
from uuid import uuid4

import structlog

# Context variable for request correlation
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def configure_logging(service_name: str) -> None:
    """
    Configure structured logging for a service.

    Args:
        service_name: Name of the service for log context
    """
    # Configure Python's standard logging to output to stdout
    # structlog.stdlib.LoggerFactory wraps stdlib logging, so we need handlers
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


def get_correlation_id() -> str:
    """Get current correlation ID or generate new one."""
    cid = correlation_id.get()
    if not cid:
        cid = str(uuid4())
        correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current context."""
    correlation_id.set(cid)


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

    @property
    def duration_s(self) -> float:
        """Duration in seconds, rounded to 3 decimal places."""
        return round(self._end - self._start, 3)


def timed(logger: Any = None):
    """
    Decorator to log function execution time.

    Usage:
        @timed(logger)
        async def my_function():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            log = logger or structlog.get_logger()
            with Timer() as t:
                result = await func(*args, **kwargs)
            log.debug(
                "Function executed",
                function=func.__name__,
                duration_ms=t.duration_ms,
            )
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            log = logger or structlog.get_logger()
            with Timer() as t:
                result = func(*args, **kwargs)
            log.debug(
                "Function executed",
                function=func.__name__,
                duration_ms=t.duration_ms,
            )
            return result

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def sanitize_for_logging(value: str, visible_chars: int = 8) -> str:
    """
    Sanitize sensitive values for logging.

    Args:
        value: The sensitive value
        visible_chars: Number of characters to show

    Returns:
        Truncated value with ellipsis
    """
    if not value:
        return ""
    if len(value) <= visible_chars:
        return value
    return value[:visible_chars] + "..."
