"""Plugin hooks module - EDMC plugin entry points."""
import os
import logging
import tkinter as tk
from tkinter import messagebox
from companion import CAPIData
from typing import Optional
import threading

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


def journal_entry(cmdr, is_beta, system, station, entry, state):
    """Called by EDMC for each journal event."""
    event = entry.get("event")
    logger.info("Event detected: %s", event)

    if event == "ColonisationConstructionDepot":
        resources = entry.get("ResourcesRequired", [])
        materials = {r["Name"]: {"Name_Localised": r["Name_Localised"],
                                   "RequiredAmount": r["RequiredAmount"],
                                   "ProvidedAmount": r["ProvidedAmount"]}
                     for r in resources}
        # Use save_facility_requirements with a refresh callback
        save_req(materials, station, system,
                 refresh_callback=lambda: ARCHITECT_GUI.refresh() if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists() else None)

    elif event == "Docked":
        logger.info(f"Docked at station: {station} in system: {system}")
        data = load_facility_requirements()
        found_station = None
        for station_key, info in data.items():
            if station and station.lower() in station_key.lower():
                found_station = station_key
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