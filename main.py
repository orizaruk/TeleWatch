import asyncio
import os
import logging
from logging.handlers import RotatingFileHandler
import argparse
import signal
from dotenv import load_dotenv
from telethon import TelegramClient, events

from config import load_config, save_config, get_enabled_destinations
from notifiers import NOTIFIERS
from notifiers.telegram import TelegramNotifier

# LOGGING
LOG_FILE = "bot.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
LOG_BACKUP_COUNT = 3  # Keep 3 backup files (bot.log.1, bot.log.2, bot.log.3)
logger = None  # Initialized in __main__

# HEALTH MONITORING
HEALTH_FILE = "health.txt"
HEALTH_INTERVAL = 60  # seconds

# SESSION STATS (reset on each monitoring session)
stats = {
    'messages_processed': 0,
    'matches_found': 0,
    'notifications_sent': 0,
    'notifications_failed': 0,
}

def setup_logging(verbosity=0):
    """Configure logging based on verbosity level with log rotation."""
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.WARNING
    else:
        level = logging.ERROR

    log_format = '[%(levelname)s %(asctime)s] %(name)s: %(message)s'
    formatter = logging.Formatter(log_format)

    # Rotating file handler - rotates when file reaches LOG_MAX_BYTES
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=[file_handler, console_handler]
    )
    return logging.getLogger(__name__)


async def health_monitor(stop_event):
    """Write timestamp to health file periodically for external monitoring."""
    while not stop_event.is_set():
        try:
            with open(HEALTH_FILE, 'w') as f:
                from datetime import datetime
                f.write(datetime.utcnow().isoformat() + '\n')
            if logger:
                logger.debug(f"Health check written to {HEALTH_FILE}")
        except Exception as e:
            if logger:
                logger.error(f"Failed to write health file: {e}")

        # Wait for interval or stop signal
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=HEALTH_INTERVAL)
            break  # stop_event was set
        except asyncio.TimeoutError:
            pass  # Continue loop


# LOAD API_ID and API_HASH from .env
load_dotenv()
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

def clear_terminal():
    if os.name == 'nt': # Windows
        os.system('cls')
    else: # Mac and Linux, should be POSIX
        os.system('clear')

async def manage_chats(client):
    """Display and toggle chats for monitoring."""
    global config

    # Fetch all dialogs
    dialogs = []
    print("Loading your chats...")
    async for dialog in client.iter_dialogs():
        dialogs.append({
            'id': dialog.entity.id,
            'name': dialog.name,
            'entity': dialog.entity
        })

    while True:
        clear_terminal()
        print("=== CHAT MANAGEMENT ===\n")

        # Display numbered list with monitoring status
        for i, d in enumerate(dialogs, 1):
            is_monitored = d['id'] in config['chats']
            status = "[*]" if is_monitored else "[ ]"
            print(f"{i:3}. {status} {d['name']}")

        print(f"\nCurrently monitoring {len(config['chats'])} chat(s)")
        print("\nOptions:")
        print("  Enter number to toggle monitoring")
        print("  'q' to return to main menu")

        choice = input("\nChoice: ").strip().lower()

        if choice == 'q':
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(dialogs):
                chat_id = dialogs[idx]['id']
                chat_name = dialogs[idx]['name']

                if chat_id in config['chats']:
                    config['chats'].remove(chat_id)
                    print(f"Removed '{chat_name}' from monitoring")
                else:
                    config['chats'].append(chat_id)
                    print(f"Added '{chat_name}' to monitoring")

                save_config(config)
                await asyncio.sleep(0.5)
            else:
                print("Invalid number")
                await asyncio.sleep(1)
        except ValueError:
            print("Invalid input")
            await asyncio.sleep(1)

async def manage_keywords():
    """Manage keyword filters for job listings."""
    global config

    while True:
        clear_terminal()
        print("=== KEYWORD MANAGEMENT ===\n")

        # Display current keywords
        if config['keywords']:
            print("Current keywords:")
            for i, kw in enumerate(config['keywords'], 1):
                print(f"  {i}. {kw}")
        else:
            print("No keywords configured.")

        print("\nOptions:")
        print("  'a' - Add keyword")
        print("  'd' - Delete keyword")
        print("  'c' - Clear all keywords")
        print("  'q' - Return to main menu")

        choice = input("\nChoice: ").strip().lower()

        if choice == 'q':
            break

        elif choice == 'a':
            keyword = input("Enter keyword to add: ").strip()
            if keyword:
                try:
                    if keyword.lower() not in [k.lower() for k in config['keywords']]:
                        config['keywords'].append(keyword)
                        save_config(config)
                        print(f"Added keyword: '{keyword}'")
                    else:
                        print("Keyword already exists (case-insensitive)")
                except Exception as e:
                    logger.error(f"Error adding keyword '{keyword}': {e}")
                    print(f"Error adding keyword: {e}")
            else:
                print("Empty keyword not allowed")
            await asyncio.sleep(1)

        elif choice == 'd':
            if not config['keywords']:
                print("No keywords to delete")
                await asyncio.sleep(1)
                continue

            try:
                idx = int(input("Enter number to delete: ").strip()) - 1
                if 0 <= idx < len(config['keywords']):
                    removed = config['keywords'].pop(idx)
                    save_config(config)
                    print(f"Removed keyword: '{removed}'")
                else:
                    print("Invalid number")
            except ValueError:
                print("Invalid input")
            await asyncio.sleep(1)

        elif choice == 'c':
            if not config['keywords']:
                print("No keywords to clear")
            else:
                confirm = input(f"Clear all {len(config['keywords'])} keyword(s)? (y/n): ").strip().lower()
                if confirm == 'y':
                    config['keywords'].clear()
                    save_config(config)
                    print("All keywords cleared.")
                else:
                    print("Cancelled.")
            await asyncio.sleep(1)

        else:
            print("Invalid choice")
            await asyncio.sleep(1)

async def manage_destinations(client):
    """Manage forwarding destinations (Telegram, Email, etc.)."""
    global config

    while True:
        clear_terminal()
        print("=== FORWARDING DESTINATIONS ===\n")

        # Display current status for each notifier
        # Note: 'whatsapp' is hidden from UI due to Sandbox limitations (template-only messages)
        # Backend remains functional if manually enabled in config.json
        hidden_notifiers = ('whatsapp',)
        destinations = config.get('destinations', {})
        notifier_list = []

        for name, notifier_cls in NOTIFIERS.items():
            if name in hidden_notifiers:
                continue  # Skip hidden notifiers in UI

            notifier = notifier_cls()
            dest_config = destinations.get(name, {})
            enabled = dest_config.get('enabled', False)
            status_marker = "[*]" if enabled else "[ ]"

            # Get display status
            if name == 'telegram' and enabled:
                # For telegram, try to get chat name
                tg_notifier = TelegramNotifier(client)
                status = await tg_notifier.get_display_status_with_name(dest_config, client)
            else:
                status = notifier.get_display_status(dest_config)

            notifier_list.append((name, notifier_cls, status_marker, status))
            display_name = 'SMS' if name == 'sms' else name.capitalize()
            print(f"{status_marker} {display_name}: {status}")

        print("\nOptions:")
        for i, (name, _, _, _) in enumerate(notifier_list, 1):
            display_name = 'SMS' if name == 'sms' else name.capitalize()
            print(f"  {i}) Configure {display_name}")
        print("  q) Back to main menu")

        choice = input("\nChoice: ").strip().lower()

        if choice == 'q':
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(notifier_list):
                name, notifier_cls, _, _ = notifier_list[idx]
                notifier = notifier_cls()

                # Configure the notifier
                new_config = await notifier.configure(client)

                if new_config is not None:
                    # Update config
                    if 'destinations' not in config:
                        config['destinations'] = {}
                    config['destinations'][name] = new_config
                    save_config(config)
            else:
                print("Invalid number")
                await asyncio.sleep(1)
        except ValueError:
            print("Invalid input")
            await asyncio.sleep(1)

async def run_bot(client, exit_on_stop=False):
    """Run the job listing monitor."""
    global config

    # Validation
    if not config['chats']:
        print("Error: No chats selected for monitoring.")
        print("Use 'Manage Chats' to select chats first.")
        input("Press Enter to continue...")
        return

    if not config['keywords']:
        print("Error: No keywords configured.")
        print("Use 'Manage Keywords' to add keywords first.")
        input("Press Enter to continue...")
        return

    # Check enabled destinations
    enabled = get_enabled_destinations(config)
    if not enabled:
        print("Warning: No forwarding destinations enabled.")
        print("Matching messages will only be printed to console.")
        input("Press Enter to continue...")

    # Initialize notifiers
    telegram_notifier = TelegramNotifier(client)
    email_notifier = NOTIFIERS.get('email')() if 'email' in NOTIFIERS else None
    sms_notifier = NOTIFIERS.get('sms')() if 'sms' in NOTIFIERS else None
    whatsapp_notifier = NOTIFIERS.get('whatsapp')() if 'whatsapp' in NOTIFIERS else None

    # Reset session stats
    stats['messages_processed'] = 0
    stats['matches_found'] = 0
    stats['notifications_sent'] = 0
    stats['notifications_failed'] = 0

    print(f"\n=== MONITORING ACTIVE ===")
    print(f"Watching {len(config['chats'])} chat(s)")
    print(f"Keywords: {', '.join(config['keywords'])}")
    if enabled:
        print(f"Forwarding to: {', '.join(enabled)}")

    if exit_on_stop:
        # Daemon mode - signals only
        print("\nRunning in daemon mode. Send SIGTERM or SIGINT to stop.\n")
    else:
        # Interactive mode - 'q' input or signals
        print("\nType 'q' and press Enter to stop monitoring.\n")

    stop_event = asyncio.Event()

    # Define the event handler
    @client.on(events.NewMessage(chats=config['chats']))
    async def handler(event):
        message_text = event.message.message or ""
        stats['messages_processed'] += 1

        # Check if any keyword matches (case-insensitive)
        matched_keywords = [
            kw for kw in config['keywords']
            if kw.lower() in message_text.lower()
        ]

        if matched_keywords:
            stats['matches_found'] += 1
            chat = await event.get_chat()
            chat_name = getattr(chat, 'title', getattr(chat, 'first_name', 'Unknown'))

            print(f"\n--- MATCH FOUND ---")
            print(f"Chat: {chat_name}")
            print(f"Keywords: {', '.join(matched_keywords)}")
            print(f"Message: {message_text[:200]}{'...' if len(message_text) > 200 else ''}")
            print("-------------------")

            destinations = config.get('destinations', {})

            # Forward via Telegram if enabled
            tg_config = destinations.get('telegram', {})
            if tg_config.get('enabled') and tg_config.get('chat_id'):
                try:
                    await client.forward_messages(tg_config['chat_id'], event.message)
                    stats['notifications_sent'] += 1
                    print(f"Forwarded to Telegram.")
                except Exception as e:
                    stats['notifications_failed'] += 1
                    logger.error(f"Failed to forward message: {e}")
                    print(f"Failed to forward to Telegram: {e}")

            # Send via Email if enabled
            email_config = destinations.get('email', {})
            if email_config.get('enabled') and email_config.get('recipients'):
                if email_notifier:
                    success = await email_notifier.send(
                        message=message_text,
                        chat_name=chat_name,
                        keywords=matched_keywords,
                        recipients=email_config['recipients']
                    )
                    if success:
                        stats['notifications_sent'] += 1
                        print(f"Sent via Email.")
                    else:
                        stats['notifications_failed'] += 1

            # Send via SMS if enabled
            sms_config = destinations.get('sms', {})
            if sms_config.get('enabled') and sms_config.get('phone'):
                if sms_notifier:
                    success = await sms_notifier.send(
                        message=message_text,
                        chat_name=chat_name,
                        keywords=matched_keywords,
                        phone=sms_config['phone']
                    )
                    if success:
                        stats['notifications_sent'] += 1
                        print(f"Sent via SMS.")
                    else:
                        stats['notifications_failed'] += 1

            # Send via WhatsApp if enabled
            wa_config = destinations.get('whatsapp', {})
            if wa_config.get('enabled') and wa_config.get('phone'):
                if whatsapp_notifier:
                    success = await whatsapp_notifier.send(
                        message=message_text,
                        chat_name=chat_name,
                        keywords=matched_keywords,
                        phone=wa_config['phone']
                    )
                    if success:
                        stats['notifications_sent'] += 1
                        print(f"Sent via WhatsApp.")
                    else:
                        stats['notifications_failed'] += 1

    # Set up signal handlers for graceful shutdown (works in Docker)
    loop = asyncio.get_event_loop()

    def signal_handler(sig):
        signame = signal.Signals(sig).name
        logger.info(f"Received {signame}, initiating graceful shutdown...")
        print(f"\nReceived {signame}, shutting down...")
        stop_event.set()

    # Register signal handlers (Unix only, but that's where Docker runs)
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler, sig)
        signals_registered = True
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        signals_registered = False
        logger.warning("Signal handlers not supported on this platform")

    input_task = None

    # In interactive mode, also listen for 'q' input
    # In daemon mode (exit_on_stop=True), rely solely on signals
    if not exit_on_stop:
        async def wait_for_quit():
            while not stop_event.is_set():
                try:
                    user_input = await loop.run_in_executor(None, input)
                    if user_input.strip().lower() == 'q':
                        stop_event.set()
                        break
                except EOFError:
                    # No stdin available, stop listening
                    break

        input_task = asyncio.create_task(wait_for_quit())

    # Start health monitoring (writes timestamp to file periodically)
    health_task = asyncio.create_task(health_monitor(stop_event))

    try:
        # Wait for stop signal (from signal handler or 'q' input)
        await stop_event.wait()
    finally:
        # Clean up signal handlers
        if signals_registered:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(sig)

        # Cancel input task if running
        if input_task is not None:
            input_task.cancel()
            try:
                await input_task
            except asyncio.CancelledError:
                pass

        # Cancel health monitoring task
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass

        client.remove_event_handler(handler, events.NewMessage(chats=config['chats']))

        # Print session summary stats
        print("\n=== SESSION SUMMARY ===")
        print(f"Messages processed: {stats['messages_processed']}")
        print(f"Matches found: {stats['matches_found']}")
        print(f"Notifications sent: {stats['notifications_sent']}")
        if stats['notifications_failed'] > 0:
            print(f"Notifications failed: {stats['notifications_failed']}")
        print("=======================")

        # Log stats for daemon mode
        if logger:
            logger.info(
                f"Session ended - Messages: {stats['messages_processed']}, "
                f"Matches: {stats['matches_found']}, "
                f"Sent: {stats['notifications_sent']}, "
                f"Failed: {stats['notifications_failed']}"
            )

        if exit_on_stop:
            print("\nMonitoring stopped. Exiting...")
        else:
            print("\nMonitoring stopped. Returning to main menu...")
        await asyncio.sleep(1)

async def main(monitor_mode=False):

    global config
    global keywords

    config = load_config()
    keywords = config["keywords"]

    async with TelegramClient(session='sesh', api_id=API_ID, api_hash=API_HASH) as client:
        # Direct monitor mode - skip menu
        if monitor_mode:
            await run_bot(client, exit_on_stop=True)
            return

        while True:
            clear_terminal()

            # CHOOSE MODE
            print("Modes:")
            print("1) Manage Chats")
            print("2) Manage Keywords")
            print("3) Manage Destinations")
            print("4) Run Monitoring")
            print("5) Exit")
            mode = input("Choose mode (1-5): ")

            if mode == '1':
                await manage_chats(client)
            elif mode == '2':
                await manage_keywords()
            elif mode == '3':
                await manage_destinations(client)
            elif mode == '4':
                await run_bot(client)
            elif mode == '5':
                print("Exiting...")
                break
            else:
                print("Invalid choice, choose 1-5.")
                await asyncio.sleep(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TeleWatch - Telegram Keyword Monitor')
    parser.add_argument('-m', '--monitor', action='store_true',
                        help='Skip menu and start monitoring immediately')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='Increase verbosity (-v for warnings, -vv for debug)')
    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    asyncio.run(main(monitor_mode=args.monitor))
