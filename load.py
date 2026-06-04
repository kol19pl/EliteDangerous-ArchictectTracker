"""
Architect Tracker - EDMC Plugin
================================
This is the main entry point for the EDMC plugin system.
All plugin hooks are delegated to the plugin_hooks module.
"""

import os
import logging
from contextlib import suppress

from settings import USER_DIR

# Configure logging early
LOG_FILE = os.path.join(USER_DIR, "EDMC_Architect_Log.txt")
with suppress(Exception):
    os.remove(LOG_FILE)

logger = logging.getLogger("ArchitectTracker")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(file_handler)

logger.info("Architect Tracker plugin loading...")

# Import all plugin hooks from the refactored module
from plugin_hooks import (
    plugin_start3,
    plugin_app,
    plugin_stop,
    journal_entry,
    capi_fleetcarrier,
)

logger.info("Architect Tracker plugin loaded successfully")

# Wywołaj overlay welcome message jeśli moduł dostępny
try:
    import overlay
except Exception as e:
    logger.exception("Failed to import overlay module: %s", e)
else:
    try:
        ok = overlay.send_witaj()
        if not ok:
            logger.warning("overlay.send_witaj() returned False")
    except Exception as e:
        logger.exception("overlay.send_witaj() raised: %s", e)

logger.info("Architect Tracker setup complete")