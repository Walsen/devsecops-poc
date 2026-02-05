from enum import Enum


class ChannelType(str, Enum):
    """Supported delivery channels."""
    WHATSAPP = "whatsapp"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    EMAIL = "email"
    SMS = "sms"
