"""Email notifier using Gmail SMTP."""

import asyncio
import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from . import BaseNotifier, register

logger = logging.getLogger(__name__)


def clear_terminal():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


@register
class EmailNotifier(BaseNotifier):
    """Send notifications via Gmail SMTP."""

    name = "email"

    async def send(self, message: str, chat_name: str, keywords: list, recipients: list = None) -> bool:
        """
        Send email notification.

        Args:
            message: The message text
            chat_name: Name of the source chat
            keywords: List of matched keywords
            recipients: List of email addresses (from config)

        Returns:
            True if sent successfully
        """
        email_addr = os.getenv('EMAIL_ADDRESS')
        email_pass = os.getenv('EMAIL_APP_PASSWORD')

        if not email_addr or not email_pass:
            logger.error("Email credentials not configured in .env")
            print("Email not configured: Missing EMAIL_ADDRESS or EMAIL_APP_PASSWORD in .env")
            return False

        if not recipients:
            logger.error("No email recipients configured")
            return False

        # Format the email
        subject = f"Job Alert: {', '.join(keywords)} in {chat_name}"

        # Create a nicely formatted body
        body = f"""Job Listing Alert

Source: {chat_name}
Matched Keywords: {', '.join(keywords)}

Message:
{'-' * 40}
{message}
{'-' * 40}

This alert was sent by your Telegram Job Listing Bot.
"""

        try:
            # Run SMTP in executor to not block async loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_email_sync,
                email_addr,
                email_pass,
                recipients,
                subject,
                body
            )
            logger.info(f"Email sent to {len(recipients)} recipient(s)")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("Email authentication failed. Check EMAIL_APP_PASSWORD.")
            print("Email auth failed: Check your App Password in .env")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            print(f"Email failed: {e}")
            return False

    def _send_email_sync(self, sender: str, password: str, recipients: list,
                         subject: str, body: str) -> None:
        """Synchronous email sending (called via executor)."""
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)

    async def configure(self, client=None) -> dict:
        """Configure email recipients interactively."""
        clear_terminal()
        print("=== EMAIL CONFIGURATION ===\n")

        # Check if sender credentials are configured
        email_addr = os.getenv('EMAIL_ADDRESS')
        email_pass = os.getenv('EMAIL_APP_PASSWORD')

        if not email_addr or not email_pass:
            print("WARNING: Sender email not configured in .env file!")
            print("\nTo use email notifications, add to your .env file:")
            print("  EMAIL_ADDRESS=your@gmail.com")
            print("  EMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx")
            print("\nTo get an App Password:")
            print("  1. Enable 2FA on your Google account")
            print("  2. Go to: https://myaccount.google.com/apppasswords")
            print("  3. Generate a new App Password for 'Mail'")
            print("\nSee PLAN-email-notifications.md for details.")
            input("\nPress Enter to continue...")
            return None

        print(f"Sender email: {email_addr}")
        print("\nOptions:")
        print("  1. Add/replace recipients")
        print("  2. Disable email notifications")
        print("  3. Test email (send test message)")
        print("  4. Cancel")

        choice = input("\nChoice: ").strip()

        if choice == '1':
            print("\nEnter recipient email addresses (comma-separated):")
            print("Tip: Use carrier gateways for SMS, e.g., 5551234567@txt.att.net")
            raw = input("> ").strip()

            if not raw:
                print("No recipients entered.")
                await asyncio.sleep(1)
                return None

            # Parse and clean recipients
            recipients = [r.strip() for r in raw.split(',') if r.strip()]

            if not recipients:
                print("No valid recipients.")
                await asyncio.sleep(1)
                return None

            print(f"\nConfigured {len(recipients)} recipient(s):")
            for r in recipients:
                print(f"  - {r}")

            await asyncio.sleep(1)
            return {"enabled": True, "recipients": recipients}

        elif choice == '2':
            print("Email notifications disabled.")
            await asyncio.sleep(1)
            return {"enabled": False, "recipients": []}

        elif choice == '3':
            # Test email functionality
            recipients_input = input("Enter test recipient email: ").strip()
            if recipients_input:
                print("Sending test email...")
                success = await self.send(
                    message="This is a test message from your Telegram Job Listing Bot.",
                    chat_name="Test",
                    keywords=["test"],
                    recipients=[recipients_input]
                )
                if success:
                    print("Test email sent successfully!")
                else:
                    print("Test email failed. Check your .env configuration.")
            await asyncio.sleep(2)
            return None

        elif choice == '4':
            return None

        return None

    def is_configured(self, config: dict) -> bool:
        """Check if email is properly configured."""
        if not config.get("enabled", False):
            return False

        recipients = config.get("recipients", [])
        if not recipients:
            return False

        # Also check if sender credentials exist
        email_addr = os.getenv('EMAIL_ADDRESS')
        email_pass = os.getenv('EMAIL_APP_PASSWORD')
        return bool(email_addr and email_pass)

    def get_display_status(self, config: dict) -> str:
        """Get display status for menu."""
        if not config.get("enabled", False):
            return "(disabled)"

        recipients = config.get("recipients", [])
        if not recipients:
            return "(no recipients)"

        # Check sender config
        if not os.getenv('EMAIL_ADDRESS') or not os.getenv('EMAIL_APP_PASSWORD'):
            return "(sender not configured in .env)"

        if len(recipients) == 1:
            return recipients[0]
        return f"{len(recipients)} recipients"
