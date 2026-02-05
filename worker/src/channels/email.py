import structlog
from aiobotocore.session import get_session

from .base import ChannelGateway, ChannelType, DeliveryResult

logger = structlog.get_logger()


class EmailGateway(ChannelGateway):
    """AWS SES email gateway."""

    def __init__(self, sender_email: str, region: str = "us-east-1") -> None:
        self._sender_email = sender_email
        self._region = region
        self._session = get_session()

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.EMAIL

    async def send(
        self,
        recipient_id: str,  # Email address
        content: str,
        media_url: str | None = None,
    ) -> DeliveryResult:
        """Send an email via SES."""
        # Build HTML body with optional media
        html_body = f"<p>{content}</p>"
        if media_url:
            html_body += f'<p><img src="{media_url}" alt="Attached media" /></p>'

        try:
            async with self._session.create_client("ses", region_name=self._region) as client:
                response = await client.send_email(
                    Source=self._sender_email,
                    Destination={"ToAddresses": [recipient_id]},
                    Message={
                        "Subject": {"Data": "New Message", "Charset": "UTF-8"},
                        "Body": {
                            "Html": {"Data": html_body, "Charset": "UTF-8"},
                            "Text": {"Data": content, "Charset": "UTF-8"},
                        },
                    },
                )
                
                message_id = response.get("MessageId")
                logger.info("Email sent", message_id=message_id, recipient=recipient_id)
                
                return DeliveryResult(success=True, external_id=message_id)

        except Exception as e:
            logger.error("Email delivery failed", error=str(e), recipient=recipient_id)
            return DeliveryResult(success=False, error=str(e))
