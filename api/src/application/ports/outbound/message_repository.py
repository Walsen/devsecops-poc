from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from ....domain.entities import Message


class MessageRepository(ABC):
    """Output port for message persistence."""

    @abstractmethod
    async def save(self, message: Message) -> None:
        """Persist a message."""
        ...

    @abstractmethod
    async def get_by_id(self, message_id: UUID) -> Message | None:
        """Retrieve a message by ID."""
        ...

    @abstractmethod
    async def get_scheduled_before(self, before: datetime) -> list[Message]:
        """Get messages scheduled before a given time."""
        ...

    @abstractmethod
    async def get_by_recipient(self, recipient_id: str, limit: int = 50) -> list[Message]:
        """Get messages for a recipient."""
        ...
