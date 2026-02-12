"""
Enterprise logging configuration for Scheduler service.

Centralized logging setup with:
- Structured JSON output
- Job correlation tracking
- Performance timing helpers
"""

import logging
import sys
import time
from contextvars import ContextVar

import structlog

# Context variable for job correlation
job_id: ContextVar[str] = ContextVar("job_id", default="")


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
            _add_job_id,
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


def _add_job_id(logger, method_name, event_dict):
    """Processor to add job ID if present."""
    jid = job_id.get()
    if jid:
        event_dict["job_id"] = jid
    return event_dict


def set_job_id(jid: str) -> None:
    """Set job ID for current context."""
    job_id.set(jid)


class Timer:
    """Context manager for timing operations."""

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
        """Duration in milliseconds."""
        return round((self._end - self._start) * 1000, 2)
