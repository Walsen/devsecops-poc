from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services import GetMessageService
from src.domain.entities import Message
from src.domain.value_objects import ChannelType, MessageContent

OWNER_ID = "user-owner-123"
OTHER_ID = "user-other-456"


class TestGetMessageService:
    @pytest.fixture
    def mock_repository(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repository):
        return GetMessageService(repository=mock_repository)

    @pytest.fixture
    def sample_message(self):
        message = Message.create(
            content=MessageContent(text="Test message"),
            channels=[ChannelType.WHATSAPP, ChannelType.EMAIL],
            scheduled_at=datetime.now(UTC) + timedelta(hours=1),
            recipient_id="recipient-123",
            user_id=OWNER_ID,
        )
        message.schedule()
        return message

    @pytest.mark.asyncio
    async def test_execute_returns_message_dto(self, service, mock_repository, sample_message):
        mock_repository.get_by_id.return_value = sample_message

        result = await service.execute(sample_message.id, user_id=OWNER_ID)

        assert result is not None
        assert result.id == sample_message.id
        assert result.content == "Test message"
        assert result.status == "scheduled"
        assert result.recipient_id == "recipient-123"
        assert len(result.deliveries) == 2

    @pytest.mark.asyncio
    async def test_execute_returns_none_for_nonexistent_message(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        result = await service.execute(uuid4(), user_id=OWNER_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_returns_none_for_other_users_message(
        self, service, mock_repository, sample_message
    ):
        """IDOR prevention: user cannot access another user's message."""
        mock_repository.get_by_id.return_value = sample_message

        result = await service.execute(sample_message.id, user_id=OTHER_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_maps_channels_correctly(self, service, mock_repository, sample_message):
        mock_repository.get_by_id.return_value = sample_message

        result = await service.execute(sample_message.id, user_id=OWNER_ID)

        assert "whatsapp" in result.channels
        assert "email" in result.channels

    @pytest.mark.asyncio
    async def test_execute_maps_deliveries_correctly(
        self, service, mock_repository, sample_message
    ):
        sample_message.mark_processing()
        sample_message.mark_channel_delivered(ChannelType.WHATSAPP)
        mock_repository.get_by_id.return_value = sample_message

        result = await service.execute(sample_message.id, user_id=OWNER_ID)

        whatsapp_delivery = next(d for d in result.deliveries if d.channel == "whatsapp")
        email_delivery = next(d for d in result.deliveries if d.channel == "email")

        assert whatsapp_delivery.status == "delivered"
        assert whatsapp_delivery.delivered_at is not None
        assert email_delivery.status == "scheduled"

    @pytest.mark.asyncio
    async def test_execute_includes_media_url(self, service, mock_repository):
        message = Message.create(
            content=MessageContent(
                text="With media",
                media_url="https://example.com/image.jpg",
            ),
            channels=[ChannelType.INSTAGRAM],
            scheduled_at=datetime.now(UTC),
            recipient_id="recipient-456",
            user_id=OWNER_ID,
        )
        mock_repository.get_by_id.return_value = message

        result = await service.execute(message.id, user_id=OWNER_ID)

        assert result.media_url == "https://example.com/image.jpg"
