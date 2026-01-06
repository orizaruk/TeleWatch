"""Notifier base class and registry."""

from abc import ABC, abstractmethod
import asyncio
import logging

logger = logging.getLogger(__name__)

# Default retry settings
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds


def is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an exception is worth retrying.

    Returns False for permanent failures (auth errors, invalid config).
    Returns True for transient failures (network, rate limits).
    """
    import smtplib

    # SMTP auth errors - permanent, don't retry
    if isinstance(exception, smtplib.SMTPAuthenticationError):
        return False

    # Check for Twilio-specific errors
    error_str = str(exception).lower()
    error_code = getattr(exception, 'code', None)

    # Twilio auth/config errors (don't retry)
    if error_code in (20003, 20008):  # Auth failure, invalid credentials
        return False
    if 'authenticate' in error_str or 'invalid credentials' in error_str:
        return False
    if 'unverified' in error_str:  # Unverified number
        return False

    # Network/transient errors (retry)
    if isinstance(exception, (ConnectionError, TimeoutError, OSError)):
        return True
    if 'timeout' in error_str or 'connection' in error_str:
        return True
    if error_code == 429 or 'rate limit' in error_str:  # Rate limited
        return True

    # Default: retry for unknown errors (might be transient)
    return True


async def retry_send(
    func,
    *args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    notifier_name: str = "notifier",
    **kwargs
) -> bool:
    """
    Execute a sync function with retry logic and exponential backoff.

    Args:
        func: Synchronous function to execute
        *args: Arguments to pass to func
        max_retries: Maximum number of attempts (default 3)
        base_delay: Initial delay between retries in seconds (default 1.0)
        notifier_name: Name for logging purposes
        **kwargs: Keyword arguments to pass to func

    Returns:
        True if successful, False if all retries exhausted
    """
    loop = asyncio.get_event_loop()
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            await loop.run_in_executor(None, lambda: func(*args, **kwargs))
            if attempt > 1:
                logger.info(f"{notifier_name}: Succeeded on attempt {attempt}")
            return True

        except Exception as e:
            last_exception = e

            if not is_retryable_error(e):
                logger.error(f"{notifier_name}: Non-retryable error: {type(e).__name__}: {e}")
                return False

            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff
                logger.warning(
                    f"{notifier_name}: Attempt {attempt}/{max_retries} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"{notifier_name}: All {max_retries} attempts failed. "
                    f"Last error: {type(last_exception).__name__}: {last_exception}"
                )

    return False

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
    async def configure(self, client=None, existing_config: dict = None) -> dict:
        """
        Interactive CLI configuration.

        Args:
            client: TelegramClient instance (needed for Telegram notifier)
            existing_config: Current configuration for this notifier (for test features)

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
from . import sms
from . import whatsapp
