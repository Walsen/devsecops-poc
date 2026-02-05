from uuid import UUID

from ...domain.repositories import MessageRepository
from ..dtos import ChannelDeliveryDTO, MessageResponseDTO


class GetMessageQuery:
    """Query for retrieving message details."""

    def __init__(self, repository: MessageRepository) -> None:
        self._repository = repository

    async def execute(self, message_id: UUID) -> MessageResponseDTO | None:
        """Get message by ID."""
        message = await self._repository.get_by_id(message_id)
        if not message:
            return None

        return MessageResponseDTO(
            id=message.id,
            content=message.content.text,
            media_url=message.content.media_url,
            channels=[ch.value for ch in message.channels],
            scheduled_at=message.scheduled_at,
            status=message.status.value,
            recipient_id=message.recipient_id,
            created_at=message.created_at,
            updated_at=message.updated_at,
            deliveries=[
                ChannelDeliveryDTO(
                    channel=d.channel.value,
                    status=d.status.value,
                    delivered_at=d.delivered_at,
                    error=d.error,
                )
                for d in message.deliveries
            ],
        )
