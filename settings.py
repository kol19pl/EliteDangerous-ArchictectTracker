import json
import os
import logging
import platform
from contextlib import suppress

# Configure user directories
if platform.system() == "Windows":
    USER_DIR = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")), "ArchitectTracker")
elif platform.system() == "Darwin":
    USER_DIR = os.path.join(os.path.expanduser("~/Library/Application Support"), "ArchitectTracker")
else:
    USER_DIR = os.path.join(os.path.expanduser("~/.config"), "ArchitectTracker")

os.makedirs(USER_DIR, exist_ok=True)

# Settings file path
SETTINGS_FILE = os.path.join(USER_DIR, "settings.json")

# Configure logger
logger = logging.getLogger("ArchitectTracker")

def load_gui_settings():
    """Load GUI settings from the settings file."""
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading GUI settings: {e}")
        return {}

def save_gui_settings(settings: dict):
    """Save GUI settings to the settings file."""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving GUI settings: {e}")

def get_skipped_version():
    """Get the skipped version from settings."""
    settings = load_gui_settings()
    return settings.get('skipped_version', '')

def save_skipped_version(version: str):
    """Save the skipped version to settings."""
    settings = load_gui_settings()
    settings['skipped_version'] = version
    save_gui_settings(settings)

