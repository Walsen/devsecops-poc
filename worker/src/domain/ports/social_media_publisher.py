"""
Outbound port for social media publishing.

This is the interface for intelligent multi-channel publishing.
Can be implemented by direct API calls or AI agents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .channel_gateway import ChannelType


@dataclass
class PublishRequest:
    """Request to publish content across channels."""

    content: str
    channels: list[ChannelType]
    media_url: str | None = None
    metadata: dict | None = None  # Additional context (certification_type, member_name, etc.)


@dataclass
class PublishResult:
    """Result of a multi-channel publish operation."""

    channel_results: dict[ChannelType, dict]  # Results per channel
    summary: str | None = None  # Optional summary (from AI agent)
    metrics: dict | None = None  # Optional metrics


class SocialMediaPublisher(ABC):
    """
    Outbound port for publishing to social media.

    This abstraction allows swapping between:
    - Direct API publishing (simple, fast)
    - AI Agent publishing (intelligent, adaptive)
    """

    @abstractmethod
    async def publish(self, request: PublishRequest) -> PublishResult:
        """
        Publish content to the requested channels.

        Args:
            request: PublishRequest with content and target channels

        Returns:
            PublishResult with per-channel results
        """
        ...
