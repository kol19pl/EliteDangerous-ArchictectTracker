import os
import sys
import math
import json
from random import choices
from string import ascii_uppercase, digits
import re
import logging

from settings import get_overlay_settings


def _safe_plugin_root():
    try:
        return plugin_root()
    except Exception:
        return os.path.dirname(__file__)


if sys.platform == "win32":
    _overlay_dir = os.path.join(_safe_plugin_root(), 'EDMCOverlay')
    if _overlay_dir not in sys.path:
        sys.path.append(_overlay_dir)

try:
    from EDMCOverlay import edmcoverlay
except ImportError:
    try:
        from .EDMCOverlay import edmcoverlay
    except ImportError:
        edmcoverlay = None


def send_witaj():
    """Wyślij prostą wiadomość 'Witaj!' przy użyciu EDMCModernOverlay (legacy edmcoverlay API)."""
    logger = logging.getLogger(__name__)
    if not edmcoverlay:
        logger.debug("EDMC overlay module not available; skipping 'Witaj' message")
        return False

    try:
        overlay = edmcoverlay.Overlay()
    except Exception as e:
        logger.exception("Could not create edmcoverlay.Overlay(): %s", e)
        return False

    try:
        overlay.send_message(
            msgid="archictect-witaj",
            text="Witaj!",
            color="white",
            x=20,
            y=20,
            ttl=5,
            size="normal",
        )
        logger.info("Sent 'Witaj' overlay message")
        return True
    except Exception:
        # Fallback: spróbuj send_raw
        try:
            overlay.send_raw({
                "id": "archictect-witaj",
                "text": "Witaj!",
                "color": "white",
                "x": 20,
                "y": 20,
                "ttl": 20,
            })
            logger.info("Sent 'Witaj' overlay message via send_raw")
            return True
        except Exception as e:
            logger.exception("Failed to send 'Witaj' overlay message: %s", e)
            return False


def send_shortage_overlay(station_name, available_items, unavailable_items, msgid=None, ttl=15, ship_items=None):
    """
    Wyślij overlay z listą brakujących materiałów do dostarczenia na stacji.
    Ustawienia koloru, pozycji i rozmiaru czcionki są odczytywane z settings.json.
    
    Args:
        ship_items: opcjonalny słownik {nazwa: ilość} z materiałami w ładowni statku
    """
    logger = logging.getLogger(__name__)
    
    if not edmcoverlay:
        logger.debug("EDMC overlay module not available; skipping shortage overlay")
        return False
    
    try:
        overlay = edmcoverlay.Overlay()
    except Exception as e:
        logger.exception("Could not create edmcoverlay.Overlay(): %s", e)
        return False
    
    # Wczytaj ustawienia overlay z pliku
    ov_settings = get_overlay_settings()
    ov_color = ov_settings.get('color', '#003399')
    ov_x = ov_settings.get('x', 20)
    ov_y = ov_settings.get('y', 100)
    ov_size = ov_settings.get('size', 'normal')

    # available_items / unavailable_items are dicts {mat_key: info}
    # Build display lists
    def _format_list(items):
        lines = []
        for mat_key, mat_info in items.items():
            name = mat_info.get('Name_Localised', mat_key.replace('$', '').replace('_name;', ''))
            shortfall = int(mat_info.get('shortfall', 0))
            lines.append(f"{name}: {shortfall}t")
        return lines

    avail_lines = _format_list(available_items or {})
    unavail_lines = _format_list(unavailable_items or {})

    if not avail_lines and not unavail_lines and not ship_items:
        logger.debug("No shortages and no ship cargo to show for station %s", station_name)
        return False

    # Title - try to emphasize (uppercase and surrounded by **)
    title = f"**{station_name.upper()}**"

    # Compose body: available first, then separator, then unavailable
    body_lines = []
    if avail_lines:
        body_lines.extend(avail_lines)

    # Separator required by user
    if unavail_lines:
        separator = "/////No///on///THIS///////////////"
        body_lines.append(separator)
        body_lines.extend(unavail_lines)

    # Sekcja ship: materiały w ładowni statku
    if ship_items:
        ship_separator = "///on///ship///"
        body_lines.append(ship_separator)
        for name, qty in sorted(ship_items.items(), key=lambda x: x[0]):
            body_lines.append(f"{name}: {qty}t")

    body_text = "\n".join(body_lines)
    full_text = f"{title}\n{body_text}"
    logger.debug(f"Shortage overlay text: {full_text}")
    
    try:
        overlay.send_message(
            msgid=(msgid or "archictect-shortage"),
            text=full_text,
            color=ov_color,
            x=ov_x,
            y=ov_y,
            ttl=ttl,
            size=ov_size,
        )
        total_items = len(avail_lines) + len(unavail_lines)
        logger.info("Sent shortage overlay for station: %s (%d items)", station_name, total_items)
        return True
    except Exception:
        # Fallback: spróbuj send_raw
        try:
            overlay.send_raw({
                "id": (msgid or "archictect-shortage"),
                "text": full_text,
                "color": ov_color,
                "x": ov_x,
                "y": ov_y,
                "ttl": ttl,
            })
            total_items = len(avail_lines) + len(unavail_lines)
            logger.info("Sent shortage overlay via send_raw for station: %s (%d items)", station_name, total_items)
            return True
        except Exception as e:
            logger.exception("Failed to send shortage overlay: %s", e)
            return False


def clear_overlay(msgid="archictect-shortage"):
    """Clear/remove an overlay message by sending a very short-lived empty message with same id.

    Some EDMC overlay backends don't provide a remove API; sending an empty message with
    small ttl is a pragmatic way to replace/clear the visible overlay.
    """
    logger = logging.getLogger(__name__)
    if not edmcoverlay:
        logger.debug("EDMC overlay module not available; cannot clear overlay")
        return False

    try:
        ov = edmcoverlay.Overlay()
    except Exception as e:
        logger.exception("Could not create edmcoverlay.Overlay() to clear overlay: %s", e)
        return False

    try:
        ov.send_message(msgid=msgid, text="", color="white", x=0, y=0, ttl=1, size="normal")
        logger.info("Cleared overlay with id: %s", msgid)
        return True
    except Exception:
        try:
            ov.send_raw({"id": msgid, "text": "", "ttl": 1})
            logger.info("Cleared overlay via send_raw for id: %s", msgid)
            return True
        except Exception as e:
            logger.exception("Failed to clear overlay: %s", e)
            return False


def send_error_overlay(message, msgid=None, ttl=8):
    """
    Wyświetla komunikat błędu/ostrzeżenia w overlay'u.
    Ustawienia koloru, pozycji i rozmiaru czcionki są odczytywane z settings.json.
    """
    logger = logging.getLogger(__name__)
    if not edmcoverlay:
        logger.debug("EDMC overlay module not available; skipping error overlay")
        return False

    try:
        overlay = edmcoverlay.Overlay()
    except Exception as e:
        logger.exception("Could not create edmcoverlay.Overlay(): %s", e)
        return False

    # Wczytaj ustawienia overlay z pliku (błędy też używają tych samych ustawień)
    ov_settings = get_overlay_settings()
    ov_color = ov_settings.get('color', '#003399')
    ov_x = ov_settings.get('x', 20)
    ov_y = ov_settings.get('y', 20)
    ov_size = ov_settings.get('size', 'normal')

    try:
        overlay.send_message(
            msgid=(msgid or "archictect-error"),
            text=message,
            color=ov_color,
            x=ov_x,
            y=ov_y,
            ttl=ttl,
            size=ov_size,
        )
        logger.info("Sent error overlay: %s", message)
        return True
    except Exception:
        # Fallback: spróbuj send_raw
        try:
            overlay.send_raw({
                "id": (msgid or "archictect-error"),
                "text": message,
                "color": ov_color,
                "x": ov_x,
                "y": ov_y,
                "ttl": ttl,
            })
            logger.info("Sent error overlay via send_raw: %s", message)
            return True
        except Exception as e:
            logger.exception("Failed to send error overlay: %s", e)
            return False


# Funkcja `send_witaj()` jest wywoływana z `load.py` po załadowaniu pluginu.
# Funkcja `send_shortage_overlay()` jest wywoływana z `plugin_hooks.py` w event Docked.
# Funkcja `send_error_overlay()` wyświetla błędy, np. gdy GUI jest zamknięte lub brak wybranej stacji.



