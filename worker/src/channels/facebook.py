import httpx
import structlog

from .base import ChannelGateway, ChannelType, DeliveryResult

logger = structlog.get_logger()


class FacebookGateway(ChannelGateway):
    """Facebook Graph API gateway for Page posts."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, access_token: str, page_id: str) -> None:
        self._access_token = access_token
        self._page_id = page_id

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.FACEBOOK

    async def send(
        self,
        recipient_id: str,  # Not used for page posts
        content: str,
        media_url: str | None = None,
    ) -> DeliveryResult:
        """Post to Facebook Page."""
        url = f"{self.BASE_URL}/{self._page_id}/feed"
        
        payload = {
            "message": content,
            "access_token": self._access_token,
        }
        
        if media_url:
            # For photo posts, use /photos endpoint
            url = f"{self.BASE_URL}/{self._page_id}/photos"
            payload["url"] = media_url
            payload["caption"] = content
            del payload["message"]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=payload)
                response.raise_for_status()
                data = response.json()
                
                post_id = data.get("id") or data.get("post_id")
                logger.info("Facebook post created", post_id=post_id)
                
                return DeliveryResult(success=True, external_id=post_id)

        except httpx.HTTPStatusError as e:
            error_msg = f"Facebook API error: {e.response.status_code}"
            logger.error("Facebook delivery failed", error=error_msg)
            return DeliveryResult(success=False, error=error_msg)

        except Exception as e:
            logger.error("Facebook delivery failed", error=str(e))
            return DeliveryResult(success=False, error=str(e))
