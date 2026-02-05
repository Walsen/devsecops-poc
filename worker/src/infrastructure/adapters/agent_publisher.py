"""
AI Agent publisher implementation using Strands Agents SDK.

This adapter implements SocialMediaPublisher using an AI agent
that intelligently optimizes content for each platform.
"""

import structlog
from strands import Agent, tool
from strands.models import BedrockModel

from ...domain.ports import (
    SocialMediaPublisher,
    PublishRequest,
    PublishResult,
    ChannelType,
)
from .channel_gateway_factory import ChannelGatewayFactory
from ...config import settings

logger = structlog.get_logger()


# System prompt for the social media agent
SYSTEM_PROMPT = """You are a social media manager AI agent for an AWS community.
Your job is to post certification announcements across multiple social media platforms.

For each platform, you should:
1. Adapt the content to fit the platform's style and character limits
2. Use the appropriate tool to post
3. Report the results

Platform guidelines:
- Facebook: Longer posts OK (up to 500 chars), use emojis, hashtags at end, include call to action
- Instagram: Visual focus, needs image, heavy emojis, hashtags in caption, keep under 300 chars
- LinkedIn: Professional tone, formal congratulations, minimal emojis, relevant hashtags
- WhatsApp: Short and celebratory (under 200 chars), personal tone, emojis OK

Always include relevant hashtags like #AWSCertified #CloudCommunity #AWSCommunity

When posting to multiple platforms:
1. First adapt the content for each platform's style
2. Post to each requested channel
3. Summarize the results at the end
"""


def _create_tools():
    """
    Create tool functions that use the channel gateways.
    
    Tools are created as closures to maintain clean separation
    while still accessing the gateway factory.
    """
    
    @tool
    async def post_to_facebook(content: str, media_url: str | None = None) -> dict:
        """
        Post content to the Facebook Page.
        
        Best for longer announcements with images. Supports hashtags and emojis.
        
        Args:
            content: The post content/caption to publish
            media_url: Optional URL to an image to include in the post
        
        Returns:
            Dictionary with success status and post_id or error message
        """
        logger.info("Agent posting to Facebook", content_length=len(content))
        gateway = ChannelGatewayFactory.get_gateway(ChannelType.FACEBOOK)
        result = await gateway.send(recipient_id="", content=content, media_url=media_url)
        return {
            "success": result.success,
            "post_id": result.external_id,
            "error": result.error,
            "platform": "facebook",
        }

    @tool
    async def post_to_instagram(content: str, media_url: str) -> dict:
        """
        Post content to Instagram.
        
        Requires an image. Good for visual announcements with emojis and hashtags.
        
        Args:
            content: The caption for the Instagram post
            media_url: URL to the image (required for Instagram)
        
        Returns:
            Dictionary with success status and post_id or error message
        """
        logger.info("Agent posting to Instagram", content_length=len(content))
        gateway = ChannelGatewayFactory.get_gateway(ChannelType.INSTAGRAM)
        result = await gateway.send(recipient_id="", content=content, media_url=media_url)
        return {
            "success": result.success,
            "post_id": result.external_id,
            "error": result.error,
            "platform": "instagram",
        }

    @tool
    async def post_to_linkedin(content: str, media_url: str | None = None) -> dict:
        """
        Post content to LinkedIn Company Page.
        
        Best for professional announcements. Use formal tone and relevant hashtags.
        
        Args:
            content: The post content for LinkedIn
            media_url: Optional URL to an image to include
        
        Returns:
            Dictionary with success status and post_id or error message
        """
        logger.info("Agent posting to LinkedIn", content_length=len(content))
        gateway = ChannelGatewayFactory.get_gateway(ChannelType.LINKEDIN)
        result = await gateway.send(recipient_id="", content=content, media_url=media_url)
        return {
            "success": result.success,
            "post_id": result.external_id,
            "error": result.error,
            "platform": "linkedin",
        }

    @tool
    async def send_whatsapp(content: str) -> dict:
        """
        Send a message to the WhatsApp community group.
        
        Best for quick, celebratory notifications. Keep messages short and personal.
        
        Args:
            content: The message content to send
        
        Returns:
            Dictionary with success status and message_id or error message
        """
        logger.info("Agent sending WhatsApp", content_length=len(content))
        gateway = ChannelGatewayFactory.get_gateway(ChannelType.WHATSAPP)
        result = await gateway.send(
            recipient_id=settings.whatsapp_community_id,
            content=content,
        )
        return {
            "success": result.success,
            "message_id": result.external_id,
            "error": result.error,
            "platform": "whatsapp",
        }

    return [post_to_facebook, post_to_instagram, post_to_linkedin, send_whatsapp]


class AgentPublisher(SocialMediaPublisher):
    """
    AI Agent implementation of SocialMediaPublisher using Strands SDK.
    
    Uses Claude on Amazon Bedrock to intelligently adapt content
    for each platform before posting.
    """

    def __init__(self) -> None:
        """Initialize the Strands agent with Bedrock model and tools."""
        self._model = BedrockModel(
            model_id=settings.bedrock_model_id,
            region_name=settings.aws_region,
        )
        self._tools = _create_tools()
        self._agent = Agent(
            model=self._model,
            system_prompt=SYSTEM_PROMPT,
            tools=self._tools,
        )

    async def publish(self, request: PublishRequest) -> PublishResult:
        """
        Publish content using the AI agent.
        
        The agent will:
        1. Analyze the content and target channels
        2. Optimize content for each platform
        3. Post to each channel using tools
        4. Return results with summary
        
        Args:
            request: PublishRequest with content and channels
            
        Returns:
            PublishResult with per-channel results and agent summary
        """
        # Build the user prompt
        channel_names = [c.value for c in request.channels]
        prompt_parts = [
            f"Please post the following announcement to these channels: {', '.join(channel_names)}",
            f"\nContent: {request.content}",
        ]

        if request.media_url:
            prompt_parts.append(f"Media URL: {request.media_url}")
        else:
            prompt_parts.append("No image provided (skip Instagram if no image)")

        if request.metadata:
            if "certification_type" in request.metadata:
                prompt_parts.append(f"Certification: {request.metadata['certification_type']}")
            if "member_name" in request.metadata:
                prompt_parts.append(f"Member: {request.metadata['member_name']}")

        prompt_parts.append("\nPost to each requested channel, adapting the content appropriately.")
        user_prompt = "\n".join(prompt_parts)

        logger.info(
            "Starting agent publisher",
            channels=channel_names,
            has_media=bool(request.media_url),
        )

        # Run the agent
        result = self._agent(user_prompt)

        # Extract results
        channel_results: dict[ChannelType, dict] = {}
        summary = ""

        # Get the final text response
        if result.message and "content" in result.message:
            for content_block in result.message["content"]:
                if "text" in content_block:
                    summary = content_block["text"]
                    break

        # Extract metrics and tool results
        metrics = {}
        if hasattr(result, "metrics"):
            metrics = result.metrics.get_summary() if hasattr(result.metrics, "get_summary") else {}
            
            # Parse tool usage to get channel results
            if hasattr(result.metrics, "tool_usage"):
                for tool_name, tool_data in result.metrics.tool_usage.items():
                    platform = tool_name.replace("post_to_", "").replace("send_", "")
                    try:
                        channel_type = ChannelType(platform)
                        channel_results[channel_type] = {
                            "success": tool_data.get("execution_stats", {}).get("success_rate", 0) == 1.0,
                            "call_count": tool_data.get("execution_stats", {}).get("call_count", 0),
                        }
                    except ValueError:
                        pass  # Not a channel tool

        logger.info(
            "Agent publisher completed",
            channels_posted=list(channel_results.keys()),
        )

        return PublishResult(
            channel_results=channel_results,
            summary=summary,
            metrics=metrics,
        )
