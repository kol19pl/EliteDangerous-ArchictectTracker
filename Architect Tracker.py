import json
import os
import logging
import tkinter as tk
from tkinter import ttk, messagebox
import platform
from contextlib import suppress
from companion import CAPIData
import binascii
from config import config
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
# Files for saving data and settings
SAVE_FILE     = os.path.join(USER_DIR, "construction_requirements.json")   
SETTINGS_FILE = os.path.join(USER_DIR, "settings.json")                    
LOG_FILE      = os.path.join(USER_DIR, "EDMC_Architect_Log.txt")           


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





# --- Settings persistence ---
def load_gui_settings():                                                    
    if not os.path.exists(SETTINGS_FILE):                                   
        return {}                                                          
    try:                                                                   
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:               
            return json.load(f)                                             
    except Exception as e:                                                  
        logger.error(f"Error loading GUI settings: {e}")                  
        return {}                                                           

def save_gui_settings(settings: dict):                                       
    try:                                                                    
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:               
            json.dump(settings, f, indent=4)                                
    except Exception as e:                                                  
        logger.error(f"Error saving GUI settings: {e}")                     


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


def save_facility_requirements(materials, station_name,system):
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
         data[station_name] = {
            "system": system,
            "materials": materials
        }

    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
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



def get_construction_system_name(self):
    # Which station is selected?
    sel  = self.station_var.get()
    full = self.station_map.get(sel)
    if not full:
        return 'N/A'

    # In save_facility_requirements you stored "system" under the full key
    entry = self.data.get(full, {})
    system_name = entry.get('system')
    return system_name or 'N/A'





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
      
    active_theme = config.get_int('theme')
    #if active_theme == theme.THEME_DARK:

    #elif active_theme == theme.THEME_TRANSPARENT:

   # elif active_theme == theme.THEME_DEFAULT:

    #else:



    edBlue = "#1fbeff"
    edOrange = "#ff8500"
    bgBlack = "#1a1a1a"

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Architect Tracker")
        self.geometry("800x600")
        self.configure(bg=self.bgBlack)
        settings = load_gui_settings()                                      # linia 205+       
        self.hide_provided     = settings.get('hide_provided', False)        # linia 206  ← dodane
        self.sort_by_system   = settings.get('sort_by_system', False)         # Sort stations by system
        self.selected_system  = settings.get('selected_system', "Wszystkie Systemy")  # Filter by system
        self.cargo_capacity   = settings.get('cargo_capacity', 720)           # Default cargo capacity (Type-9)
        cols = ("Material", "Required", "Provided", "Needed",
                "ON LAST STATION", "Carrier Qty", "Ship Qty", "Shortfall")
        self.column_visibility = settings.get(
            'column_visibility',
            {c: True for c in cols}
        )

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
        # System selection
        ttk.Label(frame, text="System:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.system_var = tk.StringVar(value=self.selected_system)
        self.system_dropdown = ttk.Combobox(frame, textvariable=self.system_var, state="readonly", width=30)
        self.system_dropdown.grid(row=0, column=1, sticky="we", padx=(0, 10))
        self.system_dropdown.bind("<<ComboboxSelected>>", lambda e: self.filter_by_system())
        
        # Station selection
        ttk.Label(frame, text="Station:").grid(row=1, column=0, sticky="w", padx=(0, 5))
        self.station_var = tk.StringVar()
        self.dropdown = ttk.Combobox(frame, textvariable=self.station_var, state="readonly", width=35)
        self.dropdown.grid(row=1, column=1, sticky="we", padx=(0, 10))
        self.dropdown.bind("<<ComboboxSelected>>", lambda e: self.display_station())

        ttk.Label(frame, text="Last Market:").grid(row=1, column=2, sticky="e", padx=(10, 5))
        self.market_name_label = ttk.Label(frame, text="")
        self.market_name_label.grid(row=1, column=3, sticky="w")

        ttk.Label(frame, text="Carrier:").grid(row=0, column=2, sticky="e", padx=(10, 5))
        self.carrier_label = ttk.Label(frame, text="")
        self.carrier_label.grid(row=0, column=3, sticky="w")

        # Settings button (now row 2)
        ttk.Button(frame, text="Settings", command=self.open_settings) \
            .grid(row=2, column=0, sticky="w", padx=5, pady=(8, 0))
        
        # Transport trips estimation
        self.transport_label = ttk.Label(frame, text="")
        self.transport_label.grid(row=2, column=1, sticky="w", padx=5, pady=(8, 0))
        

        # Treeview setup (row 3)
        cols = ("Material", "Required", "Provided", "Needed",
                "ON LAST STATION", "Carrier Qty", "Ship Qty", "Shortfall")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor='w' if c == "Material" else 'center')

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=3, column=0, columnspan=8, sticky="nsew")
        scrollbar.grid(row=3, column=8, sticky="ns")

        # Make row 3 expandable
        frame.rowconfigure(3, weight=1)
        for i in range(8):
            # Give column 1 (dropdown column) a weight to make it expandable
            frame.columnconfigure(i, weight=1 if i in [1, 3] else 0)

        #self.column_visibility = {c: True for c in cols}
        self.refresh_columns()  # Ensure columns initial visibility

    def open_settings(self):
        settings_window = tk.Toplevel(self)
        settings_window.transient(self)
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
            text="Remove delivered from lists",
            variable=self.hide_var,
            command=self.toggle_hide_provided
        )
        chk_hide.pack(anchor="w", padx=10, pady=(10, 0))
        
        # Add new setting: sort by system
        self.sort_var = tk.BooleanVar(value=self.sort_by_system)
        chk_sort = ttk.Checkbutton(
            settings_window,
            text="Sort stations by system",
            variable=self.sort_var,
            command=self.toggle_sort_mode
        )
        chk_sort.pack(anchor="w", padx=10, pady=(5, 0))
        
        # Cargo capacity setting
        ttk.Label(settings_window, text="Ship cargo capacity (tons):").pack(anchor="w", padx=10, pady=(10, 0))
        cargo_frame = ttk.Frame(settings_window)
        cargo_frame.pack(anchor="w", padx=10, pady=(0, 0), fill="x")
        
        self.cargo_var = tk.StringVar(value=str(self.cargo_capacity))
        cargo_entry = ttk.Entry(cargo_frame, width=6, textvariable=self.cargo_var)
        cargo_entry.pack(side="left", padx=(0, 5))
        
        ttk.Button(cargo_frame, text="Apply", command=self.update_cargo_capacity).pack(side="left")

        # Station removal section
        ttk.Separator(settings_window, orient="horizontal").pack(fill="x", padx=10, pady=10)
        ttk.Label(settings_window, text="Remove station from tracking:").pack(anchor="w", padx=10, pady=(5, 5))
        
        # Station removal dropdown
        removal_frame = ttk.Frame(settings_window)
        removal_frame.pack(anchor="w", padx=10, pady=(0, 5), fill="x")
        
        self.remove_station_var = tk.StringVar()
        self.remove_station_dropdown = ttk.Combobox(removal_frame, textvariable=self.remove_station_var, state="readonly", width=30)
        self.remove_station_dropdown.pack(side="left", padx=(0, 5))
        
        # Prepare the dropdown with station names and create a mapping back to the full keys
        station_options = []
        self.remove_station_map = {}  # Map display names to full station keys
        
        for station_key, info in self.data.items():
            # Use same display format as main UI
            display_name = (station_key.split(':', 1)[-1].strip() if ':' in station_key else 
                            station_key.split(';', 1)[-1].strip() if ';' in station_key else station_key)
            system_name = info.get('system', 'Unknown')
            display_text = f"{display_name} ({system_name})"
            
            # Store the mapping from display text to full station key
            self.remove_station_map[display_text] = station_key
            station_options.append(display_text)
        
        self.remove_station_dropdown['values'] = sorted(station_options)
        if station_options:
            self.remove_station_dropdown.current(0)
        
        # Remove button
        ttk.Button(removal_frame, text="Remove", command=self.remove_station).pack(side="left")
        
        # Position settings window over parent
        settings_window.update_idletasks()
        px = self.winfo_x()
        py = self.winfo_y()
        pw = self.winfo_width()
        ph = self.winfo_height()
        sw = settings_window.winfo_width()
        sh = settings_window.winfo_height()
        x = px + (pw - sw) // 2
        y = py + (ph - sh) // 2
        settings_window.geometry(f"+{x}+{y}")


    def toggle_column(self, column, is_visible: bool):
        self.column_visibility[column] = is_visible
        self.refresh_columns()
        save_gui_settings({
            'column_visibility': self.column_visibility,
            'hide_provided': self.hide_provided,
            'sort_by_system': self.sort_by_system,
            'selected_system': self.selected_system
        })

    def toggle_hide_provided(self):
        self.hide_provided = self.hide_var.get()
        self.refresh()
        save_gui_settings({
            'column_visibility': self.column_visibility,
            'hide_provided': self.hide_provided,
            'sort_by_system': self.sort_by_system,
            'selected_system': self.selected_system
        })

    def toggle_sort_mode(self):
        self.sort_by_system = self.sort_var.get()
        self.refresh()
        save_gui_settings({
            'column_visibility': self.column_visibility,
            'hide_provided': self.hide_provided,
            'sort_by_system': self.sort_by_system,
            'selected_system': self.selected_system,
            'cargo_capacity': self.cargo_capacity
        })
    
    def update_cargo_capacity(self):
        try:
            capacity = int(self.cargo_var.get())
            if capacity < 1:
                capacity = 1  # Ensure minimum capacity of 1
            self.cargo_capacity = capacity
            self.display_station()  # Update display to reflect new capacity
            save_gui_settings({
                'column_visibility': self.column_visibility,
                'hide_provided': self.hide_provided,
                'sort_by_system': self.sort_by_system,
                'selected_system': self.selected_system,
                'cargo_capacity': self.cargo_capacity
            })
        except ValueError:
            # Reset to previous value if entry is not a valid number
            self.cargo_var.set(str(self.cargo_capacity))
        
    def filter_by_system(self):
        self.selected_system = self.system_var.get()
        self.refresh()
        save_gui_settings({
            'column_visibility': self.column_visibility,
            'hide_provided': self.hide_provided,
            'sort_by_system': self.sort_by_system,
            'selected_system': self.selected_system,
            'cargo_capacity': self.cargo_capacity
        })

    def remove_station(self):
        # Get the selected station from dropdown
        selected = self.remove_station_var.get()
        if not selected:
            logger.error("No station selected for removal")
            tk.messagebox.showwarning("Warning", "Please select a station to remove", parent=self)
            return
            
        # Get the full station key directly from our mapping
        full_station_key = self.remove_station_map.get(selected)
        
        if not full_station_key:
            logger.error(f"Could not find station key for '{selected}'")
            tk.messagebox.showerror("Error", "Could not identify the selected station", parent=self)
            return
        
        # Extract station display name (for confirmation message)
        station_display = selected.rsplit(' (', 1)[0]  # Remove system name suffix
            
        # Confirm removal
        if not tk.messagebox.askyesno("Confirm Removal", 
                                      f"Are you sure you want to remove '{station_display}' from tracking?",
                                      parent=self):
            return
            
        # Remove from saved data
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if full_station_key in data:
                del data[full_station_key]
                
                # Save updated data
                with open(SAVE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                    
                # Log successful removal
                logger.info(f"Successfully removed station '{station_display}' with key '{full_station_key}'")
                
                # Update UI
                self.refresh()
                
                # Close settings window
                for widget in self.winfo_children():
                    if isinstance(widget, tk.Toplevel) and widget.title() == "Settings":
                        widget.destroy()
                        break
                
                tk.messagebox.showinfo("Success", f"Station '{station_display}' removed from tracking.", parent=self)
            else:
                logger.warning(f"Station key '{full_station_key}' not found in data file")
                tk.messagebox.showwarning("Warning", f"Station '{station_display}' not found in tracking data.", parent=self)
        except Exception as e:
            logger.error(f"Error removing station: {e}")
            tk.messagebox.showerror("Error", f"Failed to remove station: {e}", parent=self)

    def refresh_columns(self):
        visible_columns = [col for col, vis in self.column_visibility.items() if vis]
        self.tree["displaycolumns"] = visible_columns
        for col in visible_columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

    def refresh(self):
        # Zapamiętaj aktualnie wybraną nazwę stacji
        current_selection = self.station_var.get()

        # Wczytaj nowe dane
        data = load_facility_requirements()
        self.data = data
        
        # Extract all unique system names
        systems = set()
        for station, info in data.items():
            system_name = info.get('system', 'Unknown')
            if system_name:
                systems.add(system_name)
        
        # Prepare system dropdown
        current_system = self.system_var.get()
        system_values = ["Wszystkie Systemy"] + sorted(list(systems))
        self.system_dropdown['values'] = system_values
        
        # Restore system selection if possible
        if current_system in system_values:
            self.system_var.set(current_system)
        else:
            self.system_var.set("Wszystkie Systemy")
            self.selected_system = "Wszystkie Systemy"

        # Przygotuj dane do wyświetlenia
        display = [
            (
              (full.split(':', 1)[-1].strip() if ':' in full else 
               full.split(';', 1)[-1].strip() if ';' in full else full),
              full
            )
            for full in data
            if self.selected_system == "Wszystkie Systemy" or 
               self.data.get(full, {}).get('system', '') == self.selected_system
        ]
        # Sort based on user preference
        if self.sort_by_system:
            display.sort(key=lambda x: (self.data.get(x[1], {}).get('system', ''), x[0]))  # Sort by system then station
        else:
            display.sort(key=lambda x: x[0])  # Sortuj alfabetycznie
        self.station_map = {name: full for name, full in display}

        # Zaktualizuj dropdown
        values = [name for name, _ in display]
        self.dropdown['values'] = values

        # Przywróć wybór lub wybierz domyślnie pierwszą stację
        if values:
            if current_selection in values:
                self.station_var.set(current_selection)
            else:
                self.station_var.set(values[0])

            # Odśwież dane dla wybranej stacji
            self.display_station()
        else:
            # Brak danych – wyczyść drzewo
            self.tree.delete(*self.tree.get_children())
            # Clear transport label
            self.transport_label['text'] = ""

    def calculate_completion_percentage(self, materials):
        """Calculate the percentage of completion based on provided vs required materials"""
        total_required = 0
        total_provided = 0
        
        for mat, vals in materials.items():
            req = vals['RequiredAmount']
            prov = vals['ProvidedAmount']
            total_required += req
            total_provided += min(prov, req)  # Don't count excess materials
        
        if total_required == 0:
            return 100.0  # Avoid division by zero
            
        return (total_provided / total_required) * 100.0
        
    def calculate_required_trips(self, materials):
        """Calculate the estimated number of trips needed based on cargo capacity"""
        total_needed = 0
        for mat, vals in materials.items():
            req = vals['RequiredAmount']
            prov = vals['ProvidedAmount']
            if prov < req:  # Only count materials that aren't fully provided
                total_needed += (req - prov)
        
        if total_needed <= 0:
            return 0
        
        # Calculate trips, ensuring at least 1 trip if there's anything needed
        trips = (total_needed + self.cargo_capacity - 1) // self.cargo_capacity
        return max(1, trips)
        
    def display_station(self):
        self.tree.delete(*self.tree.get_children())
        sel = self.station_var.get()
        full = self.station_map.get(sel)
        if not full:
            self.transport_label['text'] = ""
            return
        materials = self.data[full]['materials']
        market_items, market_name = load_market_data()
        construction_system_name = get_construction_system_name(self)
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
            
        # Calculate and display estimated transport trips and completion percentage
        required_trips = self.calculate_required_trips(materials)
        completion_percentage = self.calculate_completion_percentage(materials)
        
        if required_trips > 0:
            self.transport_label['text'] = f"Est. trips: {required_trips} (based on {self.cargo_capacity} ton capacity) - Completion: {completion_percentage:.1f}%"
        else:
            self.transport_label['text'] = f"All materials delivered! - Completion: 100%"

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
        save_facility_requirements(materials, station, system )

    elif event in ("Market", "Cargo"):
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
    logger.info("Received fleet carrier CAPI data")
    carrier_tracker.update(data)
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.refresh()



