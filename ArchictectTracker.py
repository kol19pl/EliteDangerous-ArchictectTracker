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
from typing import Optional

# Global GUI instance
ARCHITECT_GUI = None
frame: Optional[tk.Frame] = None

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
CARGO_JSON = os.path.join(os.getenv('USERPROFILE', os.path.expanduser('~')), 'Saved Games', 'Frontier Developments', 'Elite Dangerous', 'Cargo.json')

if os.path.exists(LOG_FILE):
  os.remove(LOG_FILE)

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
        for transfer in transfers:
            name = transfer.get("Type").capitalize()
            qty = transfer.get("Count", 0)
            direction = transfer.get("Direction")
            if not name or qty <= 0 or direction not in ("tocarrier", "toship"):
                continue
            current = self.commodities.get(name, 0)
            if direction == "tocarrier":
                self.commodities[name] = current + qty
            else:  # toship
                self.commodities[name] = max(0, current - qty)
        self.save()

    def get_quantity(self, commodity_name):
        return self.commodities.get(commodity_name.capitalize(), 0)

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
        
def load_cargo_data():
    if not os.path.exists(CARGO_JSON):
        return {}, None
    try:
        with open(CARGO_JSON, "r", encoding="utf-8") as f:
            cargo = json.load(f)
        return cargo.get("Inventory", [])
    except Exception as e:
        logger.error("Error loading cargo data: %s", e)
        return [], None

# --- GUI ---
class ArchitectTrackerGUI(tk.Toplevel):

    edBlue = "#1fbeff"
    edOrange = "#ff8500"
    bgBlack="#1a1a1a"
    startx = 0
    starty = 0
    ywin = 0
    xwin = 0
        
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Architect Tracker")
        self.geometry("800x600")        
        #self.create_titlebar() also removes from task bar which means not usable in VR
        self.configure(bg=ArchitectTrackerGUI.bgBlack)
        if not os.path.exists(SAVE_FILE):
            self._build_info_widgets()
        else:
            self._build_widgets()
            self.refresh()
        
    def get_pos(self, event):
        self.xwin = self.winfo_x()
        self.ywin = self.winfo_y()
        self.startx = event.x_root
        self.starty = event.y_root

        self.ywin = self.ywin - self.starty
        self.xwin = self.xwin - self.startx
        
    def close_window(self):
        self.destroy()
        
    # Function to move the window
    def move_window(self, event):
        self.geometry('{0}x{1}+{2}+{3}'.format(self.winfo_width(), self.winfo_height(), event.x_root + self.xwin, event.y_root + self.ywin))
        self.startx = event.x_root
        self.starty = event.y_root
            
    def create_titlebar(self):
        # Remove the default title bar
        self.overrideredirect(True)

        # Create a custom title bar
        title_bar = tk.Frame(self, bg=ArchitectTrackerGUI.bgBlack, relief='raised', bd=2)
        title_bar.pack(fill=tk.X)

        # Add a title label to the custom title bar
        title_label = tk.Label(title_bar, text="Architect Tracker", bg=ArchitectTrackerGUI.bgBlack, fg=ArchitectTrackerGUI.edOrange)
        title_label.pack(side=tk.LEFT, padx=10)

        # Add a close button to the custom title bar
        close_button = tk.Button(title_bar, text='X', command=self.close_window, bg=ArchitectTrackerGUI.bgBlack, fg=ArchitectTrackerGUI.edOrange, relief='flat')
        close_button.pack(side=tk.RIGHT, padx=5)

        # Add content to the main window
        content = tk.Frame(self, bg=ArchitectTrackerGUI.bgBlack)
        content.pack(fill=tk.BOTH, expand=True)

        # Bind the title bar to the move window function
        title_bar.bind('<B1-Motion>', self.move_window)
        title_bar.bind('<Button-1>', self.get_pos)
    
    def setStyle(self):       
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=ArchitectTrackerGUI.bgBlack, foreground=ArchitectTrackerGUI.edOrange, rowheight=24,
                        selectbackground=ArchitectTrackerGUI.bgBlack)
        style.configure("Heading", background=ArchitectTrackerGUI.bgBlack, foreground=ArchitectTrackerGUI.edOrange)
        style.configure("TCombobox", background=ArchitectTrackerGUI.bgBlack, foreground=ArchitectTrackerGUI.edOrange, selectbackground=ArchitectTrackerGUI.bgBlack)
        style.configure("TFrame", background=ArchitectTrackerGUI.bgBlack)
        style.configure("TLabel", background=ArchitectTrackerGUI.bgBlack, foreground=ArchitectTrackerGUI.edOrange)
        style.map("Treeview", foreground=[("selected", ArchitectTrackerGUI.edBlue)])
        style.map('TCombobox',
                  fieldbackground=[('readonly', ArchitectTrackerGUI.bgBlack)], # Background color of the entry field
                  background=[('readonly', ArchitectTrackerGUI.bgBlack)]) # Background color of the dropdown list
    
    def _build_info_widgets(self): 
        self.setStyle()
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Construction site data not found!").grid(row=0, column=0, sticky="w", padx=(10,0))        
        ttk.Label(frame, text="Visit a construction site and the required commodities will automaticly be displayed.").grid(row=1, column=0, sticky="w", padx=(10,0))
        
        #frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        self.geometry(f"{width}x{height}")

    def _build_widgets(self):
        self.setStyle()
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        self.station_var = tk.StringVar()
        ttk.Label(frame, text="Market:").grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.market_name_label = ttk.Label(frame, text="")
        self.market_name_label.grid(row=0, column=2, sticky="w")
        ttk.Label(frame, text="Carrier:").grid(row=0, column=3, sticky="w", padx=(10, 0))
        self.carrier_label = ttk.Label(frame, text="")
        self.carrier_label.grid(row=0, column=4, sticky="w")

        self.dropdown = ttk.Combobox(frame, textvariable=self.station_var, state="readonly")
        self.dropdown.grid(row=0, column=0, sticky="w")
        self.dropdown.bind("<<ComboboxSelected>>", lambda e: self.display_station())

        cols = ("Material", "Required", "Provided", "Needed", "For Sale", "Carrier Qty", "Ship Qty", "Shortfall")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
            anchor = 'w' if c == "Material" else 'center'
            self.tree.column(c, anchor=anchor)

        # Scrollbar pionowy
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Umieszczenie w gridzie
        self.tree.grid(row=1, column=0, columnspan=5, sticky="nsew")
        scrollbar.grid(row=1, column=5, sticky='ns')

        frame.rowconfigure(1, weight=1)
        for col in range(5):
            frame.columnconfigure(col, weight=1)

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

        num_items = 0
        if self.tree.get_children():
            num_items = len(self.tree.get_children())
        self.tree.configure(height=num_items)
        self.update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        self.geometry(f"{width}x{height}")        

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
        market_lookup = {i.get("Name"): i for i in market_items}
        
        cargo_items = load_cargo_data()
        cargo_lookup = {i.get("Name"): i for i in cargo_items}
            
        self.tree.tag_configure('evenrow', background='#2a2a2a', foreground='#ff8500')
        self.tree.tag_configure('oddrow', background='#1a1a1a', foreground='#ff8500')
        
        for idx, (mat, vals) in enumerate(materials.items()):
            safeMat = mat.replace("$","").replace("_name;","")
            locName = vals["Name_Localised"]
            req = vals["RequiredAmount"]
            prov = vals["ProvidedAmount"]
            need = req - prov
            market_info = market_lookup.get(mat)
            for_sale = "✔" if market_info and market_info.get("Stock", 0) > 0 else ""
            fc_qty = carrier_tracker.get_quantity(safeMat)
            cargo_item = cargo_lookup.get(safeMat)
            ship_qty = cargo_item.get("Count") if cargo_item else 0
            short = max(0, need - (fc_qty + ship_qty))
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.tree.insert("", "end", values=(locName, req, prov, need, for_sale, fc_qty, ship_qty, short), tags=(tag,))        

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

def plugin_app(parent: tk.Frame) -> tk.Frame:
    global frame
    frame = tk.Frame(parent)
    tk.Button(frame, text="Show Architect Tracker", command=show_gui).pack(fill=tk.X, padx=5, pady=5)
    theme.update(frame)
    return frame

def plugin_stop():
    global ARCHITECT_GUI
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.destroy()

def journal_entry(cmdr, is_beta, system, station, entry, state):
    event = entry.get("event")
    logger.info("Event detected: %s", event)

    if event == "ColonisationConstructionDepot":
        resources = entry.get("ResourcesRequired", [])
        materials = {
            r["Name"]: {
                "Name_Localised": r["Name_Localised"],
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

    elif event == "Cargo":
        logger.info("Cargo event: %s", entry)
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()

    elif event == "CargoTransfer":
        logger.info("CargoTransfer event: %s", entry)
        transfers = entry.get("Transfers", [])
        carrier_tracker.apply_transfer_event(transfers)
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()

def capi_fleetcarrier(data):
    logger.info("Received fleet carrier CAPI data: %s", data)
    carrier_tracker.update(data)
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.refresh()
