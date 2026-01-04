import asyncio
import os
import logging
import argparse
from dotenv import load_dotenv
from telethon import TelegramClient, events

from config import load_config, save_config, get_enabled_destinations
from notifiers import NOTIFIERS
from notifiers.telegram import TelegramNotifier

# LOGGING
LOG_FILE = "bot.log"
logger = None  # Initialized in __main__

def setup_logging(verbosity=0):
    """Configure logging based on verbosity level."""
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.WARNING
    else:
        level = logging.ERROR

    logging.basicConfig(
        format='[%(levelname)s %(asctime)s] %(name)s: %(message)s',
        level=level,
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

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
        destinations = config.get('destinations', {})
        notifier_list = []

        for name, notifier_cls in NOTIFIERS.items():
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
            print(f"{status_marker} {name.capitalize()}: {status}")

        print("\nOptions:")
        for i, (name, _, _, _) in enumerate(notifier_list, 1):
            print(f"  {i}) Configure {name.capitalize()}")
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

    print(f"\n=== MONITORING ACTIVE ===")
    print(f"Watching {len(config['chats'])} chat(s)")
    print(f"Keywords: {', '.join(config['keywords'])}")
    if enabled:
        print(f"Forwarding to: {', '.join(enabled)}")
    print("\nType 'q' and press Enter to stop monitoring.\n")

    stop_event = asyncio.Event()

    # Define the event handler
    @client.on(events.NewMessage(chats=config['chats']))
    async def handler(event):
        message_text = event.message.message or ""

        # Check if any keyword matches (case-insensitive)
        matched_keywords = [
            kw for kw in config['keywords']
            if kw.lower() in message_text.lower()
        ]

        if matched_keywords:
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
                    print(f"Forwarded to Telegram.")
                except Exception as e:
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
                        print(f"Sent via Email.")

    # Input listener for quit command
    async def wait_for_quit():
        loop = asyncio.get_event_loop()
        while not stop_event.is_set():
            try:
                user_input = await loop.run_in_executor(None, input)
                if user_input.strip().lower() == 'q':
                    stop_event.set()
                    break
            except EOFError:
                break

    # Start input listener task
    input_task = asyncio.create_task(wait_for_quit())

    try:
        # Wait for stop signal
        await stop_event.wait()
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        input_task.cancel()
        try:
            await input_task
        except asyncio.CancelledError:
            pass
        client.remove_event_handler(handler, events.NewMessage(chats=config['chats']))
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
    parser = argparse.ArgumentParser(description='Telegram Job Listing Monitor')
    parser.add_argument('-m', '--monitor', action='store_true',
                        help='Skip menu and start monitoring immediately')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='Increase verbosity (-v for warnings, -vv for debug)')
    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    asyncio.run(main(monitor_mode=args.monitor))
