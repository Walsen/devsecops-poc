"""
Outbound port for message persistence.

This port defines the interface for message storage operations.
Implementations live in the infrastructure layer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class MessageData:
    """Domain representation of a message."""

    id: UUID
    content: str
    media_url: str | None = None
    recipient_id: str | None = None
    metadata: dict | None = None
    status: str = "pending"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MessageRepository(ABC):
    """
    Outbound port for message persistence.

    This abstraction allows the application layer to work with messages
    without knowing about the underlying storage mechanism.
    """

    @abstractmethod
    async def get_by_id(self, message_id: UUID) -> MessageData | None:
        """
        Retrieve a message by its ID.

        Args:
            message_id: UUID of the message

        Returns:
            MessageData if found, None otherwise
        """
        ...

    @abstractmethod
    async def update_status(self, message_id: UUID, status: str) -> None:
        """
        Update the status of a message.

        Args:
            message_id: UUID of the message
            status: New status (pending, processing, delivered, partial, failed)
        """
        ...

    @abstractmethod
    async def mark_channel_delivered(
        self,
        message_id: UUID,
        channel: str,
        external_id: str | None = None,
    ) -> None:
        """
        Mark a channel delivery as successful.

        Args:
            message_id: UUID of the message
            channel: Channel name (facebook, instagram, etc.)
            external_id: External ID from the channel (post ID, etc.)
        """
        ...

    @abstractmethod
    async def mark_channel_failed(
        self,
        message_id: UUID,
        channel: str,
        error: str,
    ) -> None:
        """
        Mark a channel delivery as failed.

        Args:
            message_id: UUID of the message
            channel: Channel name
            error: Error message
        """
        ...
