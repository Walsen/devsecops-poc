from datetime import datetime

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .publisher import EventPublisher

logger = structlog.get_logger()


class MessageScheduler:
    """Polls for due messages and dispatches them to workers."""

    def __init__(self, session: AsyncSession, publisher: EventPublisher) -> None:
        self._session = session
        self._publisher = publisher

    async def process_due_messages(self) -> int:
        """Find and dispatch all messages that are due for delivery."""
        now = datetime.utcnow()
        
        logger.info("Checking for due messages", timestamp=now.isoformat())

        # Find scheduled messages that are due
        result = await self._session.execute(
            text("""
                SELECT m.id, array_agg(cd.channel) as channels
                FROM messages m
                JOIN channel_deliveries cd ON cd.message_id = m.id
                WHERE m.status = 'scheduled'
                  AND m.scheduled_at <= :now
                  AND cd.status = 'scheduled'
                GROUP BY m.id
                LIMIT :limit
            """),
            {"now": now, "limit": settings.batch_size},
        )
        
        messages = result.fetchall()
        
        if not messages:
            logger.debug("No due messages found")
            return 0

        # Dispatch each message to workers
        dispatched = 0
        for row in messages:
            message_id = str(row[0])
            channels = row[1]

            try:
                # Mark as processing to prevent duplicate dispatch
                await self._session.execute(
                    text("""
                        UPDATE messages 
                        SET status = 'processing', updated_at = NOW()
                        WHERE id = :id AND status = 'scheduled'
                    """),
                    {"id": message_id},
                )
                await self._session.commit()

                # Publish event for worker
                await self._publisher.publish_message_due(message_id, channels)
                dispatched += 1

            except Exception as e:
                logger.error(
                    "Failed to dispatch message",
                    message_id=message_id,
                    error=str(e),
                )
                await self._session.rollback()

        logger.info("Dispatched due messages", count=dispatched)
        return dispatched
