"""
Telethon Handlers Package
=========================
Event handlers for the Telethon user client.
"""

from telethon_client.handlers.message_handler import TelethonMessageHandler
from telethon_client.handlers.channel_handler import TelethonChannelHandler
from telethon_client.handlers.private_handler import TelethonPrivateHandler

__all__ = [
    "TelethonMessageHandler",
    "TelethonChannelHandler",
    "TelethonPrivateHandler",
]
