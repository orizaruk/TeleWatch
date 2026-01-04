"""Notifier base class and registry."""

from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

# Registry of all notifier classes
NOTIFIERS = {}


def register(cls):
    """Decorator to register a notifier class."""
    NOTIFIERS[cls.name] = cls
    return cls


class BaseNotifier(ABC):
    """Base class for all notification channels."""

    name: str = ""  # Override in subclasses

    @abstractmethod
    async def send(self, message: str, chat_name: str, keywords: list) -> bool:
        """
        Send a notification.

        Args:
            message: The full message text
            chat_name: Name of the source chat
            keywords: List of matched keywords

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def configure(self, client=None) -> dict:
        """
        Interactive CLI configuration.

        Args:
            client: TelegramClient instance (needed for Telegram notifier)

        Returns:
            Configuration dict for this notifier
        """
        pass

    @abstractmethod
    def is_configured(self, config: dict) -> bool:
        """
        Check if this notifier has valid configuration.

        Args:
            config: The notifier's config section (e.g., {"enabled": True, "recipients": [...]})

        Returns:
            True if configuration is complete and valid
        """
        pass

    def get_display_status(self, config: dict) -> str:
        """
        Get human-readable status for menu display.

        Args:
            config: The notifier's config section

        Returns:
            Status string like "user@example.com" or "(not configured)"
        """
        return "(not configured)"


# Import notifiers to register them
from . import telegram
from . import email
