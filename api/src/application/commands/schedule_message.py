from uuid import UUID

from ...domain.entities import Message
from ...domain.repositories import MessageRepository
from ...domain.value_objects import ChannelType, MessageContent
from ..dtos import CreateMessageDTO
from ..interfaces import EventPublisher, UnitOfWork


class ScheduleMessageCommand:
    """Use case for scheduling a message for delivery."""

    def __init__(
        self,
        repository: MessageRepository,
        event_publisher: EventPublisher,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher
        self._uow = unit_of_work

    async def execute(self, dto: CreateMessageDTO) -> UUID:
        """Schedule a message and publish event for async processing."""
        # Create domain entity with validation
        content = MessageContent(text=dto.content, media_url=dto.media_url)
        channels = [ChannelType(ch) for ch in dto.channels]

        message = Message.create(
            content=content,
            channels=channels,
            scheduled_at=dto.scheduled_at,
            recipient_id=dto.recipient_id,
        )

        # Schedule the message
        message.schedule()

        # Persist within transaction
        async with self._uow:
            await self._repository.save(message)
            await self._uow.commit()

        # Publish event for async workers (outside transaction)
        await self._event_publisher.publish(
            event_type="message.scheduled",
            payload={
                "message_id": str(message.id),
                "channels": [ch.value for ch in channels],
                "scheduled_at": dto.scheduled_at.isoformat(),
            },
        )

        return message.id
