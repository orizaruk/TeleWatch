"""Discord webhook notifier."""

import asyncio
import json
import os
import logging
import urllib.request
import urllib.error
from . import BaseNotifier, register, retry_send

logger = logging.getLogger(__name__)


def clear_terminal():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


@register
class DiscordNotifier(BaseNotifier):
    """Send notifications via Discord webhook."""

    name = "discord"

    async def send(self, message: str, chat_name: str, keywords: list, webhook_url: str = None) -> bool:
        """
        Send Discord webhook notification.

        Args:
            message: The message text
            chat_name: Name of the source chat
            keywords: List of matched keywords
            webhook_url: Discord webhook URL (from config)

        Returns:
            True if sent successfully
        """
        if not webhook_url:
            logger.error("No Discord webhook URL configured")
            return False

        success = await retry_send(
            self._send_discord_sync,
            webhook_url,
            chat_name,
            keywords,
            message,
            notifier_name="Discord"
        )

        if success:
            logger.info("Discord notification sent")
        else:
            print("Discord notification failed. Check bot.log for details.")

        return success

    def _send_discord_sync(self, webhook_url: str, chat_name: str, keywords: list, message: str) -> None:
        """Synchronous Discord webhook sending (called via executor)."""
        payload = {
            "embeds": [{
                "title": f"Job Alert [{chat_name}]",
                "description": message[:4096],  # Discord embed description limit
                "color": 5814783,  # Blue color
                "fields": [{"name": "Keywords", "value": ", ".join(keywords), "inline": True}]
            }]
        }

        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TeleWatch/1.0"
            }
        )
        urllib.request.urlopen(req, timeout=30)

    async def configure(self, client=None, existing_config: dict = None) -> dict:
        """Configure Discord webhook interactively."""
        existing_config = existing_config or {}
        clear_terminal()
        print("=== DISCORD WEBHOOK CONFIGURATION ===\n")

        current_url = existing_config.get('webhook_url')
        if current_url:
            # Show truncated URL for security
            print(f"Current webhook: ...{current_url[-30:]}")
            print()

        print("Options:")
        print("  1. Set webhook URL")
        print("  2. Disable Discord notifications")
        print("  3. Test notification")
        print("  4. Cancel")

        choice = input("\nChoice: ").strip()

        if choice == '1':
            print("\nEnter Discord webhook URL:")
            print("(Create one in Discord: Server Settings > Integrations > Webhooks)")
            webhook_url = input("> ").strip()

            if not webhook_url:
                print("No URL entered.")
                await asyncio.sleep(1)
                return None

            if not webhook_url.startswith('https://discord.com/api/webhooks/'):
                print("Warning: URL doesn't look like a Discord webhook URL")
                confirm = input("Continue anyway? (y/n): ").strip().lower()
                if confirm != 'y':
                    return None

            print(f"\nConfigured Discord webhook")
            await asyncio.sleep(1)
            return {"enabled": True, "webhook_url": webhook_url}

        elif choice == '2':
            print("Discord notifications disabled.")
            await asyncio.sleep(1)
            return {"enabled": False, "webhook_url": None}

        elif choice == '3':
            url_to_test = existing_config.get('webhook_url')
            if not url_to_test:
                url_to_test = input("Enter webhook URL to test: ").strip()
                if not url_to_test:
                    input("\nNo URL entered. Press Enter to continue...")
                    return None

            print("Sending test notification...")
            success = await self.send(
                message="This is a test message from your Telegram Job Listing Bot.",
                chat_name="Test",
                keywords=["test"],
                webhook_url=url_to_test
            )
            if success:
                print("\nTest notification sent successfully!")
            else:
                print("\nTest notification failed. Check the webhook URL.")
            input("\nPress Enter to continue...")
            return None

        elif choice == '4':
            return None

        return None

    def is_configured(self, config: dict) -> bool:
        """Check if Discord is properly configured."""
        if not config.get("enabled", False):
            return False
        return bool(config.get("webhook_url"))

    def get_display_status(self, config: dict) -> str:
        """Get display status for menu."""
        if not config.get("enabled", False):
            return "(disabled)"

        webhook_url = config.get("webhook_url")
        if not webhook_url:
            return "(no webhook URL)"

        # Show truncated URL for security
        return f"...{webhook_url[-25:]}"
