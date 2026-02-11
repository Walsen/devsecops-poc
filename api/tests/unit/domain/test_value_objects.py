import pytest

from src.domain.value_objects import ChannelType, MessageContent


class TestMessageContent:
    def test_create_valid_content(self):
        content = MessageContent(text="Hello, world!")

        assert content.text == "Hello, world!"
        assert content.media_url is None

    def test_create_content_with_media(self):
        content = MessageContent(
            text="Check this out!",
            media_url="https://example.com/image.jpg",
        )

        assert content.text == "Check this out!"
        assert content.media_url == "https://example.com/image.jpg"

    def test_create_content_with_s3_url(self):
        content = MessageContent(
            text="S3 media",
            media_url="s3://bucket/key.jpg",
        )

        assert content.media_url == "s3://bucket/key.jpg"

    def test_empty_text_raises_error(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            MessageContent(text="")

    def test_whitespace_only_text_raises_error(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            MessageContent(text="   ")

    def test_text_exceeds_max_length_raises_error(self):
        long_text = "x" * 4097

        with pytest.raises(ValueError, match="cannot exceed 4096"):
            MessageContent(text=long_text)

    def test_text_at_max_length_is_valid(self):
        max_text = "x" * 4096
        content = MessageContent(text=max_text)

        assert len(content.text) == 4096

    def test_invalid_media_url_raises_error(self):
        with pytest.raises(ValueError, match="must be HTTPS or S3"):
            MessageContent(text="Test", media_url="http://insecure.com/image.jpg")

    def test_content_is_immutable(self):
        content = MessageContent(text="Original")

        with pytest.raises(AttributeError):
            content.text = "Modified"


class TestChannelType:
    def test_all_channels_exist(self):
        assert ChannelType.WHATSAPP.value == "whatsapp"
        assert ChannelType.FACEBOOK.value == "facebook"
        assert ChannelType.INSTAGRAM.value == "instagram"
        assert ChannelType.EMAIL.value == "email"
        assert ChannelType.SMS.value == "sms"

    def test_channel_from_string(self):
        channel = ChannelType("whatsapp")
        assert channel == ChannelType.WHATSAPP

    def test_invalid_channel_raises_error(self):
        with pytest.raises(ValueError, match="invalid_channel"):
            ChannelType("invalid_channel")
