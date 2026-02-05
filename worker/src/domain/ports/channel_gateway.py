"""
Outbound port for channel delivery.

This is the interface that the domain/application layer uses to send messages.
Infrastructure adapters implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class ChannelType(str, Enum):
    """Supported delivery channels."""

    WHATSAPP = "whatsapp"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    EMAIL = "email"
    SMS = "sms"


@dataclass
class DeliveryResult:
    """Result of a channel delivery attempt."""

    success: bool
    channel: ChannelType | None = None
    external_id: str | None = None
    error: str | None = None


class ChannelGateway(ABC):
    """
    Outbound port for sending messages through a channel.

    This is the interface that infrastructure adapters must implement.
    The application layer depends on this abstraction, not concrete implementations.
    """

    @property
    @abstractmethod
    def channel_type(self) -> ChannelType:
        """Return the channel type this gateway handles."""
        ...

    @abstractmethod
    async def send(
        self,
        recipient_id: str,
        content: str,
        media_url: str | None = None,
    ) -> DeliveryResult:
        """
        Send a message through this channel.

        Args:
            recipient_id: Target recipient (may be unused for page posts)
            content: Message content
            media_url: Optional media attachment URL

        Returns:
            DeliveryResult with success status and external ID
        """
        ...
