import asyncio
import os
import logging
import json
import argparse
from dotenv import load_dotenv
from telethon import TelegramClient, events

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

# CONFIG FOR PERSISTENT STORAGE
CONFIG_FILE = "config.json"

def clear_terminal():
    if os.name == 'nt': # Windows
        os.system('cls') 
    else: # Mac and Linux, should be POSIX
        os.system('clear')
    
def load_config():
    """Load monitored chats and keywords from config.json."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            # Ensure all keys exist (backward compatibility)
            if 'chats' not in data:
                data['chats'] = []
            if 'keywords' not in data:
                data['keywords'] = []
            if 'destination' not in data:
                data['destination'] = None
            return data
    except FileNotFoundError:
        return {"chats": [], "keywords": [], "destination": None}
    except json.JSONDecodeError:
        print("Error: config.json is corrupted. Starting with empty config.")
        return {"chats": [], "keywords": [], "destination": None}

# SAVE CONFIG, CONFIG IS A DICT with chats and keywords keys and arrays as values
def save_config(config):
    """Save monitored chats and keywords to config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        logger.error(f"Error saving config: {e}")
        print(f"Error saving config: {e}")

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

async def manage_destination(client):
    """Configure the forwarding destination for matched messages."""
    global config

    clear_terminal()
    print("=== FORWARDING DESTINATION ===\n")

    current = config.get('destination')
    if current:
        try:
            entity = await client.get_entity(current)
            name = getattr(entity, 'title', getattr(entity, 'first_name', 'Unknown'))
            print(f"Current destination: {name} (ID: {current})")
        except:
            print(f"Current destination ID: {current} (unable to resolve name)")
    else:
        print("No destination configured.")

    print("\nOptions:")
    print("  1. Select from your chats")
    print("  2. Enter chat username/ID manually")
    print("  3. Clear destination")
    print("  4. Return to main menu")

    choice = input("\nChoice: ").strip()

    if choice == '1':
        dialogs = []
        print("\nLoading chats...")
        async for dialog in client.iter_dialogs():
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
                config['destination'] = dialogs[idx]['id']
                save_config(config)
                print(f"Destination set to: {dialogs[idx]['name']}")
            else:
                print("Invalid number")
        except ValueError:
            print("Invalid input")
        await asyncio.sleep(1)

    elif choice == '2':
        identifier = input("Enter username (with @) or chat ID: ").strip()
        if identifier:
            try:
                entity = await client.get_entity(identifier)
                config['destination'] = entity.id
                save_config(config)
                name = getattr(entity, 'title', getattr(entity, 'first_name', 'Unknown'))
                print(f"Destination set to: {name}")
            except Exception as e:
                print(f"Could not find chat: {e}")
        else:
            print("Empty input")
        await asyncio.sleep(1)

    elif choice == '3':
        config['destination'] = None
        save_config(config)
        print("Destination cleared.")
        await asyncio.sleep(1)

    elif choice == '4':
        return
    else:
        print("Invalid choice")
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

    # Get destination chat if configured
    destination = config.get('destination')
    if not destination:
        print("Warning: No forwarding destination set.")
        print("Matching messages will only be printed to console.")
        input("Press Enter to continue...")

    print(f"\n=== MONITORING ACTIVE ===")
    print(f"Watching {len(config['chats'])} chat(s)")
    print(f"Keywords: {', '.join(config['keywords'])}")
    if destination:
        print(f"Forwarding to destination ID: {destination}")
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

            # Forward to destination if configured
            if destination:
                try:
                    await client.forward_messages(destination, event.message)
                    print(f"Forwarded to destination.")
                except Exception as e:
                    logger.error(f"Failed to forward message: {e}")
                    print(f"Failed to forward: {e}")

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
            print("3) Set Forwarding Destination")
            print("4) Run Monitoring")
            print("5) Exit")
            mode = input("Choose mode (1-5): ")

            if mode == '1':
                await manage_chats(client)
            elif mode == '2':
                await manage_keywords()
            elif mode == '3':
                await manage_destination(client)
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
        
