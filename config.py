"""Configuration management with schema migration support."""

import json
import logging

CONFIG_FILE = "config.json"
logger = logging.getLogger(__name__)

# Default config structure
DEFAULT_CONFIG = {
    "chats": [],
    "keywords": [],
    "destinations": {
        "telegram": {"enabled": False, "chat_id": None},
        "email": {"enabled": False, "recipients": []},
        "sms": {"enabled": False, "phone": None},
        "whatsapp": {"enabled": False, "phone": None}
    }
}


def _migrate_config(data: dict) -> dict:
    """Migrate old config format to new destinations-based format."""
    # Check if already migrated
    if "destinations" in data:
        # Ensure all destination types exist
        for key, default in DEFAULT_CONFIG["destinations"].items():
            if key not in data["destinations"]:
                data["destinations"][key] = default.copy()
        return data

    # Migrate from old format
    migrated = {
        "chats": data.get("chats", []),
        "keywords": data.get("keywords", []),
        "destinations": {
            "telegram": {
                "enabled": data.get("destination") is not None,
                "chat_id": data.get("destination")
            },
            "email": {"enabled": False, "recipients": []}
        }
    }

    logger.info("Migrated config from old format to new destinations format")
    return migrated


def load_config() -> dict:
    """Load config from file, migrating if necessary."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            migrated = _migrate_config(data)
            # Save if migration occurred
            if migrated != data:
                save_config(migrated)
            return migrated
    except FileNotFoundError:
        return DEFAULT_CONFIG.copy()
    except json.JSONDecodeError:
        print("Error: config.json is corrupted. Starting with empty config.")
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Save config to file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        logger.error(f"Error saving config: {e}")
        print(f"Error saving config: {e}")


def get_enabled_destinations(config: dict) -> list:
    """Return list of enabled destination names."""
    return [
        name for name, dest in config.get("destinations", {}).items()
        if dest.get("enabled", False)
    ]
