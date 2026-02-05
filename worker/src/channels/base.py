from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeliveryResult:
    """Result of a channel delivery attempt."""
    success: bool
    external_id: str | None = None
    error: str | None = None


class ChannelGateway(ABC):
    """Abstract base for channel delivery gateways."""

    @abstractmethod
    async def send(
        self,
        recipient_id: str,
        content: str,
        media_url: str | None = None,
    ) -> DeliveryResult:
        """Send a message through this channel."""
        ...
