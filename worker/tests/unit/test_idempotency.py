"""Tests for idempotency service."""

import time

import pytest

from src.infrastructure.idempotency import InMemoryIdempotencyService


class TestIdempotencyService:
    """Tests for the idempotency service."""

    def setup_method(self) -> None:
        self.service = InMemoryIdempotencyService(ttl_seconds=60)

    def test_generate_key_consistent(self) -> None:
        """Same inputs should generate same key."""
        key1 = self.service.generate_key("msg-123", ["facebook", "linkedin"])
        key2 = self.service.generate_key("msg-123", ["facebook", "linkedin"])
        assert key1 == key2

    def test_generate_key_channel_order_independent(self) -> None:
        """Channel order should not affect key."""
        key1 = self.service.generate_key("msg-123", ["facebook", "linkedin"])
        key2 = self.service.generate_key("msg-123", ["linkedin", "facebook"])
        assert key1 == key2

    def test_generate_key_different_messages(self) -> None:
        """Different messages should have different keys."""
        key1 = self.service.generate_key("msg-123", ["facebook"])
        key2 = self.service.generate_key("msg-456", ["facebook"])
        assert key1 != key2

    def test_check_and_lock_new_message(self) -> None:
        """New message should return None and be locked."""
        key = self.service.generate_key("msg-new", ["facebook"])
        result = self.service.check_and_lock(key)
        assert result is None

    def test_check_and_lock_processing_message(self) -> None:
        """Message being processed should return existing record."""
        key = self.service.generate_key("msg-processing", ["facebook"])

        # First call locks it
        self.service.check_and_lock(key)

        # Second call returns existing
        result = self.service.check_and_lock(key)
        assert result is not None
        assert result.status == "processing"

    def test_mark_completed(self) -> None:
        """Completed message should be cached."""
        key = self.service.generate_key("msg-complete", ["facebook"])

        self.service.check_and_lock(key)
        self.service.mark_completed(key, {"success": True})

        result = self.service.check_and_lock(key)
        assert result is not None
        assert result.status == "completed"
        assert result.result == {"success": True}

    def test_mark_failed_allows_retry(self) -> None:
        """Failed message should allow retry (returns None to allow re-lock)."""
        key = self.service.generate_key("msg-failed", ["facebook"])

        self.service.check_and_lock(key)
        self.service.mark_failed(key, "Connection error")

        # Failed messages can be retried - check_and_lock returns None to allow new lock
        # The implementation allows retry by not blocking on failed status
        result = self.service.check_and_lock(key)
        # Result is None because failed messages are re-lockable
        assert result is None

    def test_release_lock(self) -> None:
        """Released lock should allow new processing."""
        key = self.service.generate_key("msg-release", ["facebook"])

        self.service.check_and_lock(key)
        self.service.release_lock(key)

        # Should be able to lock again
        result = self.service.check_and_lock(key)
        assert result is None

    def test_expired_records_cleaned(self) -> None:
        """Expired records should be cleaned up."""
        # Use very short TTL
        service = InMemoryIdempotencyService(ttl_seconds=0)
        key = self.service.generate_key("msg-expire", ["facebook"])

        service.check_and_lock(key)
        service.mark_completed(key, {"success": True})

        # Wait for expiry
        time.sleep(0.1)

        # Should be cleaned up on next check
        result = service.check_and_lock(key)
        assert result is None  # Expired, so treated as new
