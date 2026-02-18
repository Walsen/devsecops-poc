from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities import Message
from src.domain.value_objects import ChannelType, MessageContent


@pytest.fixture
def sample_content() -> MessageContent:
    return MessageContent(text="Test message content")


@pytest.fixture
def sample_content_with_media() -> MessageContent:
    return MessageContent(
        text="Test message with media",
        media_url="https://example.com/image.jpg",
    )


@pytest.fixture
def sample_channels() -> list[ChannelType]:
    return [ChannelType.WHATSAPP, ChannelType.EMAIL]


@pytest.fixture
def sample_message(sample_content, sample_channels) -> Message:
    return Message.create(
        content=sample_content,
        channels=sample_channels,
        scheduled_at=datetime.now(UTC) + timedelta(hours=1),
        recipient_id="user-123",
    )


@pytest.fixture
def scheduled_message(sample_message) -> Message:
    sample_message.schedule()
    return sample_message
