from abc import ABC, abstractmethod
from uuid import UUID

from ...dtos import MessageResponseDTO


class GetMessageUseCase(ABC):
    """Input port for retrieving message details."""

    @abstractmethod
    async def execute(self, message_id: UUID, user_id: str) -> MessageResponseDTO | None:
        """Get message by ID, scoped to the authenticated user."""
        ...
