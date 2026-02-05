import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.channels import (
    WhatsAppGateway,
    FacebookGateway,
    InstagramGateway,
    EmailGateway,
    SmsGateway,
    DeliveryResult,
)


class TestWhatsAppGateway:
    @pytest.fixture
    def gateway(self):
        return WhatsAppGateway(
            access_token="test-token",
            phone_number_id="123456789",
        )

    @pytest.mark.asyncio
    async def test_send_text_message_success(self, gateway):
        mock_response = MagicMock()
        mock_response.json.return_value = {"messages": [{"id": "wamid.123"}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await gateway.send(
                recipient_id="+1234567890",
                content="Hello!",
            )
        
        assert result.success is True
        assert result.external_id == "wamid.123"

    @pytest.mark.asyncio
    async def test_send_with_media(self, gateway):
        mock_response = MagicMock()
        mock_response.json.return_value = {"messages": [{"id": "wamid.456"}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await gateway.send(
                recipient_id="+1234567890",
                content="Check this!",
                media_url="https://example.com/image.jpg",
            )
        
        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_api_error(self, gateway):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Error",
                    request=MagicMock(),
                    response=MagicMock(status_code=401),
                )
            )
            
            result = await gateway.send(
                recipient_id="+1234567890",
                content="Hello!",
            )
        
        assert result.success is False
        assert "401" in result.error


class TestFacebookGateway:
    @pytest.fixture
    def gateway(self):
        return FacebookGateway(
            access_token="test-token",
            page_id="page123",
        )

    @pytest.mark.asyncio
    async def test_post_text_success(self, gateway):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "post_123"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await gateway.send(
                recipient_id="",  # Not used for page posts
                content="Hello Facebook!",
            )
        
        assert result.success is True
        assert result.external_id == "post_123"


class TestInstagramGateway:
    @pytest.fixture
    def gateway(self):
        return InstagramGateway(
            access_token="test-token",
            instagram_account_id="ig123",
        )

    @pytest.mark.asyncio
    async def test_post_requires_media(self, gateway):
        result = await gateway.send(
            recipient_id="",
            content="No media",
            media_url=None,
        )
        
        assert result.success is False
        assert "require" in result.error.lower()


class TestEmailGateway:
    @pytest.fixture
    def gateway(self):
        return EmailGateway(
            sender_email="noreply@example.com",
            region="us-east-1",
        )

    @pytest.mark.asyncio
    async def test_send_email_success(self, gateway):
        with patch.object(gateway, "_session") as mock_session:
            mock_client = AsyncMock()
            mock_client.send_email = AsyncMock(
                return_value={"MessageId": "ses-msg-123"}
            )
            mock_session.create_client.return_value.__aenter__.return_value = mock_client
            
            result = await gateway.send(
                recipient_id="user@example.com",
                content="Hello via email!",
            )
        
        assert result.success is True
        assert result.external_id == "ses-msg-123"


class TestSmsGateway:
    @pytest.fixture
    def gateway(self):
        return SmsGateway(
            sender_id="MyApp",
            region="us-east-1",
        )

    @pytest.mark.asyncio
    async def test_send_sms_success(self, gateway):
        with patch.object(gateway, "_session") as mock_session:
            mock_client = AsyncMock()
            mock_client.publish = AsyncMock(
                return_value={"MessageId": "sns-msg-456"}
            )
            mock_session.create_client.return_value.__aenter__.return_value = mock_client
            
            result = await gateway.send(
                recipient_id="+1234567890",
                content="Hello via SMS!",
            )
        
        assert result.success is True
        assert result.external_id == "sns-msg-456"


class TestDeliveryResult:
    def test_success_result(self):
        result = DeliveryResult(success=True, external_id="123")
        
        assert result.success is True
        assert result.external_id == "123"
        assert result.error is None

    def test_failure_result(self):
        result = DeliveryResult(success=False, error="API error")
        
        assert result.success is False
        assert result.external_id is None
        assert result.error == "API error"
