"""Idempotency service for message processing.

Security: Prevents duplicate message processing which could lead to:
- Duplicate social media posts
- Wasted API calls
- Inconsistent state
"""

import hashlib
import time
from typing import Any

import structlog

from ..domain.ports import IdempotencyPort, IdempotencyRecord
from datetime import datetime

logger = structlog.get_logger()

# Default TTL for idempotency keys (24 hours)
DEFAULT_TTL_SECONDS = 86400


class InMemoryIdempotencyService(IdempotencyPort):
    """
    In-memory implementation of IdempotencyPort.

    Security: Uses in-memory cache for development, should be replaced
    with DynamoDB or Redis for production to support distributed workers.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        """
        Initialize idempotency service.

        Args:
            ttl_seconds: Time-to-live for idempotency records
        """
        self._ttl_seconds = ttl_seconds
        self._cache: dict[str, IdempotencyRecord] = {}
        self._expires: dict[str, float] = {}

    def generate_key(self, message_id: str, channels: list[str]) -> str:
        """
        Generate an idempotency key for a message.

        Args:
            message_id: The message UUID
            channels: List of target channels

        Returns:
            SHA256 hash of message_id + sorted channels
        """
        # Sort channels for consistent key generation
        channels_str = ",".join(sorted(channels))
        key_input = f"{message_id}:{channels_str}"
        return hashlib.sha256(key_input.encode()).hexdigest()

    def check_and_lock(self, key: str) -> IdempotencyRecord | None:
        """
        Check if a message has been processed and lock for processing.

        Args:
            key: The idempotency key

        Returns:
            Existing record if already processed/processing, None if new
        """
        self._cleanup_expired()

        existing = self._cache.get(key)

        if existing:
            if existing.status == "completed":
                logger.info(
                    "Message already processed (idempotent)",
                    idempotency_key=key[:16],
                )
                return existing

            if existing.status == "processing":
                # Check if processing has timed out (5 minutes)
                if (datetime.now() - existing.created_at).total_seconds() > 300:
                    logger.warning(
                        "Processing timeout, allowing retry",
                        idempotency_key=key[:16],
                    )
                    # Allow retry by falling through
                else:
                    logger.info(
                        "Message currently being processed",
                        idempotency_key=key[:16],
                    )
                    return existing

        # Lock for processing
        now = datetime.now()
        record = IdempotencyRecord(
            key=key,
            status="processing",
            created_at=now,
            completed_at=None,
            result=None,
            error=None,
        )
        self._cache[key] = record
        self._expires[key] = time.time() + self._ttl_seconds

        logger.debug(
            "Locked message for processing",
            idempotency_key=key[:16],
        )
        return None

    def mark_completed(
        self,
        key: str,
        result: dict[str, Any],
    ) -> None:
        """
        Mark a message as successfully processed.

        Args:
            key: The idempotency key
            result: The processing result to cache
        """
        if key in self._cache:
            record = self._cache[key]
            self._cache[key] = IdempotencyRecord(
                key=record.key,
                status="completed",
                created_at=record.created_at,
                completed_at=datetime.now(),
                result=result,
                error=None,
            )
            logger.debug(
                "Marked message as completed",
                idempotency_key=key[:16],
            )

    def mark_failed(self, key: str, error: str) -> None:
        """
        Mark a message as failed (allows retry).

        Args:
            key: The idempotency key
            error: The error message
        """
        if key in self._cache:
            record = self._cache[key]
            self._cache[key] = IdempotencyRecord(
                key=record.key,
                status="failed",
                created_at=record.created_at,
                completed_at=datetime.now(),
                result=None,
                error=error,
            )
            logger.debug(
                "Marked message as failed",
                idempotency_key=key[:16],
                error=error,
            )

    def release_lock(self, key: str) -> None:
        """
        Release a processing lock without marking complete.

        Args:
            key: The idempotency key
        """
        if key in self._cache:
            del self._cache[key]
            if key in self._expires:
                del self._expires[key]
            logger.debug(
                "Released processing lock",
                idempotency_key=key[:16],
            )

    def _cleanup_expired(self) -> None:
        """Remove expired records from cache."""
        now = time.time()
        expired = [k for k, v in self._expires.items() if v < now]
        for key in expired:
            del self._cache[key]
            del self._expires[key]
        if expired:
            logger.debug("Cleaned up expired idempotency records", count=len(expired))


# Global instance
_idempotency_service: InMemoryIdempotencyService | None = None


def get_idempotency_service() -> IdempotencyPort:
    """Get or create the global idempotency service."""
    global _idempotency_service
    if _idempotency_service is None:
        _idempotency_service = InMemoryIdempotencyService()
    return _idempotency_service
