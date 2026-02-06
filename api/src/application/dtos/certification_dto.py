import html
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

from ...domain.entities.certification import (
    CertificationTypeEnum,
    DeliveryStatus,
    SubmissionStatus,
)
from ...domain.value_objects.channel_type import ChannelType


class CreateCertificationDTO(BaseModel):
    """DTO for creating a certification submission.

    Security: All string fields are sanitized to prevent XSS.
    """

    member_name: str = Field(..., min_length=2, max_length=100)
    certification_type: CertificationTypeEnum
    certification_date: datetime
    channels: list[ChannelType] = Field(..., min_length=1)
    photo_url: HttpUrl | None = None
    linkedin_url: HttpUrl | None = None
    personal_message: str | None = Field(None, max_length=280)
    user_id: str | None = None  # Set by auth middleware, not user input

    @field_validator("member_name", mode="after")
    @classmethod
    def sanitize_member_name(cls, v: str) -> str:
        """Security: Escape HTML to prevent XSS."""
        return html.escape(v.strip())

    @field_validator("personal_message", mode="after")
    @classmethod
    def sanitize_personal_message(cls, v: str | None) -> str | None:
        """Security: Escape HTML to prevent XSS."""
        if v is None:
            return None
        return html.escape(v.strip())


class ChannelDeliveryDTO(BaseModel):
    channel: ChannelType
    status: DeliveryStatus
    external_post_id: str | None = None
    error: str | None = None
    delivered_at: datetime | None = None


class CertificationResponseDTO(BaseModel):
    id: UUID
    status: SubmissionStatus
    member_name: str
    certification_type: CertificationTypeEnum
    certification_date: datetime
    photo_url: str | None = None
    linkedin_url: str | None = None
    personal_message: str | None = None
    deliveries: list[ChannelDeliveryDTO] = []
    created_at: datetime
    user_id: str | None = None  # For ownership verification


class CertificationTypeInfoDTO(BaseModel):
    id: CertificationTypeEnum
    name: str
    hashtag: str
    level: str
