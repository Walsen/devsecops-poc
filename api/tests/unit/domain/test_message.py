from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities import Message, MessageStatus
from src.domain.value_objects import ChannelType


class TestMessageCreation:
    def test_create_message_with_valid_data(self, sample_content, sample_channels):
        scheduled_at = datetime.now(UTC) + timedelta(hours=1)

        message = Message.create(
            content=sample_content,
            channels=sample_channels,
            scheduled_at=scheduled_at,
            recipient_id="user-123",
            user_id="test-user-001",
        )

        assert message.id is not None
        assert message.content == sample_content
        assert message.channels == sample_channels
        assert message.scheduled_at == scheduled_at
        assert message.recipient_id == "user-123"
        assert message.status == MessageStatus.DRAFT
        assert len(message.deliveries) == len(sample_channels)

    def test_create_message_initializes_deliveries(self, sample_content, sample_channels):
        message = Message.create(
            content=sample_content,
            channels=sample_channels,
            scheduled_at=datetime.now(UTC),
            recipient_id="user-123",
            user_id="test-user-001",
        )

        assert len(message.deliveries) == 2
        assert message.deliveries[0].channel == ChannelType.WHATSAPP
        assert message.deliveries[1].channel == ChannelType.EMAIL
        assert all(d.status == MessageStatus.SCHEDULED for d in message.deliveries)


class TestMessageScheduling:
    def test_schedule_draft_message(self, sample_message):
        assert sample_message.status == MessageStatus.DRAFT

        sample_message.schedule()

        assert sample_message.status == MessageStatus.SCHEDULED

    def test_schedule_already_scheduled_raises_error(self, scheduled_message):
        with pytest.raises(ValueError, match="Cannot schedule message"):
            scheduled_message.schedule()

    def test_schedule_updates_timestamp(self, sample_message):
        original_updated = sample_message.updated_at

        sample_message.schedule()

        assert sample_message.updated_at >= original_updated


class TestMessageProcessing:
    def test_mark_processing(self, scheduled_message):
        scheduled_message.mark_processing()

        assert scheduled_message.status == MessageStatus.PROCESSING

    def test_mark_channel_delivered(self, scheduled_message):
        scheduled_message.mark_processing()
        scheduled_message.mark_channel_delivered(ChannelType.WHATSAPP)

        whatsapp_delivery = next(
            d for d in scheduled_message.deliveries if d.channel == ChannelType.WHATSAPP
        )
        assert whatsapp_delivery.status == MessageStatus.DELIVERED
        assert whatsapp_delivery.delivered_at is not None

    def test_mark_channel_failed(self, scheduled_message):
        scheduled_message.mark_processing()
        scheduled_message.mark_channel_failed(ChannelType.EMAIL, "API error")

        email_delivery = next(
            d for d in scheduled_message.deliveries if d.channel == ChannelType.EMAIL
        )
        assert email_delivery.status == MessageStatus.FAILED
        assert email_delivery.error == "API error"


class TestMessageStatusAggregation:
    def test_all_delivered_sets_delivered_status(self, scheduled_message):
        scheduled_message.mark_processing()
        scheduled_message.mark_channel_delivered(ChannelType.WHATSAPP)
        scheduled_message.mark_channel_delivered(ChannelType.EMAIL)

        assert scheduled_message.status == MessageStatus.DELIVERED

    def test_all_failed_sets_failed_status(self, scheduled_message):
        scheduled_message.mark_processing()
        scheduled_message.mark_channel_failed(ChannelType.WHATSAPP, "Error 1")
        scheduled_message.mark_channel_failed(ChannelType.EMAIL, "Error 2")

        assert scheduled_message.status == MessageStatus.FAILED

    def test_partial_delivery_sets_partially_delivered(self, scheduled_message):
        scheduled_message.mark_processing()
        scheduled_message.mark_channel_delivered(ChannelType.WHATSAPP)
        scheduled_message.mark_channel_failed(ChannelType.EMAIL, "Error")

        assert scheduled_message.status == MessageStatus.PARTIALLY_DELIVERED
