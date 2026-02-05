"""
Application service for message delivery.

This service orchestrates the delivery of messages using the appropriate publisher.
It depends on abstractions (ports), not concrete implementations.
"""

import structlog

from ...domain.ports import ChannelType, SocialMediaPublisher, PublishRequest, PublishResult

logger = structlog.get_logger()


class MessageDeliveryService:
    """
    Application service that handles message delivery.
    
    This service:
    - Receives messages from the Kinesis consumer
    - Delegates to the appropriate publisher (direct or AI agent)
    - Handles errors and logging
    
    Following hexagonal architecture, this service depends on the
    SocialMediaPublisher port, not concrete implementations.
    """

    def __init__(self, publisher: SocialMediaPublisher) -> None:
        """
        Initialize with a publisher implementation.
        
        Args:
            publisher: Implementation of SocialMediaPublisher port
                      (DirectPublisher or AgentPublisher)
        """
        self._publisher = publisher

    async def deliver(
        self,
        content: str,
        channels: list[str],
        media_url: str | None = None,
        metadata: dict | None = None,
    ) -> PublishResult:
        """
        Deliver a message to the specified channels.
        
        Args:
            content: Message content to deliver
            channels: List of channel names (facebook, instagram, etc.)
            media_url: Optional media attachment
            metadata: Optional metadata (certification_type, member_name, etc.)
            
        Returns:
            PublishResult with per-channel results
        """
        # Convert channel strings to ChannelType enum
        channel_types = []
        for channel in channels:
            try:
                channel_types.append(ChannelType(channel.lower()))
            except ValueError:
                logger.warning("Unknown channel type", channel=channel)
                continue

        if not channel_types:
            logger.error("No valid channels specified")
            return PublishResult(channel_results={}, summary="No valid channels")

        request = PublishRequest(
            content=content,
            channels=channel_types,
            media_url=media_url,
            metadata=metadata,
        )

        logger.info(
            "Delivering message",
            channels=[c.value for c in channel_types],
            has_media=bool(media_url),
        )

        result = await self._publisher.publish(request)

        # Log results
        success_count = sum(
            1 for r in result.channel_results.values() 
            if r.get("success", False)
        )
        logger.info(
            "Message delivery completed",
            total_channels=len(channel_types),
            successful=success_count,
        )

        return result
