import structlog
from aiobotocore.session import get_session

from .base import ChannelGateway, DeliveryResult

logger = structlog.get_logger()


class SmsGateway(ChannelGateway):
    """AWS SNS SMS gateway."""

    def __init__(self, sender_id: str = "", region: str = "us-east-1") -> None:
        self._sender_id = sender_id
        self._region = region
        self._session = get_session()

    async def send(
        self,
        recipient_id: str,  # Phone number in E.164 format
        content: str,
        media_url: str | None = None,  # Not supported for SMS
    ) -> DeliveryResult:
        """Send an SMS via SNS."""
        if media_url:
            content += f"\n\nMedia: {media_url}"

        try:
            async with self._session.create_client("sns", region_name=self._region) as client:
                params = {
                    "PhoneNumber": recipient_id,
                    "Message": content,
                }
                
                if self._sender_id:
                    params["MessageAttributes"] = {
                        "AWS.SNS.SMS.SenderID": {
                            "DataType": "String",
                            "StringValue": self._sender_id,
                        }
                    }
                
                response = await client.publish(**params)
                message_id = response.get("MessageId")
                
                logger.info("SMS sent", message_id=message_id, recipient=recipient_id)
                return DeliveryResult(success=True, external_id=message_id)

        except Exception as e:
            logger.error("SMS delivery failed", error=str(e), recipient=recipient_id)
            return DeliveryResult(success=False, error=str(e))
