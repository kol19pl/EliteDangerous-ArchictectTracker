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
    """Load GUI settings from the settings file.
    
    Settings are stored in:
    - Windows: %LOCALAPPDATA%\\ArchitectTracker\\settings.json
    - macOS: ~/Library/Application Support/ArchitectTracker/settings.json
    - Linux: ~/.config/ArchitectTracker/settings.json
    """
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            logger.debug(f"GUI settings loaded from {SETTINGS_FILE}")
            return settings
    except Exception as e:
        logger.error(f"Error loading GUI settings: {e}")
        return {}

def save_gui_settings(settings: dict):
    """Save GUI settings to the settings file."""
    try:
        os.makedirs(USER_DIR, exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        logger.debug(f"GUI settings saved successfully to {SETTINGS_FILE}")
    except Exception as e:
        logger.error(f"Error saving GUI settings: {e}")

# Domyślne ustawienia overlay
DEFAULT_OVERLAY_SETTINGS = {
    'color': '#003399',
    'x': 20,
    'y': 100,
    'size': 'normal'
}

# Predefiniowane kolory do wyboru w GUI
OVERLAY_COLORS = [
    ('Ciemnoniebieski', '#003399'),
    ('Pomarańczowy ED', '#ff8500'),
    ('Niebieski ED', '#1fbeff'),
    ('Biały', '#ffffff'),
    ('Czerwony', '#ff0000'),
    ('Zielony', '#00cc00'),
    ('Żółty', '#ffff00'),
    ('Jasnoniebieski', '#00ccff'),
    ('Fioletowy', '#9900ff'),
    ('Szary', '#888888'),
]

def get_overlay_settings():
    """Pobierz ustawienia overlay (kolor, pozycja, rozmiar)."""
    settings = load_gui_settings()
    overlay = settings.get('overlay', {})
    result = {}
    for key, default_val in DEFAULT_OVERLAY_SETTINGS.items():
        result[key] = overlay.get(key, default_val)
    return result

def save_overlay_settings(overlay_dict: dict):
    """Zapisz ustawienia overlay."""
    settings = load_gui_settings()
    settings['overlay'] = overlay_dict
    save_gui_settings(settings)

def get_skipped_version():
    """Get the skipped version from settings."""
    settings = load_gui_settings()
    return settings.get('skipped_version', '')

def save_skipped_version(version: str):
    """Save the skipped version to settings."""
    settings = load_gui_settings()
    settings['skipped_version'] = version
    save_gui_settings(settings)

