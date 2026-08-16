"""Plugin hooks module - EDMC plugin entry points."""
import os
import logging
import tkinter as tk
from tkinter import messagebox
from companion import CAPIData
from typing import Optional
import threading
import time

from settings import USER_DIR, load_gui_settings, save_gui_settings, get_skipped_version, save_skipped_version
from gui_main import ArchitectTrackerGUI, carrier_tracker, ARCHITECT_GUI as GUI_INSTANCE
from data_manager import SAVE_FILE, load_facility_requirements, save_facility_requirements as save_req
import updater

# Configure logger (should already be configured in load.py stub)
logger = logging.getLogger("ArchitectTracker")

# Global references (set from plugin_app / plugin_start3)
ARCHITECT_GUI: Optional[ArchitectTrackerGUI] = None
PLUGIN_PARENT = None
frame: Optional[tk.Frame] = None
# Overlay persistence control
overlay_resend_thread = None
overlay_resend_stop_event = None
overlay_resend_msgid = None
overlay_active = False  # Flaga: czy overlay już został uruchomiony

# Import overlay for shortage notifications (after logger configured)
try:
    import overlay
except Exception as e:
    logger.warning(f"Failed to import overlay module: {e}")
    overlay = None


def show_gui():
    """Show the main Architect Tracker window."""
    global ARCHITECT_GUI, PLUGIN_PARENT
    if not ARCHITECT_GUI or not ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI = ArchitectTrackerGUI(PLUGIN_PARENT)
        ARCHITECT_GUI.after(30000, check_for_updates_at_startup)
    else:
        ARCHITECT_GUI.lift()
        ARCHITECT_GUI.focus_force()
        ARCHITECT_GUI.setStyle()
        ARCHITECT_GUI.refresh()


def check_for_updates_at_startup():
    """Check for updates at startup and show notification if newer version is available."""
    global ARCHITECT_GUI
    
    if not ARCHITECT_GUI or not ARCHITECT_GUI.winfo_exists():
        logger.warning("Cannot check for updates: GUI not initialized")
        return
    
    logger.info("Checking for updates at startup")
    
    def _check_worker():
        try:
            success, result = updater.get_available_releases()
            if not success:
                logger.warning(f"Failed to check for updates: {result}")
                return
            if not result:
                logger.info("No releases found when checking for updates")
                return
            
            current_version = updater.get_current_version()
            latest_release = result[0]
            latest_version = latest_release.get('version')
            skipped_version = get_skipped_version()
            
            if (updater.is_newer_version(current_version, latest_version) and 
                latest_version != skipped_version):
                logger.info(f"New version available: {latest_version} (current: {current_version})")
                ARCHITECT_GUI.after(0, lambda: show_update_notification(
                    current_version, latest_version, latest_release))
            else:
                logger.info(f"No new version available or version was skipped. "
                           f"Current: {current_version}, Latest: {latest_version}, "
                           f"Skipped: {skipped_version}")
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
    
    check_thread = threading.Thread(target=_check_worker)
    check_thread.daemon = True
    check_thread.start()


def show_update_notification(current_version, latest_version, latest_release_data):
    """Show the update notification dialog."""
    global ARCHITECT_GUI
    if not ARCHITECT_GUI or not ARCHITECT_GUI.winfo_exists():
        logger.warning("Cannot show update notification: GUI not initialized")
        return
    
    from gui_main import UpdateNotificationDialog
    notification = UpdateNotificationDialog(
        ARCHITECT_GUI, current_version, latest_version, latest_release_data
    )
    notification.focus_set()


# === EDMC Plugin Hooks ===

def plugin_start3(plugin_dir):
    """Called when the plugin is loaded by EDMC."""
    logger.info("Starting Architect Tracker plugin")
    settings = load_gui_settings()
    if settings.get('window_was_open', False):
        logger.info("Window was open on last exit, will reopen")
    return "Architect Tracker"


def plugin_app(parent: tk.Frame) -> tk.Frame:
    """Called when the EDMC app is ready. Returns the plugin frame."""
    global frame, PLUGIN_PARENT
    PLUGIN_PARENT = parent.winfo_toplevel()
    
    frame = tk.Frame(parent)
    tk.Button(frame, text="Show Architect Tracker", command=show_gui).pack(fill=tk.X, padx=5, pady=5)
    
    settings = load_gui_settings()
    if settings.get('window_was_open', False):
        parent.after(1000, show_gui)
    
    return frame


def plugin_stop():
    """Called when the plugin is stopped by EDMC."""
    global ARCHITECT_GUI
    settings = load_gui_settings()
    settings['window_was_open'] = bool(ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists())
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        settings['window_geometry'] = ARCHITECT_GUI.geometry()
    save_gui_settings(settings)
    
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.destroy()


def _start_overlay(found_station_key, found_station_materials_arg, skip_carrier_flag):
    """
    Uruchom persistent overlay z brakami dla podanej stacji.
    Wydzielona funkcja, aby uniknąć duplikacji kodu między startem gry a eventem Docked.
    """
    global overlay_resend_thread, overlay_resend_stop_event, overlay_resend_msgid, overlay_active

    if not overlay:
        logger.debug("Overlay module not available, cannot start overlay")
        return
    if not found_station_key or not found_station_materials_arg:
        logger.warning("Cannot start overlay without station key and materials")
        overlay_active = False
        return

    # Zatrzymaj poprzedni overlay jeśli istnieje
    try:
        if overlay_resend_stop_event:
            overlay_resend_stop_event.set()
        if overlay_resend_thread and overlay_resend_thread.is_alive():
            overlay_resend_thread.join(timeout=1)
    except Exception as exc:
        logger.debug(f"Failed to stop previous overlay thread: {exc}")

    overlay_active = True
    logger.info(f"Starting persistent overlay for station: {found_station_key}")

    # Uruchom pętlę odświeżania
    overlay_resend_stop_event = threading.Event()
    overlay_resend_msgid = f"archictect-shortage-{int(time.time())}"

    def _resend_loop(station_key, materials, skip_carrier_flag_inner, stop_event, interval=8):
        try:
            while not stop_event.is_set():
                try:
                    # Każda iteracja odświeża Market.json i Cargo.json
                    try:
                        from data_manager import load_market_data, load_cargo_data
                        market_items, market_name = load_market_data()
                        cargo_items = load_cargo_data()
                    except Exception:
                        market_items, cargo_items = [], []

                    cargo_lookup = {i.get('Name'): i for i in cargo_items} if cargo_items else {}
                    market_lookup = {i.get('Name'): i for i in market_items} if market_items else {}

                    shortage_data = {}
                    ship_items_dict = {}  # materiały w ładowni dla sekcji ///on///ship///
                    for mat_key, mat_info in materials.items():
                        try:
                            req = mat_info.get('RequiredAmount', 0)
                            prov = mat_info.get('ProvidedAmount', 0)
                            need = req - prov

                            if need <= 0:
                                continue

                            safe_mat = mat_key.replace("$", "").replace("_name;", "")

                            # Ilość z carriera (pomijane na normalnej stacji)
                            fc_qty = 0
                            if not skip_carrier_flag_inner and carrier_tracker:
                                try:
                                    fc_qty = carrier_tracker.get_quantity(safe_mat)
                                except Exception:
                                    logger.debug(f"Could not read carrier quantity for material: {safe_mat}")

                            # Ilość z ładowni statku
                            ship_qty = 0
                            if cargo_lookup and safe_mat in cargo_lookup:
                                ship_qty = cargo_lookup[safe_mat].get('Count', 0)

                            shortfall = max(0, need - (fc_qty + ship_qty))

                            # Zbierz materiały w ładowni do sekcji ship
                            if ship_qty > 0:
                                ship_name = mat_info.get('Name_Localised', safe_mat)
                                ship_items_dict[ship_name] = ship_qty

                            if shortfall > 0:
                                shortage_data[mat_key] = {
                                    'Name_Localised': mat_info.get('Name_Localised', safe_mat),
                                    'shortfall': shortfall,
                                    'RequiredAmount': req,
                                    'ProvidedAmount': prov
                                }
                        except Exception:
                            logger.debug(f"Skipping invalid material entry for key: {mat_key}", exc_info=True)

                    # Podział na dostępne/niedostępne w rynku
                    available_shortage = {k: v for k, v in shortage_data.items() if market_lookup.get(k, {}).get('Stock', 0) > 0}
                    unavailable_shortage = {k: v for k, v in shortage_data.items() if k not in available_shortage}

                    # Wyciągnij nazwę wyświetlaną
                    display_name = station_key
                    if ':' in display_name:
                        display_name = display_name.split(':', 1)[-1].strip()
                    elif ';' in display_name:
                        display_name = display_name.split(';', 1)[-1].strip()

                    if shortage_data or ship_items_dict:
                        overlay.send_shortage_overlay(
                            display_name, available_shortage, unavailable_shortage,
                            msgid=overlay_resend_msgid, ttl=interval + 2,
                            ship_items=ship_items_dict if ship_items_dict else None
                        )
                except Exception:
                    logger.debug("Error in overlay resend loop; will retry", exc_info=True)
                stop_event.wait(interval)
        finally:
            overlay_active = False
            try:
                overlay.clear_overlay(overlay_resend_msgid)
            except Exception as exc:
                logger.debug(f"Failed to clear overlay in thread cleanup: {exc}")

    overlay_resend_thread = threading.Thread(
        target=_resend_loop,
        args=(found_station_key, found_station_materials_arg, skip_carrier_flag, overlay_resend_stop_event),
        daemon=True
    )
    overlay_resend_thread.start()


def journal_entry(cmdr, is_beta, system, station, entry, state):
    """Called by EDMC for each journal event."""
    # Declare overlay persistence globals early so they are global within this function
    global overlay_resend_thread, overlay_resend_stop_event, overlay_resend_msgid, overlay_active
    event = entry.get("event")
    logger.info("Event detected: %s", event)

    # === Overlay przy starcie gry (gdy statek już zadokowany) ===
    # Jeśli state.Docked=True i overlay jeszcze nie działa, uruchom go
    if state.get('Docked') and overlay and not overlay_active:
        data = load_facility_requirements()
        found_station = None
        found_station_materials = None
        for station_key, info in data.items():
            if station and station.lower() in station_key.lower():
                found_station = station_key
                found_station_materials = info.get('materials', {})
                break

        if not found_station_materials and ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            try:
                sel = ARCHITECT_GUI.station_var.get()
                full_key = ARCHITECT_GUI.station_map.get(sel)
                if full_key and full_key in ARCHITECT_GUI.data:
                    found_station = full_key
                    found_station_materials = ARCHITECT_GUI.data[full_key].get('materials', {})
            except Exception:
                logger.debug("Could not determine selected station from GUI during startup overlay check", exc_info=True)

        if found_station_materials:
            _start_overlay(found_station, found_station_materials, True)
        elif ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists() and overlay:
            overlay.send_error_overlay(
                "Błąd: wybierz stację konstrukcyjną w oknie Architect Tracker",
                msgid="archictect-error-no-station"
            )

    if event == "ColonisationConstructionDepot":
        resources = entry.get("ResourcesRequired") or []
        materials = {}
        for resource in resources:
            try:
                name = resource.get("Name")
                if not name:
                   continue
                materials[name] = {
                   "Name_Localised": resource.get("Name_Localised", name),
                   "RequiredAmount": resource.get("RequiredAmount", 0),
                   "ProvidedAmount": resource.get("ProvidedAmount", 0),
                }
            except Exception:
                logger.debug("Skipping invalid construction resource entry", exc_info=True)
        # Use save_facility_requirements with a refresh callback
        save_req(materials, station, system,
                 refresh_callback=lambda: ARCHITECT_GUI.refresh() if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists() else None)

    elif event == "Docked":
        logger.info(f"Docked at station: {station} in system: {system}")
        data = load_facility_requirements()
        found_station = None
        found_station_materials = None
        for station_key, info in data.items():
            if station and station.lower() in station_key.lower():
                found_station = station_key
                found_station_materials = info.get('materials', {})
                logger.info(f"Found matching construction station: {found_station}")
                break
        
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()
            if found_station:
                for display_name, full_key in ARCHITECT_GUI.station_map.items():
                    if full_key == found_station:
                        logger.info(f"Auto-selecting construction station: {display_name}")
                        ARCHITECT_GUI.station_var.set(display_name)
                        ARCHITECT_GUI.display_station()
                        break
        
        # === Obsługa normalnych stacji (nie-konstrukcyjnych) ===
        # Jeśli nie znaleziono dopasowania do stacji konstrukcyjnej,
        # spróbuj użyć stacji wybranej w GUI – wtedy overlay pokaże
        # brakujące materiały dla tej stacji, bez danych z carriera.
        skip_carrier = False
        if not found_station_materials and overlay:
            if not ARCHITECT_GUI or not ARCHITECT_GUI.winfo_exists():
                # GUI zamknięte – wyślij błąd w overlay'u
                overlay.send_error_overlay(
                    "Błąd: otwórz okno Architect Tracker i wybierz stację konstrukcyjną",
                    msgid="archictect-error-no-gui"
                )
            else:
                try:
                    sel = ARCHITECT_GUI.station_var.get()
                    full_key = ARCHITECT_GUI.station_map.get(sel)
                    if not sel or not full_key:
                        # Brak wybranej stacji w GUI
                        overlay.send_error_overlay(
                            "Błąd: wybierz stację konstrukcyjną w oknie Architect Tracker",
                            msgid="archictect-error-no-station"
                        )
                    elif full_key in ARCHITECT_GUI.data:
                        found_station = full_key
                        found_station_materials = ARCHITECT_GUI.data[full_key].get('materials', {})
                        skip_carrier = True  # na normalnej stacji pomiń dane z carriera
                        logger.info(f"Using GUI-selected construction station for overlay: {found_station}")
                    else:
                        # Stacja istnieje ale nie ma materiałów (usunięta?)
                        overlay.send_error_overlay(
                            f"Błąd: brak danych dla stacji {sel}",
                            msgid="archictect-error-no-data"
                        )
                except Exception as e:
                    logger.debug(f"Could not get GUI-selected station: {e}", exc_info=True)

        # Uruchom persistent overlay – wspólna funkcja odświeża market/cargo co 8s
        if found_station_materials and overlay:
            _start_overlay(found_station, found_station_materials, skip_carrier)

    elif event == "Loadout":
        cargo_capacity = entry.get("CargoCapacity")
        if cargo_capacity and cargo_capacity > 0:
            logger.info(f"Ship loadout detected - Cargo capacity: {cargo_capacity}")
            if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
                ARCHITECT_GUI.update_cargo_capacity(cargo_capacity)

    elif event in ("Market", "Cargo", "CollectCargo", "EjectCargo", "MarketBuy", "MarketSell", 
                   "MiningRefined", "MissionCompleted", "BuyDrones", "SellDrones", 
                   "FetchRemoteModule", "MissionAccepted", "RedeemVoucher", "CarrierBuy", 
                   "CarrierSell", "EngineerCraft", "ModuleBuy", "ModuleSell", "ModuleRetrieve", 
                   "ModuleStore", "ApproachSettlement", "Location", "MarketData", "FSSDiscoveryScan"):
        logger.info(f"Market-related event detected: {event}. Refreshing GUI.")
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()

    elif event == "Undocked":
        # Stop persistent overlay resend when undocking
        overlay_active = False  # zresetuj flagę – po ponownym zadokowaniu overlay może wystartować
        if overlay_resend_stop_event:
            try:
                overlay_resend_stop_event.set()
            except Exception:
                pass
        if overlay_resend_thread and overlay_resend_thread.is_alive():
            try:
                overlay_resend_thread.join(timeout=1)
            except Exception:
                pass

    elif event == "CargoTransfer":
        transfers = entry.get("Transfers", [])
        carrier_tracker.apply_transfer_event(transfers)
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()

    elif event == "CargoDepot":
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()


def capi_fleetcarrier(data: CAPIData):
    """Called by EDMC when fleet carrier CAPI data is received."""
    logger.info("Received fleet carrier CAPI data")
    carrier_tracker.update(data)
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.refresh()