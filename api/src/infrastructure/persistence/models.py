from datetime import UTC, datetime
from typing import overload
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ...domain.entities import ChannelDelivery, Message, MessageStatus
from ...domain.value_objects import ChannelType, MessageContent


def _naive_utc(dt: datetime | None) -> datetime | None:
    """Strip timezone info for storage in TIMESTAMP WITHOUT TIME ZONE columns."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None)


@overload
def _aware_utc(dt: datetime) -> datetime: ...


@overload
def _aware_utc(dt: None) -> None: ...


@overload
def _aware_utc(dt: datetime | None) -> datetime | None: ...


def _aware_utc(dt: datetime | None) -> datetime | None:
    """Attach UTC timezone to naive datetimes read from the database."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class Base(DeclarativeBase):
    pass


class MessageModel(Base):
    """SQLAlchemy model for Message entity."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_media_url: Mapped[str | None] = mapped_column(String(2048))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    deliveries: Mapped[list["ChannelDeliveryModel"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    @classmethod
    def from_entity(cls, message: Message) -> "MessageModel":
        """Convert domain entity to ORM model."""
        model = cls(
            id=message.id,
            user_id=message.user_id,
            content_text=message.content.text,
            content_media_url=message.content.media_url,
            scheduled_at=_naive_utc(message.scheduled_at),
            status=message.status.value,
            recipient_id=message.recipient_id,
            created_at=_naive_utc(message.created_at),
            updated_at=_naive_utc(message.updated_at),
        )
        model.deliveries = [
            ChannelDeliveryModel.from_entity(d, message.id) for d in message.deliveries
        ]
        return model

    def to_entity(self) -> Message:
        """Convert ORM model to domain entity."""
        channels = [ChannelType(d.channel) for d in self.deliveries]
        message = Message(
            id=self.id,
            content=MessageContent(text=self.content_text, media_url=self.content_media_url),
            channels=channels,
            scheduled_at=_aware_utc(self.scheduled_at),
            status=MessageStatus(self.status),
            recipient_id=self.recipient_id,
            user_id=self.user_id,
            created_at=_aware_utc(self.created_at),
            updated_at=_aware_utc(self.updated_at),
            deliveries=[d.to_entity() for d in self.deliveries],
        )
        return message


class ChannelDeliveryModel(Base):
    """SQLAlchemy model for channel delivery tracking."""

    __tablename__ = "channel_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(Text)

    message: Mapped["MessageModel"] = relationship(back_populates="deliveries")

    @classmethod
    def from_entity(cls, delivery: ChannelDelivery, message_id: UUID) -> "ChannelDeliveryModel":
        return cls(
            message_id=message_id,
            channel=delivery.channel.value,
            status=delivery.status.value,
            delivered_at=_naive_utc(delivery.delivered_at),
            error=delivery.error,
        )

    def to_entity(self) -> ChannelDelivery:
        return ChannelDelivery(
            channel=ChannelType(self.channel),
            status=MessageStatus(self.status),
            delivered_at=_aware_utc(self.delivered_at),
            error=self.error,
        )


class CertificationSubmissionModel(Base):
    """SQLAlchemy model for certification submissions."""

    __tablename__ = "certification_submissions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    member_name: Mapped[str] = mapped_column(String(100), nullable=False)
    certification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    certification_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String(2048))
    linkedin_url: Mapped[str | None] = mapped_column(String(2048))
    personal_message: Mapped[str | None] = mapped_column(String(280))
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    deliveries: Mapped[list["CertificationDeliveryModel"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )


class CertificationDeliveryModel(Base):
    """SQLAlchemy model for certification delivery tracking."""

    __tablename__ = "certification_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    submission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("certification_submissions.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    external_post_id: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)

    submission: Mapped["CertificationSubmissionModel"] = relationship(back_populates="deliveries")
