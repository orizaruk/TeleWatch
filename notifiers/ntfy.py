"""ntfy.sh push notification notifier."""

import asyncio
import json
import os
import logging
import urllib.request
import urllib.error
from . import BaseNotifier, register, retry_send
from .links import extract_web_links, pick_click_url

logger = logging.getLogger(__name__)


def format_telegram_links(message: str, telegram_message=None) -> tuple[str, str | None]:
    """Expose embedded web links and choose a destination for notification taps."""
    links = extract_web_links(telegram_message)
    if not links:
        return message, None

    click_url = pick_click_url(links)
    visible_urls = {url for _, url, embedded in links if not embedded}
    extra_lines = []
    for label, url, embedded in links:
        if embedded and url not in visible_urls:
            extra_lines.append(f"{label.strip() or 'Link'}: {url}")
            visible_urls.add(url)
    if extra_lines:
        message += '\n\nLinks:\n' + '\n'.join(extra_lines)
    return message, click_url


def clear_terminal():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


@register
class NtfyNotifier(BaseNotifier):
    """Send notifications via ntfy.sh push notifications."""

    name = "ntfy"

    async def send(
        self, message: str, chat_name: str, keywords: list,
        topic: str = None, telegram_message=None,
    ) -> bool:
        """
        Send ntfy.sh notification.

        Args:
            message: The message text
            chat_name: Name of the source chat
            keywords: List of matched keywords
            topic: ntfy.sh topic (from config)
            telegram_message: Original Telegram message, including link entities

        Returns:
            True if sent successfully
        """
        if not topic:
            logger.error("No ntfy.sh topic configured")
            return False

        title = f"Job Alert [{chat_name}]"
        message, click_url = format_telegram_links(message, telegram_message)
        body = f"Keywords: {', '.join(keywords)}\n\n{message}"

        success = await retry_send(
            self._send_ntfy_sync,
            topic,
            title,
            body,
            click_url=click_url,
            notifier_name="ntfy"
        )

        if success:
            logger.info(f"ntfy notification sent to topic {topic}")
        else:
            print("ntfy notification failed. Check bot.log for details.")

        return success

    def _send_ntfy_sync(
        self, topic: str, title: str, body: str, click_url: str = None,
    ) -> None:
        """Synchronous ntfy.sh sending (called via executor)."""
        payload = {"topic": topic, "title": title, "message": body}
        if click_url:
            payload["click"] = click_url
        # JSON preserves Unicode in chat names and URLs without HTTP header encoding.
        req = urllib.request.Request(
            "https://ntfy.sh/",
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            response.read()

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
