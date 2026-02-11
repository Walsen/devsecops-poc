import httpx
import structlog

from .base import ChannelGateway, ChannelType, DeliveryResult

logger = structlog.get_logger()


class WhatsAppGateway(ChannelGateway):
    """WhatsApp Business API gateway."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, access_token: str, phone_number_id: str) -> None:
        self._access_token = access_token
        self._phone_number_id = phone_number_id

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.WHATSAPP

    async def send(
        self,
        recipient_id: str,
        content: str,
        media_url: str | None = None,
    ) -> DeliveryResult:
        """Send a WhatsApp message."""
        url = f"{self.BASE_URL}/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        # Build message payload
        if media_url:
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient_id,
                "type": "image",
                "image": {"link": media_url, "caption": content},
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient_id,
                "type": "text",
                "text": {"body": content},
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                message_id = data.get("messages", [{}])[0].get("id")
                logger.info("WhatsApp message sent", message_id=message_id, recipient=recipient_id)

                return DeliveryResult(success=True, external_id=message_id)

        except httpx.HTTPStatusError as e:
            error_msg = f"WhatsApp API error: {e.response.status_code}"
            logger.error("WhatsApp delivery failed", error=error_msg, recipient=recipient_id)
            return DeliveryResult(success=False, error=error_msg)

        except Exception as e:
            logger.error("WhatsApp delivery failed", error=str(e), recipient=recipient_id)
            return DeliveryResult(success=False, error=str(e))
