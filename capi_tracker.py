"""Fleet Carrier Cargo Tracker module - handles CAPI data and auto-refresh logic."""
import json
import os
import logging
import binascii
from settings import USER_DIR

# Configure logger
logger = logging.getLogger("ArchitectTracker")

# File paths
CARRIER_FILE = os.path.join(USER_DIR, "fleet_carrier_cargo.json")


def decode_vanity_name(hex_string):
    """Decode a hex-encoded vanity name."""
    try:
        return binascii.unhexlify(hex_string).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to decode vanity name: {e}")
        return hex_string


class FleetCarrierCargoTracker:
    """Tracks fleet carrier cargo data from CAPI."""

    def __init__(self):
        self.commodities = {}
        self.carrier_name = ""
        self.callsign = ""
        self.load()

    def update(self, data):
        """Update cargo data from CAPI response."""
        cargo_items = data.get('cargo', [])
        if not isinstance(cargo_items, list):
            logger.warning("Unexpected cargo data format.")
            return
        self.commodities.clear()
        for item in cargo_items:
            name = item.get("commodity")
            qty = item.get("qty", 0)
            if not name:
                logger.warning("Missing commodity name in cargo item: %s", item)
                continue
            self.commodities[name] = self.commodities.get(name, 0) + qty

        carrier_info = data.get("name", {})
        hex_name = carrier_info.get("vanityName")
        self.carrier_name = decode_vanity_name(hex_name) if hex_name else "Unnamed Carrier"
        self.callsign = carrier_info.get("callsign", "")
        self.save()

    def apply_transfer_event(self, transfers):
        """Apply cargo transfer events to tracked quantities."""
        for transfer in transfers:
            name = transfer.get("Type").capitalize()
            qty = transfer.get("Count", 0)
            direction = transfer.get("Direction")
            if not name or qty <= 0 or direction not in ("tocarrier", "toship"):
                continue
            current = self.commodities.get(name, 0)
            if direction == "tocarrier":
                self.commodities[name] = current + qty
            else:
                self.commodities[name] = max(0, current - qty)
        self.save()

    def get_quantity(self, commodity_name):
        """Get the quantity of a specific commodity on the carrier."""
        return self.commodities.get(commodity_name.capitalize(), 0)

    def save(self):
        """Save carrier cargo data to file."""
        try:
            with open(CARRIER_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "carrier_name": self.carrier_name,
                    "callsign": self.callsign,
                    "commodities": self.commodities
                }, f, indent=4)
        except Exception as e:
            logger.error("Error saving fleet carrier cargo: %s", e)

    def load(self):
        """Load carrier cargo data from file."""
        if not os.path.exists(CARRIER_FILE):
            return
        try:
            with open(CARRIER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.carrier_name = data.get("carrier_name", "")
                self.callsign = data.get("callsign", "")
                self.commodities = data.get("commodities", {})
        except Exception as e:
            logger.error("Error loading fleet carrier cargo: %s", e)


class CapiAutoRefresh:
    """Manages automatic CAPI refresh timer for the main GUI."""
    
    def __init__(self, refresh_callback, save_settings_callback):
        """
        Args:
            refresh_callback: Callable to refresh the GUI display
            save_settings_callback: Callable to save settings after interval change
        """
        self.refresh_callback = refresh_callback
        self.save_settings_callback = save_settings_callback
        self.refresh_interval = 60  # default 60 minutes
        self._timer_id = None
        self._after_func = None  # Reference to tkinter's after function
        self._after_cancel_func = None  # Reference to tkinter's after_cancel function

    def set_tk_after_funcs(self, after_func, after_cancel_func):
        """Set the tkinter after/after_cancel function references."""
        self._after_func = after_func
        self._after_cancel_func = after_cancel_func

    def set_interval(self, minutes):
        """Set the refresh interval in minutes."""
        if minutes < 0:
            minutes = 0
        self.refresh_interval = minutes
        self.restart()

    def get_interval(self):
        """Get the current refresh interval in minutes."""
        return self.refresh_interval

    def start(self):
        """Start the periodic refresh timer."""
        self.stop()
        if self.refresh_interval > 0 and self._after_func:
            interval_ms = self.refresh_interval * 60 * 1000
            self._timer_id = self._after_func(interval_ms, self._do_refresh)
            logger.info(f"CAPI auto-refresh started: every {self.refresh_interval} minutes")

    def stop(self):
        """Stop the refresh timer."""
        if self._timer_id is not None and self._after_cancel_func:
            try:
                self._after_cancel_func(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

    def restart(self):
        """Restart the timer (stop + start)."""
        self.start()

    def _do_refresh(self):
        """Perform the refresh and reschedule."""
        try:
            logger.info("CAPI auto-refresh: refreshing display")
            if self.refresh_callback:
                self.refresh_callback()
        except Exception as e:
            logger.error(f"CAPI auto-refresh error: {e}")
        finally:
            self.start()

    def force_refresh(self):
        """Force an immediate refresh and restart the timer."""
        logger.info("Manual CAPI refresh triggered")
        if self.refresh_callback:
            self.refresh_callback()
        self.start()