"""
Message processor for the worker service.

This module handles incoming messages from Kinesis and delegates
to the MessageDeliveryService for actual delivery.
"""

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from .application.services import MessageDeliveryService
from .infrastructure.adapters import DirectPublisher, AgentPublisher
from .config import settings

logger = structlog.get_logger()


class MessageProcessor:
    """
    Processes messages from Kinesis and delivers to channels.

    Uses the MessageDeliveryService (application layer) which depends
    on the SocialMediaPublisher port. The publisher implementation
    (DirectPublisher or AgentPublisher) is selected based on config.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._delivery_service = self._init_delivery_service()

    def _init_delivery_service(self) -> MessageDeliveryService:
        """Initialize the delivery service with appropriate publisher."""
        if settings.use_ai_agent:
            logger.info("Using AI Agent publisher for intelligent content adaptation")
            publisher = AgentPublisher()
        else:
            logger.info("Using Direct publisher for simple delivery")
            publisher = DirectPublisher()

        return MessageDeliveryService(publisher)

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

        # Fetch message from database
        message = await self._get_message(UUID(message_id))
        if not message:
            logger.error("Message not found", message_id=message_id)
            return

        # Mark as processing
        await self._update_status(message_id, "processing")

        try:
            # Deliver using the application service
            result = await self._delivery_service.deliver(
                content=message["content"],
                channels=channels,
                media_url=message.get("media_url"),
                metadata=message.get("metadata"),
            )

            # Update channel delivery statuses based on results
            for channel_type, channel_result in result.channel_results.items():
                channel_name = channel_type.value
                if channel_result.get("success"):
                    await self._mark_channel_delivered(
                        message_id,
                        channel_name,
                        channel_result.get("external_id"),
                    )
                else:
                    await self._mark_channel_failed(
                        message_id,
                        channel_name,
                        channel_result.get("error", "Unknown error"),
                    )

            # Update overall message status
            success_count = sum(1 for r in result.channel_results.values() if r.get("success"))
            if success_count == len(channels):
                await self._update_status(message_id, "delivered")
            elif success_count > 0:
                await self._update_status(message_id, "partial")
            else:
                await self._update_status(message_id, "failed")

        except Exception as e:
            logger.error(
                "Message processing failed",
                message_id=message_id,
                error=str(e),
            )
            await self._update_status(message_id, "failed")

    async def _get_message(self, message_id: UUID) -> dict | None:
        """Fetch message from database."""
        result = await self._session.execute(
            """
            SELECT id, content_text, content_media_url, recipient_id, metadata
            FROM messages WHERE id = :id
            """,
            {"id": str(message_id)},
        )
        row = result.fetchone()
        if row:
            return {
                "id": str(row[0]),
                "content": row[1],
                "media_url": row[2],
                "recipient_id": row[3],
                "metadata": row[4] if len(row) > 4 else None,
            }
        return None

    async def _update_status(self, message_id: str, status: str) -> None:
        """Update message status."""
        await self._session.execute(
            """
            UPDATE messages SET status = :status, updated_at = NOW()
            WHERE id = :id
            """,
            {"id": message_id, "status": status},
        )
        await self._session.commit()

    async def _mark_channel_delivered(
        self,
        message_id: str,
        channel: str,
        external_id: str | None,
    ) -> None:
        """Mark channel as delivered."""
        logger.info(
            "Channel delivered",
            message_id=message_id,
            channel=channel,
            external_id=external_id,
        )
        await self._session.execute(
            """
            UPDATE channel_deliveries
            SET status = 'delivered', delivered_at = NOW(), external_id = :external_id
            WHERE message_id = :message_id AND channel = :channel
            """,
            {"message_id": message_id, "channel": channel, "external_id": external_id},
        )
        await self._session.commit()

    async def _mark_channel_failed(
        self,
        message_id: str,
        channel: str,
        error: str,
    ) -> None:
        """Mark channel as failed."""
        logger.error(
            "Channel failed",
            message_id=message_id,
            channel=channel,
            error=error,
        )
        await self._session.execute(
            """
            UPDATE channel_deliveries
            SET status = 'failed', error = :error
            WHERE message_id = :message_id AND channel = :channel
            """,
            {"message_id": message_id, "channel": channel, "error": error},
        )
        await self._session.commit()
