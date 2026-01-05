"""SMS notifier using Twilio."""

import asyncio
import os
import logging
from . import BaseNotifier, register

logger = logging.getLogger(__name__)


def clear_terminal():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


@register
class SMSNotifier(BaseNotifier):
    """Send notifications via Twilio SMS."""

    name = "sms"

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
        Send SMS notification.

        Args:
            message: The message text
            chat_name: Name of the source chat
            keywords: List of matched keywords
            phone: Recipient phone number (from config)

        Returns:
            True if sent successfully
        """
        from_number = os.getenv('TWILIO_PHONE_NUMBER')

        if not from_number:
            logger.error("TWILIO_PHONE_NUMBER not configured in .env")
            print("SMS not configured: Missing TWILIO_PHONE_NUMBER in .env")
            return False

        if not phone:
            logger.error("No recipient phone number configured")
            return False

        client = self._get_client()
        if not client:
            print("SMS failed: Twilio not configured. Check .env credentials.")
            return False

        # Format the SMS (keep it concise - SMS has 160 char limit per segment)
        sms_body = f"Job Alert [{chat_name}]\n"
        sms_body += f"Keywords: {', '.join(keywords)}\n\n"
        # Truncate message to fit SMS reasonably
        remaining = 400 - len(sms_body)  # Allow ~3 segments
        if len(message) > remaining:
            sms_body += message[:remaining-3] + "..."
        else:
            sms_body += message

        try:
            # Run Twilio API call in executor to not block async loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_sms_sync,
                client,
                from_number,
                phone,
                sms_body
            )
            logger.info(f"SMS sent to {phone}")
            return True

        except Exception as e:
            logger.error(f"Failed to send SMS: {type(e).__name__}: {e}")
            print(f"SMS failed: {e}")
            return False

    def _send_sms_sync(self, client, from_number: str, to_number: str, body: str) -> None:
        """Synchronous SMS sending (called via executor)."""
        client.messages.create(
            body=body,
            from_=from_number,
            to=to_number
        )

    async def configure(self, client=None) -> dict:
        """Configure SMS recipient interactively."""
        clear_terminal()
        print("=== SMS CONFIGURATION ===\n")

        # Check if Twilio is installed
        try:
            import twilio
        except ImportError:
            print("ERROR: Twilio package not installed!")
            print("\nTo use SMS notifications, run:")
            print("  pip install twilio")
            input("\nPress Enter to continue...")
            return None

        # Check if credentials are configured
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_PHONE_NUMBER')

        if not account_sid or not auth_token or not from_number:
            print("WARNING: Twilio credentials not configured in .env file!")
            print("\nTo use SMS notifications, add to your .env file:")
            print("  TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            print("  TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            print("  TWILIO_PHONE_NUMBER=+1234567890")
            print("\nGet these from: https://console.twilio.com/")
            print("\nNote: You'll need to:")
            print("  1. Create a Twilio account (free trial available)")
            print("  2. Get a phone number (~$1/month)")
            print("  3. For US numbers, register for A2P 10DLC messaging")
            input("\nPress Enter to continue...")
            return None

        print(f"Twilio Account: {account_sid[:10]}...")
        print(f"From Number: {from_number}")
        print("\nOptions:")
        print("  1. Set recipient phone number")
        print("  2. Disable SMS notifications")
        print("  3. Test SMS (send test message)")
        print("  4. Cancel")

        choice = input("\nChoice: ").strip()

        if choice == '1':
            print("\nEnter recipient phone number (with country code, e.g., +1234567890):")
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

            print(f"\nConfigured SMS to: {phone}")
            await asyncio.sleep(1)
            return {"enabled": True, "phone": phone}

        elif choice == '2':
            print("SMS notifications disabled.")
            await asyncio.sleep(1)
            return {"enabled": False, "phone": None}

        elif choice == '3':
            # Test SMS functionality
            phone_input = input("Enter test phone number (with country code): ").strip()
            if phone_input:
                print("Sending test SMS...")
                success = await self.send(
                    message="This is a test message from your Telegram Job Listing Bot.",
                    chat_name="Test",
                    keywords=["test"],
                    phone=phone_input
                )
                if success:
                    print("\nTest SMS sent successfully!")
                else:
                    print("\nTest SMS failed. Check your Twilio configuration.")
            input("\nPress Enter to continue...")
            return None

        elif choice == '4':
            return None

        return None

    def is_configured(self, config: dict) -> bool:
        """Check if SMS is properly configured."""
        if not config.get("enabled", False):
            return False

        phone = config.get("phone")
        if not phone:
            return False

        # Also check if Twilio credentials exist
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_PHONE_NUMBER')
        return bool(account_sid and auth_token and from_number)

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

        if not os.getenv('TWILIO_PHONE_NUMBER'):
            return "(missing TWILIO_PHONE_NUMBER)"

        return phone
