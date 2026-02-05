"""
Channel gateway base classes.

Re-exports from domain ports for backward compatibility.
Channel implementations should inherit from ChannelGateway and return DeliveryResult.
"""

from ..domain.ports.channel_gateway import (
    ChannelGateway,
    ChannelType,
    DeliveryResult,
)

__all__ = ["ChannelGateway", "ChannelType", "DeliveryResult"]
