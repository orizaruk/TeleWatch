"""Telegram forwarding notifier."""

import asyncio
import logging
from . import BaseNotifier, register

logger = logging.getLogger(__name__)


def clear_terminal():
    import os
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


@register
class TelegramNotifier(BaseNotifier):
    """Forward messages to a Telegram chat."""

    name = "telegram"

    def __init__(self, client=None):
        self.client = client

    async def send(self, message: str, chat_name: str, keywords: list, event=None) -> bool:
        """
        Forward message to Telegram destination.

        Note: For Telegram, we forward the original message rather than sending text,
        so we need the event object.
        """
        if not self.client or not event:
            logger.error("TelegramNotifier requires client and event")
            return False

        try:
            # Get destination from config - this is passed in via the send call
            # The actual forwarding happens in main.py since it has access to config
            return True
        except Exception as e:
            logger.error(f"Failed to forward message: {e}")
            return False

    async def forward_message(self, destination_id: int, event) -> bool:
        """Forward the original Telegram message to destination."""
        if not self.client:
            return False

        try:
            await self.client.forward_messages(destination_id, event.message)
            return True
        except Exception as e:
            logger.error(f"Failed to forward message: {e}")
            print(f"Failed to forward: {e}")
            return False

    async def configure(self, client=None, existing_config: dict = None) -> dict:
        """Configure Telegram destination interactively."""
        if client:
            self.client = client

        if not self.client:
            print("Error: Telegram client not available")
            return {"enabled": False, "chat_id": None}

        clear_terminal()
        print("=== TELEGRAM DESTINATION ===\n")
        print("Options:")
        print("  1. Select from your chats")
        print("  2. Enter chat username/ID manually")
        print("  3. Disable Telegram forwarding")
        print("  4. Cancel")

        choice = input("\nChoice: ").strip()

        if choice == '1':
            dialogs = []
            print("\nLoading chats...")
            async for dialog in self.client.iter_dialogs():
                dialogs.append({
                    'id': dialog.entity.id,
                    'name': dialog.name
                })

            clear_terminal()
            print("Select a chat as forwarding destination:\n")
            for i, d in enumerate(dialogs, 1):
                print(f"{i:3}. {d['name']}")

            try:
                idx = int(input("\nEnter number: ").strip()) - 1
                if 0 <= idx < len(dialogs):
                    print(f"Destination set to: {dialogs[idx]['name']}")
                    await asyncio.sleep(1)
                    return {"enabled": True, "chat_id": dialogs[idx]['id']}
                else:
                    print("Invalid number")
            except ValueError:
                print("Invalid input")
            await asyncio.sleep(1)
            return None  # Signal no change

        elif choice == '2':
            identifier = input("Enter username (with @) or chat ID: ").strip()
            if identifier:
                try:
                    entity = await self.client.get_entity(identifier)
                    name = getattr(entity, 'title', getattr(entity, 'first_name', 'Unknown'))
                    print(f"Destination set to: {name}")
                    await asyncio.sleep(1)
                    return {"enabled": True, "chat_id": entity.id}
                except Exception as e:
                    print(f"Could not find chat: {e}")
            else:
                print("Empty input")
            await asyncio.sleep(1)
            return None

        elif choice == '3':
            print("Telegram forwarding disabled.")
            await asyncio.sleep(1)
            return {"enabled": False, "chat_id": None}

        elif choice == '4':
            return None

        return None

    def is_configured(self, config: dict) -> bool:
        """Check if Telegram destination is configured."""
        return config.get("enabled", False) and config.get("chat_id") is not None

    def get_display_status(self, config: dict) -> str:
        """Get display status for menu."""
        if not config.get("enabled", False):
            return "(disabled)"
        chat_id = config.get("chat_id")
        if chat_id:
            return f"Chat ID: {chat_id}"
        return "(not configured)"

    async def get_display_status_with_name(self, config: dict, client=None) -> str:
        """Get display status with resolved chat name."""
        if not config.get("enabled", False):
            return "(disabled)"

        chat_id = config.get("chat_id")
        if not chat_id:
            return "(not configured)"

        if client:
            try:
                entity = await client.get_entity(chat_id)
                name = getattr(entity, 'title', getattr(entity, 'first_name', 'Unknown'))
                return f"{name} (ID: {chat_id})"
            except:
                pass

        return f"Chat ID: {chat_id}"
