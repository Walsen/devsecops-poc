"""Message DTOs with input sanitization.

Security: All user-provided string fields are sanitized to prevent XSS.
"""

import html
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CreateMessageDTO(BaseModel):
    """DTO for creating a new message.

    Security: Content is sanitized to prevent XSS attacks.
    """

    content: str = Field(..., min_length=1, max_length=4096)
    media_url: str | None = None
    channels: list[str] = Field(..., min_length=1)
    scheduled_at: datetime
    recipient_id: str
    user_id: str | None = None  # Set by auth middleware

    @field_validator("content", mode="after")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        """Security: Escape HTML to prevent XSS."""
        return html.escape(v.strip())

    @field_validator("recipient_id", mode="after")
    @classmethod
    def sanitize_recipient_id(cls, v: str) -> str:
        """Security: Escape HTML to prevent XSS."""
        return html.escape(v.strip())


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
    user_id: str | None = None  # For ownership verification
