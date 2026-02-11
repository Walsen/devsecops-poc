import httpx
import structlog

from .base import ChannelGateway, ChannelType, DeliveryResult

logger = structlog.get_logger()


class LinkedInGateway(ChannelGateway):
    """LinkedIn API gateway for Company Page posts."""

    BASE_URL = "https://api.linkedin.com/v2"

    def __init__(self, access_token: str, organization_id: str) -> None:
        self._access_token = access_token
        self._organization_id = organization_id

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.LINKEDIN

    async def send(
        self,
        recipient_id: str,  # Not used for page posts
        content: str,
        media_url: str | None = None,
    ) -> DeliveryResult:
        """Post to LinkedIn Company Page."""
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # Build the share content
        share_content = {
            "author": f"urn:li:organization:{self._organization_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        # If media URL provided, include it as an article
        if media_url:
            share_content["specificContent"]["com.linkedin.ugc.ShareContent"].update(
                {
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "originalUrl": media_url,
                        }
                    ],
                }
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/ugcPosts",
                    headers=headers,
                    json=share_content,
                )
                response.raise_for_status()
                data = response.json()

                post_id = data.get("id")
                logger.info("LinkedIn post created", post_id=post_id)

                return DeliveryResult(success=True, external_id=post_id)

        except httpx.HTTPStatusError as e:
            error_msg = f"LinkedIn API error: {e.response.status_code}"
            logger.error("LinkedIn delivery failed", error=error_msg)
            return DeliveryResult(success=False, error=error_msg)

        except Exception as e:
            logger.error("LinkedIn delivery failed", error=str(e))
            return DeliveryResult(success=False, error=str(e))
