import asyncio
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from .channels import (
    ChannelGateway,
    EmailGateway,
    FacebookGateway,
    InstagramGateway,
    SmsGateway,
    WhatsAppGateway,
)
from .config import settings

logger = structlog.get_logger()


class MessageProcessor:
    """Processes messages and delivers to channels."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._gateways = self._init_gateways()

    def _init_gateways(self) -> dict[str, ChannelGateway]:
        """Initialize channel gateways."""
        gateways: dict[str, ChannelGateway] = {}

        if settings.meta_access_token:
            if settings.meta_phone_number_id:
                gateways["whatsapp"] = WhatsAppGateway(
                    settings.meta_access_token,
                    settings.meta_phone_number_id,
                )
            if settings.meta_page_id:
                gateways["facebook"] = FacebookGateway(
                    settings.meta_access_token,
                    settings.meta_page_id,
                )
            if settings.meta_instagram_account_id:
                gateways["instagram"] = InstagramGateway(
                    settings.meta_access_token,
                    settings.meta_instagram_account_id,
                )

        if settings.ses_sender_email:
            gateways["email"] = EmailGateway(
                settings.ses_sender_email,
                settings.aws_region,
            )

        gateways["sms"] = SmsGateway(
            settings.sns_sender_id,
            settings.aws_region,
        )

        return gateways

    async def process_scheduled_message(
        self,
        message_id: str,
        channels: list[str],
    ) -> None:
        """Process a scheduled message and deliver to all channels."""
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

        # Deliver to each channel concurrently
        tasks = [
            self._deliver_to_channel(message, channel)
            for channel in channels
            if channel in self._gateways
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log results
        for channel, result in zip(channels, results):
            if isinstance(result, Exception):
                logger.error(
                    "Channel delivery exception",
                    channel=channel,
                    error=str(result),
                )

    async def _deliver_to_channel(
        self,
        message: dict,
        channel: str,
    ) -> None:
        """Deliver message to a specific channel."""
        gateway = self._gateways.get(channel)
        if not gateway:
            logger.warning("No gateway for channel", channel=channel)
            return

        result = await gateway.send(
            recipient_id=message["recipient_id"],
            content=message["content"],
            media_url=message.get("media_url"),
        )

        if result.success:
            await self._mark_channel_delivered(
                message["id"],
                channel,
                result.external_id,
            )
        else:
            await self._mark_channel_failed(
                message["id"],
                channel,
                result.error or "Unknown error",
            )

    async def _get_message(self, message_id: UUID) -> dict | None:
        """Fetch message from database."""
        # Using raw SQL for simplicity - in production, use repository pattern
        result = await self._session.execute(
            """
            SELECT id, content_text, content_media_url, recipient_id
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
            SET status = 'delivered', delivered_at = NOW()
            WHERE message_id = :message_id AND channel = :channel
            """,
            {"message_id": message_id, "channel": channel},
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
