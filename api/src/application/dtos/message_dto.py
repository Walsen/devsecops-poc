from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateMessageDTO(BaseModel):
    """DTO for creating a new message."""
    content: str = Field(..., min_length=1, max_length=4096)
    media_url: str | None = None
    channels: list[str] = Field(..., min_length=1)
    scheduled_at: datetime
    recipient_id: str


class ChannelDeliveryDTO(BaseModel):
    """DTO for channel delivery status."""
    channel: str
    status: str
    delivered_at: datetime | None = None
    error: str | None = None


class MessageResponseDTO(BaseModel):
    """DTO for message response."""
    id: UUID
    content: str
    media_url: str | None
    channels: list[str]
    scheduled_at: datetime
    status: str
    recipient_id: str
    created_at: datetime
    updated_at: datetime
    deliveries: list[ChannelDeliveryDTO]
