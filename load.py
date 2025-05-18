import logging
import tkinter as tk
from companion import CAPIData

# Import settings functionality
from settings import load_gui_settings, save_gui_settings
from main import (
    ArchitectTrackerGUI, show_gui, carrier_tracker, save_facility_requirements,
    load_facility_requirements, load_market_data, load_cargo_data, ARCHITECT_GUI, frame
)

# Plugin registration functions
def plugin_start3(plugin_dir):
    logger = logging.getLogger("ArchitectTracker")
    logger.info("Starting Architect Tracker plugin")
    
    # Check if window should be reopened based on previous state
    settings = load_gui_settings()
    if settings.get('window_was_open', False):
        # We'll handle the actual window opening in plugin_app
        logger.info("Window was open on last exit, will reopen")
    
    return "Architect Tracker"

def plugin_app(parent: tk.Frame) -> tk.Frame:
    global frame
    # Create a standard frame with NO custom styling
    frame = tk.Frame(parent)
    
    # Use a standard Tkinter button without custom styling
    tk.Button(frame, text="Show Architect Tracker", command=show_gui).pack(fill=tk.X, padx=5, pady=5)
    
    # Check if we need to open the window based on previous state
    settings = load_gui_settings()
    if settings.get('window_was_open', False):
        # Use after to ensure EDMC is fully loaded before showing our window
        parent.after(1000, show_gui)
    
    return frame

def plugin_stop():
    global ARCHITECT_GUI
    # Save window state before closing
    settings = load_gui_settings()
    settings['window_was_open'] = bool(ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists())
    save_gui_settings(settings)
    
    # Then destroy the window
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.destroy()

def journal_entry(cmdr, is_beta, system, station, entry, state):
    logger = logging.getLogger("ArchitectTracker")
    event = entry.get("event")
    logger.info("Event detected: %s", event)

    if event == "ColonisationConstructionDepot":
        resources = entry.get("ResourcesRequired", [])
        materials = {r["Name"]: {"Name_Localised": r["Name_Localised"],
                                "RequiredAmount": r["RequiredAmount"],
                                "ProvidedAmount": r["ProvidedAmount"]}
                    for r in resources}
        save_facility_requirements(materials, station, system)

    elif event in ("Market", "Cargo", "CollectCargo", "EjectCargo", "MarketBuy", "MarketSell", "MiningRefined", "MissionCompleted"):
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
    logger = logging.getLogger("ArchitectTracker")
    logger.info("Received fleet carrier CAPI data")
    carrier_tracker.update(data)
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.refresh()
