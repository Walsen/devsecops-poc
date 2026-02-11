"""
Message processor for the worker service.

This module handles incoming messages from Kinesis and delegates
to the MessageDeliveryService for actual delivery.

Following hexagonal architecture, this class depends on ports (abstractions)
rather than concrete implementations.
"""

from uuid import UUID

import structlog

from .application.services import MessageDeliveryService
from .domain.ports import MessageRepository, SocialMediaPublisher

logger = structlog.get_logger()


class MessageProcessor:
    """
    Processes messages from Kinesis and delivers to channels.

    Uses the MessageDeliveryService (application layer) which depends
    on the SocialMediaPublisher port. The publisher implementation
    (DirectPublisher or AgentPublisher) is injected via constructor.

    Following hexagonal architecture:
    - Depends on MessageRepository port (not SQLAlchemy directly)
    - Depends on SocialMediaPublisher port (not concrete publishers)
    """

    def __init__(
        self,
        message_repository: MessageRepository,
        publisher: SocialMediaPublisher,
    ) -> None:
        """
        Initialize with injected dependencies.

        Args:
            message_repository: Implementation of MessageRepository port
            publisher: Implementation of SocialMediaPublisher port
        """
        self._repository = message_repository
        self._delivery_service = MessageDeliveryService(publisher)

    async def process_scheduled_message(
        self,
        message_id: str,
        channels: list[str],
    ) -> None:
        """
        Process a scheduled message and deliver to all channels.

        Args:
            message_id: UUID of the message to process
            channels: List of channel names to deliver to
        """
        logger.info(
            "Processing message",
            message_id=message_id,
            channels=channels,
        )

        # Fetch message from database via repository
        message = await self._repository.get_by_id(UUID(message_id))
        if not message:
            logger.error("Message not found", message_id=message_id)
            return

        # Mark as processing
        await self._repository.update_status(UUID(message_id), "processing")

        try:
            # Deliver using the application service
            result = await self._delivery_service.deliver(
                content=message.content,
                channels=channels,
                media_url=message.media_url,
                metadata=message.metadata,
            )

            # Update channel delivery statuses based on results
            for channel_type, channel_result in result.channel_results.items():
                channel_name = channel_type.value
                if channel_result.get("success"):
                    await self._repository.mark_channel_delivered(
                        UUID(message_id),
                        channel_name,
                        channel_result.get("external_id"),
                    )
                else:
                    await self._repository.mark_channel_failed(
                        UUID(message_id),
                        channel_name,
                        channel_result.get("error", "Unknown error"),
                    )

            # Update overall message status
            success_count = sum(1 for r in result.channel_results.values() if r.get("success"))
            if success_count == len(channels):
                await self._repository.update_status(UUID(message_id), "delivered")
            elif success_count > 0:
                await self._repository.update_status(UUID(message_id), "partial")
            else:
                await self._repository.update_status(UUID(message_id), "failed")

        except Exception as e:
            logger.error(
                "Message processing failed",
                message_id=message_id,
                error=str(e),
            )
            await self._repository.update_status(UUID(message_id), "failed")
