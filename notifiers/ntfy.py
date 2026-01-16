"""ntfy.sh push notification notifier."""

import asyncio
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
class NtfyNotifier(BaseNotifier):
    """Send notifications via ntfy.sh push notifications."""

    name = "ntfy"

    async def send(self, message: str, chat_name: str, keywords: list, topic: str = None) -> bool:
        """
        Send ntfy.sh notification.

        Args:
            message: The message text
            chat_name: Name of the source chat
            keywords: List of matched keywords
            topic: ntfy.sh topic (from config)

        Returns:
            True if sent successfully
        """
        if not topic:
            logger.error("No ntfy.sh topic configured")
            return False

        title = f"Job Alert [{chat_name}]"
        body = f"Keywords: {', '.join(keywords)}\n\n{message}"

        success = await retry_send(
            self._send_ntfy_sync,
            topic,
            title,
            body,
            notifier_name="ntfy"
        )

        if success:
            logger.info(f"ntfy notification sent to topic {topic}")
        else:
            print("ntfy notification failed. Check bot.log for details.")

        return success

    def _send_ntfy_sync(self, topic: str, title: str, body: str) -> None:
        """Synchronous ntfy.sh sending (called via executor)."""
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}",
            data=body.encode('utf-8'),
            headers={"Title": title}
        )
        urllib.request.urlopen(req, timeout=30)

    async def configure(self, client=None, existing_config: dict = None) -> dict:
        """Configure ntfy.sh topic interactively."""
        existing_config = existing_config or {}
        clear_terminal()
        print("=== NTFY.SH CONFIGURATION ===\n")

        current_topic = existing_config.get('topic')
        if current_topic:
            print(f"Current topic: {current_topic}")
            print(f"URL: https://ntfy.sh/{current_topic}\n")

        print("Options:")
        print("  1. Set ntfy.sh topic")
        print("  2. Disable ntfy notifications")
        print("  3. Test notification")
        print("  4. Cancel")

        choice = input("\nChoice: ").strip()

        if choice == '1':
            print("\nEnter ntfy.sh topic (just the topic name, not the full URL):")
            print("Example: If your URL is ntfy.sh/mytopic, enter 'mytopic'")
            topic = input("> ").strip()

            if not topic:
                print("No topic entered.")
                await asyncio.sleep(1)
                return None

            # Remove URL prefix if user accidentally included it
            if topic.startswith('https://ntfy.sh/'):
                topic = topic[16:]
            elif topic.startswith('ntfy.sh/'):
                topic = topic[8:]

            print(f"\nConfigured ntfy.sh topic: {topic}")
            print(f"URL: https://ntfy.sh/{topic}")
            await asyncio.sleep(1)
            return {"enabled": True, "topic": topic}

        elif choice == '2':
            print("ntfy notifications disabled.")
            await asyncio.sleep(1)
            return {"enabled": False, "topic": None}

        elif choice == '3':
            topic_to_test = existing_config.get('topic')
            if not topic_to_test:
                topic_to_test = input("Enter topic to test: ").strip()
                if not topic_to_test:
                    input("\nNo topic entered. Press Enter to continue...")
                    return None

            print(f"Sending test notification to {topic_to_test}...")
            success = await self.send(
                message="This is a test message from your Telegram Job Listing Bot.",
                chat_name="Test",
                keywords=["test"],
                topic=topic_to_test
            )
            if success:
                print("\nTest notification sent successfully!")
            else:
                print("\nTest notification failed. Check the topic name.")
            input("\nPress Enter to continue...")
            return None

        elif choice == '4':
            return None

        return None

    def is_configured(self, config: dict) -> bool:
        """Check if ntfy is properly configured."""
        if not config.get("enabled", False):
            return False
        return bool(config.get("topic"))

    def get_display_status(self, config: dict) -> str:
        """Get display status for menu."""
        if not config.get("enabled", False):
            return "(disabled)"

        topic = config.get("topic")
        if not topic:
            return "(no topic set)"

        return f"ntfy.sh/{topic}"
