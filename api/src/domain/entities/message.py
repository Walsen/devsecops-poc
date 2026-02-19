from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from ..value_objects import ChannelType, MessageContent


class MessageStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    PARTIALLY_DELIVERED = "partially_delivered"
    FAILED = "failed"


@dataclass
class ChannelDelivery:
    """Tracks delivery status per channel."""

    channel: ChannelType
    status: MessageStatus = MessageStatus.SCHEDULED
    delivered_at: datetime | None = None
    error: str | None = None


@dataclass
class Message:
    """Message aggregate root."""

    id: UUID
    content: MessageContent
    channels: list[ChannelType]
    scheduled_at: datetime
    status: MessageStatus
    recipient_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    deliveries: list[ChannelDelivery] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        content: MessageContent,
        channels: list[ChannelType],
        scheduled_at: datetime,
        recipient_id: str,
        user_id: str,
    ) -> "Message":
        """Factory method to create a new message."""
        now = datetime.now(UTC)
        message = cls(
            id=uuid4(),
            content=content,
            channels=channels,
            scheduled_at=scheduled_at,
            status=MessageStatus.DRAFT,
            recipient_id=recipient_id,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        # Initialize delivery tracking for each channel
        message.deliveries = [ChannelDelivery(channel=ch) for ch in channels]
        return message

    def schedule(self) -> None:
        """Mark message as scheduled for delivery."""
        if self.status != MessageStatus.DRAFT:
            raise ValueError(f"Cannot schedule message in {self.status} status")
        self.status = MessageStatus.SCHEDULED
        self.updated_at = datetime.now(UTC)

    def mark_processing(self) -> None:
        """Mark message as being processed."""
        self.status = MessageStatus.PROCESSING
        self.updated_at = datetime.now(UTC)

    def mark_channel_delivered(self, channel: ChannelType) -> None:
        """Mark a specific channel as delivered."""
        for delivery in self.deliveries:
            if delivery.channel == channel:
                delivery.status = MessageStatus.DELIVERED
                delivery.delivered_at = datetime.now(UTC)
                break
        self._update_overall_status()

    def mark_channel_failed(self, channel: ChannelType, error: str) -> None:
        """Mark a specific channel as failed."""
        for delivery in self.deliveries:
            if delivery.channel == channel:
                delivery.status = MessageStatus.FAILED
                delivery.error = error
                break
        self._update_overall_status()

    def _update_overall_status(self) -> None:
        """Update overall message status based on channel deliveries."""
        statuses = [d.status for d in self.deliveries]

        if all(s == MessageStatus.DELIVERED for s in statuses):
            self.status = MessageStatus.DELIVERED
        elif all(s == MessageStatus.FAILED for s in statuses):
            self.status = MessageStatus.FAILED
        elif any(s == MessageStatus.DELIVERED for s in statuses):
            self.status = MessageStatus.PARTIALLY_DELIVERED

        self.updated_at = datetime.now(UTC)
