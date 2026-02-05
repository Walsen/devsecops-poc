from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...domain.entities import Message, MessageStatus
from ...domain.repositories import MessageRepository
from .models import MessageModel


class PostgresMessageRepository(MessageRepository):
    """PostgreSQL implementation of MessageRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, message: Message) -> None:
        """Persist a message (insert or update)."""
        existing = await self._session.get(MessageModel, message.id)
        
        if existing:
            # Update existing
            existing.content_text = message.content.text
            existing.content_media_url = message.content.media_url
            existing.scheduled_at = message.scheduled_at
            existing.status = message.status.value
            existing.updated_at = message.updated_at
            # Update deliveries
            for i, delivery in enumerate(message.deliveries):
                if i < len(existing.deliveries):
                    existing.deliveries[i].status = delivery.status.value
                    existing.deliveries[i].delivered_at = delivery.delivered_at
                    existing.deliveries[i].error = delivery.error
        else:
            # Insert new
            model = MessageModel.from_entity(message)
            self._session.add(model)

    async def get_by_id(self, message_id: UUID) -> Message | None:
        """Retrieve a message by ID."""
        stmt = (
            select(MessageModel)
            .where(MessageModel.id == message_id)
            .options(selectinload(MessageModel.deliveries))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def get_scheduled_before(self, before: datetime) -> list[Message]:
        """Get messages scheduled before a given time that are ready to process."""
        stmt = (
            select(MessageModel)
            .where(
                MessageModel.scheduled_at <= before,
                MessageModel.status == MessageStatus.SCHEDULED.value,
            )
            .options(selectinload(MessageModel.deliveries))
            .limit(100)
        )
        result = await self._session.execute(stmt)
        return [model.to_entity() for model in result.scalars()]

    async def get_by_recipient(self, recipient_id: str, limit: int = 50) -> list[Message]:
        """Get messages for a recipient."""
        stmt = (
            select(MessageModel)
            .where(MessageModel.recipient_id == recipient_id)
            .options(selectinload(MessageModel.deliveries))
            .order_by(MessageModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [model.to_entity() for model in result.scalars()]
