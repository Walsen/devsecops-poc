from abc import ABC, abstractmethod
from typing import Any


class EventPublisher(ABC):
    """Abstract interface for publishing domain events."""

    @abstractmethod
    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish an event to the message queue."""
        ...
