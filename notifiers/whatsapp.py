"""WhatsApp notifier using Twilio Sandbox."""

import asyncio
import os
import logging
from . import BaseNotifier, register, retry_send

logger = logging.getLogger(__name__)


def clear_terminal():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


@register
class WhatsAppNotifier(BaseNotifier):
    """Send notifications via Twilio WhatsApp Sandbox."""

    name = "whatsapp"

    def _get_client(self):
        """Get Twilio client, importing lazily to avoid errors if not installed."""
        try:
            from twilio.rest import Client
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            if account_sid and auth_token:
                return Client(account_sid, auth_token)
        except ImportError:
            logger.error("Twilio package not installed. Run: pip install twilio")
        return None

    async def send(self, message: str, chat_name: str, keywords: list, phone: str = None) -> bool:
        """
        Send WhatsApp notification.

        Args:
            message: The message text
            chat_name: Name of the source chat
            keywords: List of matched keywords
            phone: Recipient phone number in WhatsApp format (from config)

        Returns:
            True if sent successfully
        """
        from_number = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')  # Default sandbox number

        if not phone:
            logger.error("No recipient WhatsApp number configured")
            return False

        client = self._get_client()
        if not client:
            print("WhatsApp failed: Twilio not configured. Check .env credentials.")
            return False

        # Format the WhatsApp message
        wa_body = f"*Job Alert* - {chat_name}\n"
        wa_body += f"Keywords: {', '.join(keywords)}\n\n"
        # WhatsApp allows longer messages than SMS
        remaining = 1600 - len(wa_body)
        if len(message) > remaining:
            wa_body += message[:remaining-3] + "..."
        else:
            wa_body += message

        # Ensure phone has whatsapp: prefix
        to_number = phone if phone.startswith('whatsapp:') else f'whatsapp:{phone}'
        from_number = from_number if from_number.startswith('whatsapp:') else f'whatsapp:{from_number}'

        # Use retry logic for transient failures
        success = await retry_send(
            self._send_whatsapp_sync,
            client,
            from_number,
            to_number,
            wa_body,
            notifier_name="WhatsApp"
        )

        if success:
            logger.info(f"WhatsApp sent to {phone}")
        else:
            print("WhatsApp failed. Check bot.log for details.")

        return success

    def _send_whatsapp_sync(self, client, from_number: str, to_number: str, body: str) -> None:
        """Synchronous WhatsApp sending (called via executor)."""
        client.messages.create(
            body=body,
            from_=from_number,
            to=to_number
        )

    async def configure(self, client=None) -> dict:
        """Configure WhatsApp recipient interactively."""
        clear_terminal()
        print("=== WHATSAPP CONFIGURATION ===\n")

        # Check if Twilio is installed
        try:
            import twilio
        except ImportError:
            print("ERROR: Twilio package not installed!")
            print("\nTo use WhatsApp notifications, run:")
            print("  pip install twilio")
            input("\nPress Enter to continue...")
            return None

        # Check if credentials are configured
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')

        if not account_sid or not auth_token:
            print("WARNING: Twilio credentials not configured in .env file!")
            print("\nTo use WhatsApp notifications, add to your .env file:")
            print("  TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            print("  TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            print("\nGet these from: https://console.twilio.com/")
            input("\nPress Enter to continue...")
            return None

        sandbox_number = os.getenv('TWILIO_WHATSAPP_NUMBER', '+14155238886')

        print("IMPORTANT: Twilio WhatsApp uses a Sandbox for testing.")
        print("\nBefore you can receive messages, you must opt-in:")
        print(f"  1. Go to: https://console.twilio.com/")
        print(f"  2. Navigate to: Messaging > Try it out > Send a WhatsApp message")
        print(f"  3. Send the join code from your phone to the sandbox number")
        print(f"  4. You'll receive a confirmation message")
        print(f"\nSandbox number: {sandbox_number}")
        print(f"Twilio Account: {account_sid[:10]}...")

        print("\nOptions:")
        print("  1. Set recipient WhatsApp number")
        print("  2. Disable WhatsApp notifications")
        print("  3. Test WhatsApp (send test message)")
        print("  4. Cancel")

        choice = input("\nChoice: ").strip()

        if choice == '1':
            print("\nEnter recipient phone number (with country code, e.g., +1234567890):")
            print("Note: This number must have opted into the Twilio Sandbox first!")
            phone = input("> ").strip()

            if not phone:
                print("No phone number entered.")
                await asyncio.sleep(1)
                return None

            # Basic validation
            if not phone.startswith('+'):
                print("Warning: Phone number should include country code (e.g., +1 for US)")
                confirm = input("Continue anyway? (y/n): ").strip().lower()
                if confirm != 'y':
                    return None

            print(f"\nConfigured WhatsApp to: {phone}")
            print("Remember: This number must opt-in to the Twilio Sandbox to receive messages!")
            await asyncio.sleep(2)
            return {"enabled": True, "phone": phone}

        elif choice == '2':
            print("WhatsApp notifications disabled.")
            await asyncio.sleep(1)
            return {"enabled": False, "phone": None}

        elif choice == '3':
            # Test WhatsApp functionality
            print("\nIMPORTANT: The test number must have already opted into the Sandbox!")
            phone_input = input("Enter test phone number (with country code): ").strip()
            if phone_input:
                print("Sending test WhatsApp message...")
                success = await self.send(
                    message="This is a test message from your Telegram Job Listing Bot.",
                    chat_name="Test",
                    keywords=["test"],
                    phone=phone_input
                )
                if success:
                    print("\nTest WhatsApp sent successfully!")
                else:
                    print("\nTest WhatsApp failed.")
                    print("Make sure the number has opted into the Twilio Sandbox.")
            input("\nPress Enter to continue...")
            return None

        elif choice == '4':
            return None

        return None

    def is_configured(self, config: dict) -> bool:
        """Check if WhatsApp is properly configured."""
        if not config.get("enabled", False):
            return False

        phone = config.get("phone")
        if not phone:
            return False

        # Also check if Twilio credentials exist
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        return bool(account_sid and auth_token)

    def get_display_status(self, config: dict) -> str:
        """Get display status for menu."""
        if not config.get("enabled", False):
            return "(disabled)"

        phone = config.get("phone")
        if not phone:
            return "(no phone number)"

        # Check Twilio config
        if not os.getenv('TWILIO_ACCOUNT_SID') or not os.getenv('TWILIO_AUTH_TOKEN'):
            return "(Twilio not configured in .env)"

        return phone
