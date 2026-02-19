from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.application.dtos import CreateMessageDTO
from src.application.services import ScheduleMessageService
from src.domain.entities import Message, MessageStatus


class TestScheduleMessageService:
    @pytest.fixture
    def mock_repository(self):
        return AsyncMock()

    @pytest.fixture
    def mock_event_publisher(self):
        return AsyncMock()

    @pytest.fixture
    def mock_unit_of_work(self):
        uow = AsyncMock()
        uow.__aenter__ = AsyncMock(return_value=uow)
        uow.__aexit__ = AsyncMock(return_value=None)
        return uow

    @pytest.fixture
    def service(self, mock_repository, mock_event_publisher, mock_unit_of_work):
        return ScheduleMessageService(
            repository=mock_repository,
            event_publisher=mock_event_publisher,
            unit_of_work=mock_unit_of_work,
        )

    @pytest.fixture
    def valid_dto(self):
        return CreateMessageDTO(
            content="Test message",
            channels=["whatsapp", "email"],
            scheduled_at=datetime.now(UTC) + timedelta(hours=1),
            recipient_id="user-123",
            user_id="auth-user-001",
        )

    @pytest.mark.asyncio
    async def test_execute_creates_and_saves_message(self, service, valid_dto, mock_repository):
        result = await service.execute(valid_dto)

        assert isinstance(result, UUID)
        mock_repository.save.assert_called_once()

        saved_message = mock_repository.save.call_args[0][0]
        assert isinstance(saved_message, Message)
        assert saved_message.status == MessageStatus.SCHEDULED

    @pytest.mark.asyncio
    async def test_execute_commits_transaction(self, service, valid_dto, mock_unit_of_work):
        await service.execute(valid_dto)

        mock_unit_of_work.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_publishes_event(self, service, valid_dto, mock_event_publisher):
        result = await service.execute(valid_dto)

        mock_event_publisher.publish.assert_called_once()
        call_args = mock_event_publisher.publish.call_args

        assert call_args[1]["event_type"] == "message.scheduled"
        assert call_args[1]["payload"]["message_id"] == str(result)
        assert call_args[1]["payload"]["channels"] == ["whatsapp", "email"]

    @pytest.mark.asyncio
    async def test_execute_with_media_url(self, service, mock_repository):
        dto = CreateMessageDTO(
            content="Message with media",
            media_url="https://example.com/image.jpg",
            channels=["instagram"],
            scheduled_at=datetime.now(UTC) + timedelta(hours=1),
            recipient_id="user-456",
            user_id="auth-user-001",
        )

        await service.execute(dto)

        saved_message = mock_repository.save.call_args[0][0]
        assert saved_message.content.media_url == "https://example.com/image.jpg"

    @pytest.mark.asyncio
    async def test_execute_with_invalid_channel_raises_error(self, service):
        dto = CreateMessageDTO(
            content="Test",
            channels=["invalid_channel"],
            scheduled_at=datetime.now(UTC) + timedelta(hours=1),
            recipient_id="user-123",
            user_id="auth-user-001",
        )

        with pytest.raises(ValueError, match="invalid_channel"):
            await service.execute(dto)

    @pytest.mark.asyncio
    async def test_execute_with_empty_content_raises_error(self, service):
        with pytest.raises(ValidationError):
            CreateMessageDTO(
                content="",
                channels=["whatsapp"],
                scheduled_at=datetime.now(UTC) + timedelta(hours=1),
                recipient_id="user-123",
            )
