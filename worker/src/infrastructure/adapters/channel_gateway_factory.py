"""
Factory for creating channel gateway instances.

This factory creates the appropriate gateway implementation based on channel type.
It encapsulates the creation logic and configuration.
"""

from ...domain.ports import ChannelGateway, ChannelType
from ...channels import (
    FacebookGateway,
    InstagramGateway,
    LinkedInGateway,
    WhatsAppGateway,
    EmailGateway,
    SmsGateway,
)
from ...config import settings


class ChannelGatewayFactory:
    """
    Factory for creating channel gateway instances.
    
    Encapsulates the creation and configuration of channel gateways.
    Uses lazy initialization to avoid creating unused gateways.
    """

    _instances: dict[ChannelType, ChannelGateway] = {}

    @classmethod
    def get_gateway(cls, channel_type: ChannelType) -> ChannelGateway:
        """
        Get or create a gateway for the specified channel type.
        
        Args:
            channel_type: The channel type to get a gateway for
            
        Returns:
            ChannelGateway implementation for the channel
            
        Raises:
            ValueError: If channel type is not supported
        """
        if channel_type not in cls._instances:
            cls._instances[channel_type] = cls._create_gateway(channel_type)
        return cls._instances[channel_type]

    @classmethod
    def _create_gateway(cls, channel_type: ChannelType) -> ChannelGateway:
        """Create a new gateway instance for the channel type."""
        match channel_type:
            case ChannelType.FACEBOOK:
                return FacebookGateway(
                    access_token=settings.meta_access_token,
                    page_id=settings.meta_page_id,
                )
            case ChannelType.INSTAGRAM:
                return InstagramGateway(
                    access_token=settings.meta_access_token,
                    instagram_account_id=settings.meta_instagram_account_id,
                )
            case ChannelType.LINKEDIN:
                return LinkedInGateway(
                    access_token=settings.linkedin_access_token,
                    organization_id=settings.linkedin_organization_id,
                )
            case ChannelType.WHATSAPP:
                return WhatsAppGateway(
                    access_token=settings.meta_access_token,
                    phone_number_id=settings.meta_phone_number_id,
                )
            case ChannelType.EMAIL:
                return EmailGateway(
                    sender_email=settings.ses_sender_email,
                    region=settings.aws_region,
                )
            case ChannelType.SMS:
                return SmsGateway(
                    sender_id=settings.sns_sender_id,
                    region=settings.aws_region,
                )
            case _:
                raise ValueError(f"Unsupported channel type: {channel_type}")

    @classmethod
    def get_all_gateways(cls) -> dict[ChannelType, ChannelGateway]:
        """Get gateways for all supported channel types."""
        for channel_type in ChannelType:
            try:
                cls.get_gateway(channel_type)
            except ValueError:
                pass  # Skip unsupported channels
        return cls._instances.copy()

    @classmethod
    def reset(cls) -> None:
        """Reset all cached gateway instances (useful for testing)."""
        cls._instances.clear()
