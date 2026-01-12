"""Configuration management with schema migration support."""

import json
import logging
import os

CONFIG_FILE = "config.json"
logger = logging.getLogger(__name__)

# Environment variable names for Docker/CI configuration
ENV_CHATS = "TELEWATCH_CHATS"           # Comma-separated chat IDs
ENV_KEYWORDS = "TELEWATCH_KEYWORDS"     # Comma-separated keywords
ENV_EXCLUDED_KEYWORDS = "TELEWATCH_EXCLUDED_KEYWORDS"  # Comma-separated excluded keywords
ENV_DESTINATIONS = "TELEWATCH_DESTINATIONS"  # JSON string

# Default config structure
DEFAULT_CONFIG = {
    "chats": [],
    "keywords": [],
    "excluded_keywords": [],
    "destinations": {
        "telegram": {"enabled": False, "chat_id": None},
        "email": {"enabled": False, "recipients": []},
        "sms": {"enabled": False, "phone": None},
        "whatsapp": {"enabled": False, "phone": None}
    }
}


def _load_env_overrides() -> dict:
    """Load configuration overrides from environment variables.

    Environment variables:
        TELEWATCH_CHATS: Comma-separated chat IDs (e.g., "123456789,-987654321")
        TELEWATCH_KEYWORDS: Comma-separated keywords (e.g., "python,remote,developer")
        TELEWATCH_DESTINATIONS: JSON string with destinations config

    Returns:
        Dict with any overrides found (empty if none set)
    """
    overrides = {}

    # Parse TELEWATCH_CHATS (comma-separated integers)
    chats_env = os.getenv(ENV_CHATS)
    if chats_env:
        try:
            chats = [int(c.strip()) for c in chats_env.split(",") if c.strip()]
            overrides["chats"] = chats
            if logger:
                logger.info(f"Loaded {len(chats)} chat(s) from {ENV_CHATS}")
        except ValueError as e:
            if logger:
                logger.error(f"Invalid {ENV_CHATS} format (expected comma-separated integers): {e}")

    # Parse TELEWATCH_KEYWORDS (comma-separated strings)
    keywords_env = os.getenv(ENV_KEYWORDS)
    if keywords_env:
        keywords = [k.strip() for k in keywords_env.split(",") if k.strip()]
        overrides["keywords"] = keywords
        if logger:
            logger.info(f"Loaded {len(keywords)} keyword(s) from {ENV_KEYWORDS}")

    # Parse TELEWATCH_EXCLUDED_KEYWORDS (comma-separated strings)
    excluded_env = os.getenv(ENV_EXCLUDED_KEYWORDS)
    if excluded_env:
        excluded = [k.strip() for k in excluded_env.split(",") if k.strip()]
        overrides["excluded_keywords"] = excluded
        if logger:
            logger.info(f"Loaded {len(excluded)} excluded keyword(s) from {ENV_EXCLUDED_KEYWORDS}")

    # Parse TELEWATCH_DESTINATIONS (JSON string)
    destinations_env = os.getenv(ENV_DESTINATIONS)
    if destinations_env:
        try:
            destinations = json.loads(destinations_env)
            if isinstance(destinations, dict):
                overrides["destinations"] = destinations
                if logger:
                    logger.info(f"Loaded destinations config from {ENV_DESTINATIONS}")
            else:
                if logger:
                    logger.error(f"Invalid {ENV_DESTINATIONS} format (expected JSON object)")
        except json.JSONDecodeError as e:
            if logger:
                logger.error(f"Invalid {ENV_DESTINATIONS} JSON: {e}")

    return overrides


def _migrate_config(data: dict) -> dict:
    """Migrate old config format to new destinations-based format."""
    # Check if already migrated
    if "destinations" in data:
        # Ensure all destination types exist
        for key, default in DEFAULT_CONFIG["destinations"].items():
            if key not in data["destinations"]:
                data["destinations"][key] = default.copy()
        # Ensure excluded_keywords exists (migration for older configs)
        if "excluded_keywords" not in data:
            data["excluded_keywords"] = []
        return data

    # Migrate from old format
    migrated = {
        "chats": data.get("chats", []),
        "keywords": data.get("keywords", []),
        "excluded_keywords": data.get("excluded_keywords", []),
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
    """Load config from file, then apply any environment variable overrides.

    Priority (highest to lowest):
        1. Environment variables (TELEWATCH_CHATS, TELEWATCH_KEYWORDS, TELEWATCH_DESTINATIONS)
        2. config.json file
        3. Default config
    """
    # Load from file
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            config = _migrate_config(data)
            # Save if migration occurred
            if config != data:
                save_config(config)
    except FileNotFoundError:
        config = DEFAULT_CONFIG.copy()
    except json.JSONDecodeError:
        print("Error: config.json is corrupted. Starting with empty config.")
        config = DEFAULT_CONFIG.copy()

    # Apply environment variable overrides
    env_overrides = _load_env_overrides()
    if env_overrides:
        for key, value in env_overrides.items():
            if key == "destinations" and "destinations" in config:
                # Merge destinations rather than replace entirely
                for dest_name, dest_config in value.items():
                    if dest_name in config["destinations"]:
                        config["destinations"][dest_name].update(dest_config)
                    else:
                        config["destinations"][dest_name] = dest_config
            else:
                config[key] = value

    return config


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
