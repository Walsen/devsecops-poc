"""
SQLAlchemy implementation of the MessageRepository port.

This adapter implements the MessageRepository interface using SQLAlchemy
for database operations.
"""

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ...domain.ports import MessageRepository, MessageData

logger = structlog.get_logger()


class SqlAlchemyMessageRepository(MessageRepository):
    """
    SQLAlchemy implementation of MessageRepository.

    This adapter handles all database operations for messages,
    keeping SQL queries isolated from the application layer.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize with a database session.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session

    async def get_by_id(self, message_id: UUID) -> MessageData | None:
        """Retrieve a message by its ID."""
        result = await self._session.execute(
            text("""
                SELECT id, content_text, content_media_url, recipient_id, metadata, status
                FROM messages WHERE id = :id
            """),
            {"id": str(message_id)},
        )
        row = result.fetchone()

        if row:
            return MessageData(
                id=UUID(str(row[0])),
                content=row[1],
                media_url=row[2],
                recipient_id=row[3],
                metadata=row[4] if len(row) > 4 else None,
                status=row[5] if len(row) > 5 else "pending",
            )
        return None

    async def update_status(self, message_id: UUID, status: str) -> None:
        """Update the status of a message."""
        await self._session.execute(
            text("""
                UPDATE messages SET status = :status, updated_at = NOW()
                WHERE id = :id
            """),
            {"id": str(message_id), "status": status},
        )
        await self._session.commit()

        logger.info(
            "Message status updated",
            message_id=str(message_id),
            status=status,
        )

    async def mark_channel_delivered(
        self,
        message_id: UUID,
        channel: str,
        external_id: str | None = None,
    ) -> None:
        """Mark a channel delivery as successful."""
        await self._session.execute(
            text("""
                UPDATE channel_deliveries
                SET status = 'delivered', delivered_at = NOW(), external_id = :external_id
                WHERE message_id = :message_id AND channel = :channel
            """),
            {
                "message_id": str(message_id),
                "channel": channel,
                "external_id": external_id,
            },
        )
        await self._session.commit()

        logger.info(
            "Channel marked as delivered",
            message_id=str(message_id),
            channel=channel,
            external_id=external_id,
        )

    async def mark_channel_failed(
        self,
        message_id: UUID,
        channel: str,
        error: str,
    ) -> None:
        """Mark a channel delivery as failed."""
        await self._session.execute(
            text("""
                UPDATE channel_deliveries
                SET status = 'failed', error = :error
                WHERE message_id = :message_id AND channel = :channel
            """),
            {
                "message_id": str(message_id),
                "channel": channel,
                "error": error,
            },
        )
        await self._session.commit()

        logger.error(
            "Channel marked as failed",
            message_id=str(message_id),
            channel=channel,
            error=error,
        )
