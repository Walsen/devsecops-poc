from abc import ABC, abstractmethod
from uuid import UUID

from ...dtos import CreateMessageDTO


class ScheduleMessageUseCase(ABC):
    """Input port for scheduling a message."""

    @abstractmethod
    async def execute(self, dto: CreateMessageDTO) -> UUID:
        """Schedule a message for delivery."""
        ...
