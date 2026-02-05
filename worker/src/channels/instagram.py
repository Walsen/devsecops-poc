import httpx
import structlog

from .base import ChannelGateway, DeliveryResult

logger = structlog.get_logger()


class InstagramGateway(ChannelGateway):
    """Instagram Graph API gateway for content publishing."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, access_token: str, instagram_account_id: str) -> None:
        self._access_token = access_token
        self._account_id = instagram_account_id

    async def send(
        self,
        recipient_id: str,  # Not used for posts
        content: str,
        media_url: str | None = None,
    ) -> DeliveryResult:
        """Publish to Instagram (requires media_url for posts)."""
        if not media_url:
            return DeliveryResult(
                success=False,
                error="Instagram posts require a media URL",
            )

        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Create media container
                container_url = f"{self.BASE_URL}/{self._account_id}/media"
                container_payload = {
                    "image_url": media_url,
                    "caption": content,
                    "access_token": self._access_token,
                }
                
                response = await client.post(container_url, data=container_payload)
                response.raise_for_status()
                container_id = response.json().get("id")

                # Step 2: Publish the container
                publish_url = f"{self.BASE_URL}/{self._account_id}/media_publish"
                publish_payload = {
                    "creation_id": container_id,
                    "access_token": self._access_token,
                }
                
                response = await client.post(publish_url, data=publish_payload)
                response.raise_for_status()
                post_id = response.json().get("id")
                
                logger.info("Instagram post published", post_id=post_id)
                return DeliveryResult(success=True, external_id=post_id)

        except httpx.HTTPStatusError as e:
            error_msg = f"Instagram API error: {e.response.status_code}"
            logger.error("Instagram delivery failed", error=error_msg)
            return DeliveryResult(success=False, error=error_msg)

        except Exception as e:
            logger.error("Instagram delivery failed", error=str(e))
            return DeliveryResult(success=False, error=str(e))
