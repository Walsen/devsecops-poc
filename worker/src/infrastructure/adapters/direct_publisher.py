"""
Direct publisher implementation.

This adapter implements SocialMediaPublisher by directly calling channel gateways.
Simple, fast, but no content optimization.
"""

import structlog

from ...domain.ports import (
    SocialMediaPublisher,
    PublishRequest,
    PublishResult,
    ChannelType,
)
from .channel_gateway_factory import ChannelGatewayFactory

logger = structlog.get_logger()


class DirectPublisher(SocialMediaPublisher):
    """
    Direct implementation of SocialMediaPublisher.
    
    Posts the same content to all channels without optimization.
    Fast and simple, but doesn't adapt content per platform.
    """

    async def publish(self, request: PublishRequest) -> PublishResult:
        """
        Publish content directly to all requested channels.
        
        Args:
            request: PublishRequest with content and channels
            
        Returns:
            PublishResult with per-channel results
        """
        channel_results: dict[ChannelType, dict] = {}
        
        # Create tasks for parallel execution
        tasks = []
        for channel_type in request.channels:
            task = self._publish_to_channel(
                channel_type=channel_type,
                content=request.content,
                media_url=request.media_url,
            )
            tasks.append((channel_type, task))

        # Execute all tasks concurrently
        for channel_type, task in tasks:
            try:
                result = await task
                channel_results[channel_type] = {
                    "success": result.success,
                    "external_id": result.external_id,
                    "error": result.error,
                }
            except Exception as e:
                logger.error(
                    "Channel publish failed",
                    channel=channel_type.value,
                    error=str(e),
                )
                channel_results[channel_type] = {
                    "success": False,
                    "error": str(e),
                }

        # Generate summary
        success_count = sum(1 for r in channel_results.values() if r.get("success"))
        summary = f"Published to {success_count}/{len(request.channels)} channels"

        return PublishResult(
            channel_results=channel_results,
            summary=summary,
        )

    async def _publish_to_channel(
        self,
        channel_type: ChannelType,
        content: str,
        media_url: str | None,
    ):
        """Publish to a single channel."""
        gateway = ChannelGatewayFactory.get_gateway(channel_type)
        
        # Instagram requires media
        if channel_type == ChannelType.INSTAGRAM and not media_url:
            from ...domain.ports.channel_gateway import DeliveryResult
            return DeliveryResult(
                success=False,
                channel=channel_type,
                error="Instagram requires a media URL",
            )

        return await gateway.send(
            recipient_id="",  # Not used for page posts
            content=content,
            media_url=media_url,
        )
