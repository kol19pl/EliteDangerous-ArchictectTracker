import json
import os
import logging
import tkinter as tk
from tkinter import ttk
import platform
from contextlib import suppress

# Global GUI instance
ARCHITECT_GUI = None

# Configure user directories
if platform.system() == "Windows":
    USER_DIR = os.path.join(
        os.getenv("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")),
        "ArchitectTracker"
    )
elif platform.system() == "Darwin":
    USER_DIR = os.path.join(
        os.path.expanduser("~/Library/Application Support"),
        "ArchitectTracker"
    )
else:
    USER_DIR = os.path.join(
        os.path.expanduser("~/.config"),
        "ArchitectTracker"
    )

os.makedirs(USER_DIR, exist_ok=True)

SAVE_FILE = os.path.join(USER_DIR, "construction_requirements.json")
LOG_FILE = os.path.join(USER_DIR, "EDMC_Architect_Log.txt")
MARKET_JSON = os.path.join(
    os.getenv('USERPROFILE', os.path.expanduser('~')),
    'Saved Games',
    'Frontier Developments',
    'Elite Dangerous',
    'Market.json'
)

logger = logging.getLogger("ArchitectTracker")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(file_handler)

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
        return {}
    try:
        with open(MARKET_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Error loading market data: %s", e)
        return {}

def get_required_commodities():
    data = load_facility_requirements()
    required = set()
    for info in data.values():
        for mat, vals in info.get("materials", {}).items():
            if vals["ProvidedAmount"] < vals["RequiredAmount"]:
                required.add(mat)
    return required

class ArchitectTrackerGUI(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Architect Tracker")
        self.geometry("700x450")
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
        self.dropdown = ttk.Combobox(frame, textvariable=self.station_var, state="readonly")
        self.dropdown.grid(row=0, column=0, sticky="w")
        self.dropdown.bind("<<ComboboxSelected>>", lambda e: self.display_station())

        self.market_station_label = ttk.Label(frame, text="", foreground="white", background="#1a1a1a")
        self.market_station_label.grid(row=0, column=1, sticky="w", padx=10)

        cols = ("Material", "Required", "Provided", "Needed", "For Sale")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.grid(row=1, column=0, columnspan=2, sticky="nsew")

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
        market_data = load_market_data()
        market_station = market_data.get("StationName", "")
        self.market_station_label.config(text=f"Market: {market_station}" if market_station else "")
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
        market_items = load_market_data().get("Items", [])

        for_sale_lookup = {}
        for item in market_items:
            name = (item.get("Name_Localised") or item.get("Name")).lower()
            if item.get("Stock", 0) > 0:
                for_sale_lookup[name] = True

        self.tree.tag_configure('evenrow', background='#2a2a2a')
        self.tree.tag_configure('oddrow', background='#1a1a1a')

        for idx, (mat, vals) in enumerate(materials.items()):
            req = vals["RequiredAmount"]
            prov = vals["ProvidedAmount"]
            need = req - prov
            for_sale = "✔" if mat.lower() in for_sale_lookup else ""
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.tree.insert("", "end", values=(mat, req, prov, need, for_sale), tags=(tag,))

def show_gui():
    global ARCHITECT_GUI
    if not ARCHITECT_GUI or not ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI = ArchitectTrackerGUI(None)
    else:
        ARCHITECT_GUI.lift()
        ARCHITECT_GUI.refresh()

def journal_entry(cmdr, is_beta, system, station, entry, state):
    event = entry.get("event")

    if event == "ColonisationConstructionDepot":
        resources = entry.get("ResourcesRequired", [])
        materials = {r["Name_Localised"]: {"RequiredAmount": r["RequiredAmount"],
                                           "ProvidedAmount": r["ProvidedAmount"]}
                     for r in resources}
        logger.info("Detected ColonisationConstructionDepot for %s", station)
        save_facility_requirements(materials, station)

    elif event == "Market":
        logger.info("Detected Market event at %s", station)
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()

def plugin_start3(plugin_dir):
    return "Architect Tracker"

def plugin_stop():
    global ARCHITECT_GUI
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.destroy()

def plugin_app(parent):
    frame = ttk.Frame(parent)
    ttk.Button(frame, text="Show Architect Tracker", command=show_gui).pack(fill=tk.X, padx=5, pady=5)
    return frame
