"""
Outbound port for idempotency checking.

This port defines the interface for idempotency operations.
Implementations live in the infrastructure layer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class IdempotencyRecord:
    """Record of a processed operation."""

    key: str
    status: str  # processing, completed, failed
    created_at: datetime
    completed_at: datetime | None = None
    result: dict | None = None
    error: str | None = None


class IdempotencyPort(ABC):
    """
    Outbound port for idempotency checking.

    This abstraction allows the application layer to check for
    duplicate operations without knowing about the storage mechanism.
    """

    @abstractmethod
    def generate_key(self, message_id: str, channels: list[str]) -> str:
        """
        Generate a unique idempotency key.

        Args:
            message_id: Message identifier
            channels: List of target channels

        Returns:
            Unique key for this operation
        """
        ...

    @abstractmethod
    def check_and_lock(self, key: str) -> IdempotencyRecord | None:
        """
        Check if operation exists and lock if not.

        Args:
            key: Idempotency key

        Returns:
            Existing record if found, None if new (and locked)
        """
        ...

    @abstractmethod
    def mark_completed(self, key: str, result: dict[str, Any]) -> None:
        """
        Mark operation as completed.

        Args:
            key: Idempotency key
            result: Operation result
        """
        ...

    @abstractmethod
    def mark_failed(self, key: str, error: str) -> None:
        """
        Mark operation as failed.

        Args:
            key: Idempotency key
            error: Error message
        """
        ...
