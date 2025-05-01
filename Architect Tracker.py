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

# Reset log
with suppress(Exception):
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
            else:
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

# --- Requirement persistence ---
def is_station_complete(materials):
    return all(info["ProvidedAmount"] >= info["RequiredAmount"] for info in materials.values())


def save_facility_requirements(materials, station_name):
    global ARCHITECT_GUI
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception:
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
    cleaned = {s: info for s, info in data.items() if not is_station_complete(info.get("materials", {}))}
    if cleaned != data:
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(cleaned, f, indent=4)
        except Exception as e:
            logger.error("Error writing cleaned data: %s", e)
    return cleaned


def load_market_data():
    if not os.path.exists(MARKET_JSON):
        return [], None
    try:
        with open(MARKET_JSON, "r", encoding="utf-8") as f:
            market = json.load(f)
        return market.get("Items", []), market.get("StationName")
    except Exception as e:
        logger.error("Error loading market data: %s", e)
        return [], None


def load_cargo_data():
    if not os.path.exists(CARGO_JSON):
        return []
    try:
        with open(CARGO_JSON, "r", encoding="utf-8") as f:
            cargo = json.load(f)
        return cargo.get("Inventory", [])
    except Exception as e:
        logger.error("Error loading cargo data: %s", e)
        return []

# --- GUI Definition ---
class ArchitectTrackerGUI(tk.Toplevel):
    edBlue = "#1fbeff"
    edOrange = "#ff8500"
    bgBlack = "#1a1a1a"

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Architect Tracker")
        self.geometry("800x600")
        self.configure(bg=self.bgBlack)
        self.hide_provided = False  # Nowe ustawienie
        self.last_selection = None
        self.setStyle()

        if not os.path.exists(SAVE_FILE):
            self._build_info_widgets()
        else:
            self._build_widgets()
            self.refresh()

    def setStyle(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=self.bgBlack,
                        foreground=self.edOrange,
                        rowheight=24,
                        fieldbackground=self.bgBlack)
        style.configure("Heading",
                        background=self.bgBlack,
                        foreground=self.edOrange)
        style.map("Treeview",
                  foreground=[("selected", self.edBlue)])

    def _build_info_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Construction site data not found!",
                  background=self.bgBlack,
                  foreground=self.edOrange).grid(row=0, column=0, sticky="w", padx=10)
        ttk.Label(frame,
                  text="Visit a construction site and the required commodities will automatically be displayed.",
                  background=self.bgBlack,
                  foreground=self.edOrange).grid(row=1, column=0, sticky="w", padx=10)
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}")

    def _build_widgets(self):
        frame = ttk.Frame(self, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)

        # Top controls (row 0)
        self.station_var = tk.StringVar()
        self.dropdown = ttk.Combobox(frame, textvariable=self.station_var, state="readonly")
        self.dropdown.grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.dropdown.bind("<<ComboboxSelected>>", lambda e: self.display_station())

        ttk.Label(frame, text="Market:").grid(row=0, column=1, sticky="e", padx=(0, 5))
        self.market_name_label = ttk.Label(frame, text="")
        self.market_name_label.grid(row=0, column=2, sticky="w")

        ttk.Label(frame, text="Carrier:").grid(row=0, column=3, sticky="e", padx=(10, 5))
        self.carrier_label = ttk.Label(frame, text="")
        self.carrier_label.grid(row=0, column=4, sticky="w")

        # Settings button (now row 1)
        ttk.Button(frame, text="Settings", command=self.open_settings) \
            .grid(row=1, column=0, sticky="w", padx=5, pady=(8, 0))

        # Treeview setup (row 2)
        cols = ("Material", "Required", "Provided", "Needed",
                "For Sale", "Carrier Qty", "Ship Qty", "Shortfall")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor='w' if c == "Material" else 'center')

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=2, column=0, columnspan=5, sticky="nsew")
        scrollbar.grid(row=2, column=5, sticky="ns")

        # Make row 2 expandable
        frame.rowconfigure(2, weight=1)
        for i in range(5):
            frame.columnconfigure(i, weight=1)

        self.column_visibility = {c: True for c in cols}
        self.refresh_columns()  # Ensure columns initial visibility

    def open_settings(self):
        settings_window = tk.Toplevel(self)
        settings_window.title("Settings")
        ttk.Label(settings_window, text="Select columns to display:").pack(padx=10, pady=5)
        for idx, (col, visible) in enumerate(self.column_visibility.items()):
            var = tk.BooleanVar(value=visible)
            if idx == 0:
                chk = ttk.Checkbutton(
                    settings_window,
                    text=col,
                    variable=var,
                    state="disabled"
                )
                var.set(True)
            else:
                chk = ttk.Checkbutton(
                    settings_window,
                    text=col,
                    variable=var,
                    command=lambda c=col, v=var: self.toggle_column(c, v.get())
                )
            chk.pack(anchor="w", padx=10)

        # New setting: remove fully provided materials
        self.hide_var = tk.BooleanVar(value=self.hide_provided)
        chk_hide = ttk.Checkbutton(
            settings_window,
            text="Usuń dostarczone z listy",
            variable=self.hide_var,
            command=self.toggle_hide_provided
        )
        chk_hide.pack(anchor="w", padx=10, pady=(10, 0))

    def toggle_column(self, column, is_visible: bool):
        self.column_visibility[column] = is_visible
        self.refresh_columns()

    def toggle_hide_provided(self):
        self.hide_provided = self.hide_var.get()
        self.refresh()

    def refresh_columns(self):
        visible_columns = [col for col, vis in self.column_visibility.items() if vis]
        self.tree["displaycolumns"] = visible_columns
        for col in visible_columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

    def refresh(self):
        #data = load_facility_requirements()
        # przywróć poprzedni wybór, jeśli jest
        previous = self.last_selection or self.station_var.get()
        data = load_facility_requirements()
        self.data = data
        display = [(full.split(':', 1)[-1].strip() if ':' in full else full, full) for full in data]
        display.sort(key=lambda x: x[0])
        self.station_map = {name: full for name, full in display}
        #self.dropdown['values'] = [name for name, _ in display]
        #if display:
        #    self.station_var.set(display[0][0])
        #    self.display_station()
        #else:
        #    self.tree.delete(*self.tree.get_children())
        values = [name for name, _ in display]
        self.dropdown['values'] = values
        if values:
        # jeśli poprzednia stacja nadal jest w liście, wybierz ją
         if previous in values:
          self.station_var.set(previous)
         else:
          self.station_var.set(values[0])
          self.display_station()

        else:
         self.tree.delete(*self.tree.get_children())

           # zapamiętaj aktualny wybór
        self.last_selection = self.station_var.get()


    def display_station(self):
        self.tree.delete(*self.tree.get_children())
        sel = self.station_var.get()
        full = self.station_map.get(sel)
        if not full:
            return
        materials = self.data[full]['materials']
        market_items, market_name = load_market_data()
        cargo_items = load_cargo_data()

        market_lookup = {i.get('Name'): i for i in market_items}
        cargo_lookup = {i.get('Name'): i for i in cargo_items}

        self.market_name_label['text'] = market_name or 'N/A'
        self.carrier_label['text'] = carrier_tracker.carrier_name or 'N/A'

        for idx, (mat, vals) in enumerate(materials.items()):
            req = vals['RequiredAmount']
            prov = vals['ProvidedAmount']
            if self.hide_provided and prov >= req:
                continue
            safeMat = mat.replace("$", "").replace("_name;", "")
            locName = vals['Name_Localised']
            need = req - prov
            for_sale = '✔' if market_lookup.get(mat, {}).get('Stock', 0) > 0 else ''
            fc_qty = carrier_tracker.get_quantity(safeMat)
            ship_qty = cargo_lookup.get(safeMat, {}).get('Count', 0)
            short = max(0, need - (fc_qty + ship_qty))
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.tree.insert("", "end", values=(locName, req, prov, need, for_sale,
                                                   fc_qty, ship_qty, short), tags=(tag,))

# --- Plugin Hooks ---
def show_gui():
    global ARCHITECT_GUI
    if not ARCHITECT_GUI or not ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI = ArchitectTrackerGUI(None)
    else:
        ARCHITECT_GUI.lift()
        ARCHITECT_GUI.refresh()


def plugin_start3(plugin_dir):
    logger.info("Starting Architect Tracker plugin")
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
        materials = {r["Name"]: {"Name_Localised": r["Name_Localised"],
                                   "RequiredAmount": r["RequiredAmount"],
                                   "ProvidedAmount": r["ProvidedAmount"]}
                     for r in resources}
        save_facility_requirements(materials, station)

    elif event in ("Market", "Cargo"):
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()

    elif event == "CargoTransfer":
        transfers = entry.get("Transfers", [])
        carrier_tracker.apply_transfer_event(transfers)
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()


def capi_fleetcarrier(data: CAPIData):
    logger.info("Received fleet carrier CAPI data")
    carrier_tracker.update(data)
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.refresh()

