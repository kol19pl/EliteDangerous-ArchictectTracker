import json
import os
import logging
import tkinter as tk
from tkinter import ttk
import platform
from contextlib import suppress
from companion import CAPIData
import binascii
from theme import theme

# Global GUI instance
ARCHITECT_GUI = None

# Configure user directories
if platform.system() == "Windows":
    USER_DIR = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")), "ArchitectTracker")
elif platform.system() == "Darwin":
    USER_DIR = os.path.join(os.path.expanduser("~/Library/Application Support"), "ArchitectTracker")
else:
    USER_DIR = os.path.join(os.path.expanduser("~/.config"), "ArchitectTracker")

os.makedirs(USER_DIR, exist_ok=True)

SAVE_FILE = os.path.join(USER_DIR, "construction_requirements.json")
LOG_FILE = os.path.join(USER_DIR, "EDMC_Architect_Log.txt")
CARRIER_FILE = os.path.join(USER_DIR, "fleet_carrier_cargo.json")
MARKET_JSON = os.path.join(os.getenv('USERPROFILE', os.path.expanduser('~')), 'Saved Games', 'Frontier Developments', 'Elite Dangerous', 'Market.json')

logger = logging.getLogger("ArchitectTracker")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(file_handler)

# --- Helpers ---
def decode_vanity_name(hex_string):
    try:
        return binascii.unhexlify(hex_string).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to decode vanity name: {e}")
        return hex_string

# --- Fleet Carrier Cargo Tracker ---
class FleetCarrierCargoTracker:
    def __init__(self):
        self.commodities = {}
        self.carrier_name = ""
        self.callsign = ""
        self.load()

    def update(self, data):
        cargo_items = data.get('cargo', [])
        if not isinstance(cargo_items, list):
            logger.warning("Unexpected cargo data format.")
            return
        self.commodities.clear()
        for item in cargo_items:
            name = item.get("locName") or item.get("commodity")
            qty = item.get("qty", 0)
            if not name:
                logger.warning("Missing commodity name in cargo item: %s", item)
                continue
            self.commodities[name.lower()] = self.commodities.get(name.lower(), 0) + qty

        carrier_info = data.get("name", {})
        hex_name = carrier_info.get("vanityName")
        self.carrier_name = decode_vanity_name(hex_name) if hex_name else "Unnamed Carrier"
        self.callsign = carrier_info.get("callsign", "")
        self.save()

    def apply_transfer_event(self, transfers):
        for transfer in transfers:
            name = transfer.get("Type_Localised") or transfer.get("Type")
            qty = transfer.get("Count", 0)
            direction = transfer.get("Direction")
            if not name or qty <= 0 or direction not in ("tocarrier", "toship"):
                continue
            current = self.commodities.get(name.lower(), 0)
            if direction == "tocarrier":
                self.commodities[name.lower()] = current + qty
            else:  # toship
                self.commodities[name.lower()] = max(0, current - qty)
        self.save()

    def get_quantity(self, commodity_name):
        return self.commodities.get(commodity_name.lower(), 0)

    def save(self):
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

carrier_tracker = FleetCarrierCargoTracker()

# --- Helper Functions ---
def is_station_complete(materials):
    return all(info["ProvidedAmount"] >= info["RequiredAmount"] for info in materials.values())

def save_facility_requirements(materials, station_name):
    global ARCHITECT_GUI
    try:
        with suppress(FileNotFoundError):
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception as e:
        logger.error("Error loading saved data: %s", e)
        data = {}
    if is_station_complete(materials):
        data.pop(station_name, None)
    else:
        data[station_name] = {"materials": materials}
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error("Error saving data: %s", e)
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.refresh()

def load_facility_requirements():
    if not os.path.exists(SAVE_FILE):
        return {}
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Error reading save file: %s", e)
        return {}
    cleaned = {}
    for station, info in data.items():
        if not is_station_complete(info.get("materials", {})):
            cleaned[station] = info
    if cleaned != data:
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(cleaned, f, indent=4)
        except Exception as e:
            logger.error("Error writing cleaned data: %s", e)
    return cleaned

def load_market_data():
    if not os.path.exists(MARKET_JSON):
        return {}, None
    try:
        with open(MARKET_JSON, "r", encoding="utf-8") as f:
            market = json.load(f)
        return market.get("Items", []), market.get("StationName")
    except Exception as e:
        logger.error("Error loading market data: %s", e)
        return [], None

# --- GUI ---
class ArchitectTrackerGUI(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Architect Tracker")
        self.geometry("800x480")
        self.configure(bg="#1a1a1a")
        self._build_widgets()
        self.refresh()

    def _build_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#1a1a1a", foreground="white", rowheight=24,
                        fieldbackground="#1a1a1a")
        style.map("Treeview", background=[("selected", "#333333")])
        self.station_var = tk.StringVar()
        ttk.Label(frame, text="Market:", foreground="white", background="#1a1a1a").grid(row=0, column=1, sticky="w", padx=(10,0))
        self.market_name_label = ttk.Label(frame, text="", foreground="white", background="#1a1a1a")
        self.market_name_label.grid(row=0, column=2, sticky="w")
        ttk.Label(frame, text="Carrier:", foreground="white", background="#1a1a1a").grid(row=0, column=3, sticky="w", padx=(10,0))
        self.carrier_label = ttk.Label(frame, text="", foreground="white", background="#1a1a1a")
        self.carrier_label.grid(row=0, column=4, sticky="w")
        self.dropdown = ttk.Combobox(frame, textvariable=self.station_var, state="readonly")
        self.dropdown.grid(row=0, column=0, sticky="w")
        self.dropdown.bind("<<ComboboxSelected>>", lambda e: self.display_station())
        cols = ("Material", "Required", "Provided", "Needed", "For Sale", "Carrier Qty", "Shortfall")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.grid(row=1, column=0, columnspan=5, sticky="nsew")
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

    def refresh(self):
        data = load_facility_requirements()
        self.data = data
        display = []
        for full, info in data.items():
            name = full.split(":", 1)[-1].strip() if ":" in full else full
            display.append((name, full))
        display.sort(key=lambda x: x[0])
        self.station_map = {name: full for name, full in display}
        self.dropdown["values"] = [name for name, _ in display]
        if display:
            self.station_var.set(display[0][0])
            self.display_station()
        else:
            self.tree.delete(*self.tree.get_children())

    def display_station(self):
        self.tree.delete(*self.tree.get_children())
        sel = self.station_var.get()
        full = self.station_map.get(sel)
        if not full:
            return
        materials = self.data[full]["materials"]
        market_items, market_name = load_market_data()
        self.market_name_label["text"] = f"{market_name or 'N/A'}"
        self.carrier_label["text"] = carrier_tracker.carrier_name or 'N/A'
        market_lookup = {i.get("Name_Localised") or i.get("Name"): i for i in market_items}
        for mat, vals in materials.items():
            req = vals["RequiredAmount"]
            prov = vals["ProvidedAmount"]
            need = req - prov
            market_info = market_lookup.get(mat)
            for_sale = "✔" if market_info and market_info.get("Stock", 0) > 0 else ""
            fc_qty = carrier_tracker.get_quantity(mat)
            short = max(0, need - fc_qty)
            self.tree.insert("", "end", values=(mat, req, prov, need, for_sale, fc_qty, short))

# --- Plugin Hooks ---
def show_gui():
    global ARCHITECT_GUI
    if not ARCHITECT_GUI or not ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI = ArchitectTrackerGUI(None)
    else:
        ARCHITECT_GUI.lift()
        ARCHITECT_GUI.refresh()

def plugin_start3(plugin_dir):
    show_gui()
    return "Architect Tracker"

def plugin_app(parent):
    frame = ttk.Frame(parent)
    ttk.Button(frame, text="Show Architect Tracker", command=show_gui).pack(fill=tk.X, padx=5, pady=5)
    theme.update(frame) #   DOESN'T DO ANYTHING
    return frame

def plugin_stop():
    global ARCHITECT_GUI
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.destroy()

def journal_entry(cmdr, is_beta, system, station, entry, state):
    event = entry.get("event")

    if event == "ColonisationConstructionDepot":
        resources = entry.get("ResourcesRequired", [])
        materials = {
            r["Name_Localised"]: {
                "RequiredAmount": r["RequiredAmount"],
                "ProvidedAmount": r["ProvidedAmount"]
            }
            for r in resources
        }
        logger.info("Detected ColonisationConstructionDepot for %s", station)
        save_facility_requirements(materials, station)

    elif event == "Market":
        logger.info("Journal Market event detected at station: %s", station)
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()

    elif event == "CargoTransfer":
        logger.info("CargoTransfer event: %s", entry)
        transfers = entry.get("Transfers", [])
        carrier_tracker.apply_transfer_event(transfers)
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()


def capi_fleetcarrier(data):
    logger.info("Received fleet carrier CAPI data")
    carrier_tracker.update(data)
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.refresh()
