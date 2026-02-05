from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ...domain.entities import Message, MessageStatus, ChannelDelivery
from ...domain.value_objects import ChannelType, MessageContent


class Base(DeclarativeBase):
    pass


class MessageModel(Base):
    """SQLAlchemy model for Message entity."""
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
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
            content_text=message.content.text,
            content_media_url=message.content.media_url,
            scheduled_at=message.scheduled_at,
            status=message.status.value,
            recipient_id=message.recipient_id,
            created_at=message.created_at,
            updated_at=message.updated_at,
        )
        model.deliveries = [
            ChannelDeliveryModel.from_entity(d, message.id)
            for d in message.deliveries
        ]
        return model

    def to_entity(self) -> Message:
        """Convert ORM model to domain entity."""
        channels = [ChannelType(d.channel) for d in self.deliveries]
        message = Message(
            id=self.id,
            content=MessageContent(text=self.content_text, media_url=self.content_media_url),
            channels=channels,
            scheduled_at=self.scheduled_at,
            status=MessageStatus(self.status),
            recipient_id=self.recipient_id,
            created_at=self.created_at,
            updated_at=self.updated_at,
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
            delivered_at=delivery.delivered_at,
            error=delivery.error,
        )

    def to_entity(self) -> ChannelDelivery:
        return ChannelDelivery(
            channel=ChannelType(self.channel),
            status=MessageStatus(self.status),
            delivered_at=self.delivered_at,
            error=self.error,
        )
