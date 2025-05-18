import json
import os
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from contextlib import suppress
from companion import CAPIData
import binascii
from config import config
# Don't import theme to avoid any interference with EDMC's theming system
import theme  # Import as module to avoid namespace conflicts
from typing import Optional

# Import settings functionality
from settings import USER_DIR, load_gui_settings, save_gui_settings
from GUI_settings import SettingsWindow

# Global GUI instance
ARCHITECT_GUI = None
frame: Optional[tk.Frame] = None

SAVE_FILE = os.path.join(USER_DIR, "construction_requirements.json")
LOG_FILE = os.path.join(USER_DIR, "EDMC_Architect_Log.txt")
CARRIER_FILE = os.path.join(USER_DIR, "fleet_carrier_cargo.json")
MARKET_JSON = os.path.join(os.getenv('USERPROFILE', os.path.expanduser('~')), 'Saved Games', 'Frontier Developments', 'Elite Dangerous', 'Market.json')
CARGO_JSON = os.path.join(os.getenv('USERPROFILE', os.path.expanduser('~')), 'Saved Games', 'Frontier Developments', 'Elite Dangerous', 'Cargo.json')
# Files for saving data and settings
SAVE_FILE     = os.path.join(USER_DIR, "construction_requirements.json")   
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





# Settings management is now in settings.py


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

def get_total_ship_cargo():
    """Calculate the total amount of cargo currently in the ship."""
    cargo_items = load_cargo_data()
    total_cargo = sum(item.get('Count', 0) for item in cargo_items)
    return total_cargo

# --- GUI Definition ---
class ArchitectTrackerGUI(tk.Toplevel):
      
    # Get EDMC's active theme to use as default if no user preference is set
    @staticmethod
    def get_edmc_theme():
        """Convert EDMC theme to plugin theme constant without affecting EDMC itself"""
        try:
            # Get EDMC's theme setting without modifying it
            active_theme = config.get_int('theme')
            # Use constants directly to avoid theme module manipulation
            if active_theme == 1:  # theme.THEME_DARK
                return ArchitectTrackerGUI.THEME_BLACK
            elif active_theme == 2:  # theme.THEME_TRANSPARENT
                return ArchitectTrackerGUI.THEME_BLACK  # Transparent maps to black
            elif active_theme == 0:  # theme.THEME_DEFAULT
                return ArchitectTrackerGUI.THEME_WHITE
            else:
                return ArchitectTrackerGUI.THEME_BLACK  # Default fallback
        except Exception as e:
            logger.error(f"Error detecting EDMC theme: {e}")
            return ArchitectTrackerGUI.THEME_BLACK  # Safe fallback if we can't detect EDMC theme

    # Theme constants
    THEME_BLACK = 0
    THEME_WHITE = 1
    
    # Color schemes
    THEME_COLORS = {
        THEME_BLACK: {
            "background": "#1a1a1a",
            "foreground": "#ff8500",
            "highlight": "#1fbeff",
            "button_bg": "#333333",
            "button_fg": "#ffffff",
            "label_fg": "#ff8500"
        },
        THEME_WHITE: {
            "background": "#f0f0f0",
            "foreground": "#222222",
            "highlight": "#1fbeff",
            "button_bg": "#e0e0e0",
            "button_fg": "#000000",
            "label_fg": "#000000"
        }
    }
    
    # Legacy color definitions (kept for backward compatibility)
    edBlue = "#1fbeff"
    edOrange = "#ff8500"
    bgBlack = "#1a1a1a"

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Architect Tracker")
        self.geometry("800x600")
        settings = load_gui_settings()                                      # linia 205+       
        self.hide_provided     = settings.get('hide_provided', False)        # linia 206  ← dodane
        self.sort_by_system   = settings.get('sort_by_system', False)         # Sort stations by system
        self.selected_system  = settings.get('selected_system', "Wszystkie Systemy")  # Filter by system
        self.cargo_capacity   = settings.get('cargo_capacity', 720)           # Default cargo capacity (Type-9)
        
        # Store settings window reference for theme updates
        self.settings_window = None
        
        # Use user preference if set, otherwise default to WHITE theme for main window
        if 'current_theme' in settings:
            self.current_theme = settings.get('current_theme')
        else:
            self.current_theme = self.THEME_WHITE  # Default to WHITE theme for main window
            
        # Material frame theme - default to BLACK theme if not set
        if 'materials_theme' in settings:
            self.materials_theme = settings.get('materials_theme')
        else:
            self.materials_theme = self.THEME_BLACK  # Default to BLACK theme for materials
        self.configure(bg=self.THEME_COLORS[self.current_theme]["background"])
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
        # Main window theme
        main_theme_colors = self.THEME_COLORS[self.current_theme]
        # Materials frame theme
        materials_theme_colors = self.THEME_COLORS[self.materials_theme]
        
        style = ttk.Style()
        style.theme_use("default")
        
        # Configure TreeView with materials theme
        style.configure("Treeview",
                        background=materials_theme_colors["background"],
                        foreground=materials_theme_colors["foreground"],
                        rowheight=24,
                        fieldbackground=materials_theme_colors["background"])
        style.configure("Heading",
                        background=materials_theme_colors["background"],
                        foreground=materials_theme_colors["foreground"])
        style.map("Treeview",
                  foreground=[("selected", materials_theme_colors["highlight"])])
                  
        # Configure TButton style based on main theme
        style.configure("TButton",
                       background=main_theme_colors["button_bg"],
                       foreground=main_theme_colors["button_fg"])
        style.map("TButton",
                  background=[("active", main_theme_colors["highlight"])],
                  foreground=[("active", main_theme_colors["button_fg"])])
        
        # Configure TLabel style based on main theme
        style.configure("TLabel",
                       background=main_theme_colors["background"],
                       foreground=main_theme_colors["label_fg"])
                       
        # Configure TEntry style for text fields
        style.configure("TEntry",
                       fieldbackground=main_theme_colors["background"],
                       foreground=main_theme_colors["foreground"])
        style.map("TEntry",
                 fieldbackground=[("active", main_theme_colors["background"])])
                       
        # Materials frame specific style (for frame backgrounds)
        style.configure("Materials.TFrame", 
                       background=materials_theme_colors["background"])
        
        # Main window specific style
        style.configure("Main.TFrame",
                       background=main_theme_colors["background"])
                       
        # Configure TCheckbutton style
        style.configure("TCheckbutton",
                       background=main_theme_colors["background"],
                       foreground=main_theme_colors["foreground"])
        style.map("TCheckbutton",
                  background=[("active", main_theme_colors["background"])],
                  foreground=[("active", main_theme_colors["highlight"])])
                  
        # Configure TRadiobutton style
        style.configure("TRadiobutton",
                       background=main_theme_colors["background"],
                       foreground=main_theme_colors["foreground"])
        style.map("TRadiobutton",
                  background=[("active", main_theme_colors["background"])],
                  foreground=[("active", main_theme_colors["highlight"])])

    def _build_info_widgets(self):
        frame = ttk.Frame(self, padding=10, style="Main.TFrame")
        frame.pack(fill=tk.BOTH, expand=True)
        theme_colors = self.THEME_COLORS[self.current_theme]
        ttk.Label(frame, text="Construction site data not found!",
                  background=theme_colors["background"],
                  foreground=theme_colors["foreground"]).grid(row=0, column=0, sticky="w", padx=10)
        ttk.Label(frame,
                  text="Visit a construction site and the required commodities will automatically be displayed.",
                  background=theme_colors["background"],
                  foreground=theme_colors["foreground"]).grid(row=1, column=0, sticky="w", padx=10)
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}")

    def _build_widgets(self):
        # Main control frame with main theme
        frame = ttk.Frame(self, padding=8, style="Main.TFrame")
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
        
        # Current cargo display
        self.cargo_label = ttk.Label(frame, text="")
        self.cargo_label.grid(row=2, column=2, sticky="e", padx=5, pady=(8, 0))
        

        # Treeview setup (row 3)
        cols = ("Material", "Required", "Provided", "Needed",
                "ON LAST STATION", "Carrier Qty", "Ship Qty", "Shortfall")
        # Materials frame with materials theme
        materials_frame = ttk.Frame(frame, style="Materials.TFrame")
        materials_frame.grid(row=3, column=0, columnspan=8, sticky="nsew")
        
        self.tree = ttk.Treeview(materials_frame, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor='w' if c == "Material" else 'center')

        scrollbar = ttk.Scrollbar(materials_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Make row 3 expandable
        frame.rowconfigure(3, weight=1)
        for i in range(8):
            # Give column 1 (dropdown column) a weight to make it expandable
            frame.columnconfigure(i, weight=1 if i in [1, 3] else 0)

        #self.column_visibility = {c: True for c in cols}
        self.refresh_columns()  # Ensure columns initial visibility


    def toggle_column(self, column, is_visible: bool):
        self.column_visibility[column] = is_visible
        self.refresh_columns()
        save_gui_settings({
            'column_visibility': self.column_visibility,
            'hide_provided': self.hide_provided,
            'sort_by_system': self.sort_by_system,
            'selected_system': self.selected_system,
            'current_theme': self.current_theme,
            'materials_theme': self.materials_theme,
            'cargo_capacity': self.cargo_capacity
        })

    def toggle_hide_provided(self, value=None):
        """Toggle hide provided setting."""
        if value is not None:
            self.hide_provided = value
            # Update the checkbox if this is called from settings window
            if hasattr(self, 'hide_var'):
                self.hide_var.set(value)
        else:
            self.hide_provided = self.hide_var.get()
        self.refresh()
        save_gui_settings({
            'column_visibility': self.column_visibility,
            'hide_provided': self.hide_provided,
            'sort_by_system': self.sort_by_system,
            'selected_system': self.selected_system,
            'current_theme': self.current_theme,
            'materials_theme': self.materials_theme,
            'cargo_capacity': self.cargo_capacity
        })

    def toggle_sort_mode(self):
        self.sort_by_system = self.sort_var.get()
        self.refresh()
        save_gui_settings({
            'column_visibility': self.column_visibility,
            'hide_provided': self.hide_provided,
            'sort_by_system': self.sort_by_system,
            'selected_system': self.selected_system,
            'current_theme': self.current_theme,
            'cargo_capacity': self.cargo_capacity
        })
    
    def update_cargo_capacity(self, value=None):
        """Update cargo capacity setting."""
        try:
            if value is not None:
                # Value passed from settings window
                capacity = value
                # Update the cargo_var if it exists in this context
                if hasattr(self, 'cargo_var'):
                    self.cargo_var.set(str(capacity))
            else:
                # Called from main window UI
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
                'current_theme': self.current_theme,
                'cargo_capacity': self.cargo_capacity
            })
            
            # Add logging to help debug
            logger.info(f"Cargo capacity updated to: {capacity}")
            
        except ValueError:
            # Reset to previous value if entry is not a valid number
            if hasattr(self, 'cargo_var'):
                self.cargo_var.set(str(self.cargo_capacity))
            logger.warning(f"Invalid cargo capacity value provided")
        
    def filter_by_system(self):
        self.selected_system = self.system_var.get()
        self.refresh()
        save_gui_settings({
            'column_visibility': self.column_visibility,
            'hide_provided': self.hide_provided,
            'sort_by_system': self.sort_by_system,
            'selected_system': self.selected_system,
            'current_theme': self.current_theme,
            'cargo_capacity': self.cargo_capacity
        })

    def change_theme(self, value=None):
        """Change the application theme when a different theme is selected"""
        if value is not None:
            # Value passed from settings window
            self.current_theme = value
            # Update the theme_var if it exists in this context
            if hasattr(self, 'theme_var'):
                self.theme_var.set(value)
        else:
            # Called from main window UI
            self.current_theme = self.theme_var.get()
            
        # Update window background color
        self.configure(bg=self.THEME_COLORS[self.current_theme]["background"])
        
        # Apply new style
        self.setStyle()
        
        # Force refresh the UI to apply new theme colors
        self.refresh()
        
        # Update settings window if it exists
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.update_theme()
        
        # Save settings
        save_gui_settings({
            'column_visibility': self.column_visibility,
            'hide_provided': self.hide_provided,
            'sort_by_system': self.sort_by_system,
            'selected_system': self.selected_system,
            'current_theme': self.current_theme,  # Explicitly save user's theme preference
            'materials_theme': self.materials_theme,
            'cargo_capacity': self.cargo_capacity
        })
        
        # Add logging to help debug
        logger.info(f"Main window - Changed theme to: {self.current_theme}")

    def change_materials_theme(self, value=None):
        """Change the materials frame theme when a different theme is selected"""
        if value is not None:
            # Value passed from settings window
            self.materials_theme = value
            # Update the materials_theme_var if it exists in this context
            if hasattr(self, 'materials_theme_var'):
                self.materials_theme_var.set(value)
        else:
            # Called from main window UI
            self.materials_theme = self.materials_theme_var.get()
        
        # Apply new style
        self.setStyle()
        
        # Force refresh the UI to apply new theme colors
        self.refresh()
        
        # Update settings window if it exists
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.update_theme()
        
        # Save settings
        save_gui_settings({
            'column_visibility': self.column_visibility,
            'hide_provided': self.hide_provided,
            'sort_by_system': self.sort_by_system,
            'selected_system': self.selected_system,
            'current_theme': self.current_theme,
            'materials_theme': self.materials_theme,  # Save materials theme preference
            'cargo_capacity': self.cargo_capacity
        })
        
        # Add logging to help debug
        logger.info(f"Main window - Changed materials theme to: {self.materials_theme}")
    
    # update_settings_window_theme method removed - now handled by SettingsWindow
    
    def open_settings(self):
        """Open the settings window to configure plugin options."""
        # Close existing settings window if open
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
            
        # Create a dictionary with theme constants
        theme_constants = {
            "THEME_COLORS": self.THEME_COLORS,
            "THEME_BLACK": self.THEME_BLACK,
            "THEME_WHITE": self.THEME_WHITE
        }
            
        # Create new settings window with proper theme
        self.settings_window = SettingsWindow(
            parent=self,
            # Theme-related properties
            theme_constants=theme_constants,
            current_theme=self.current_theme,
            materials_theme=self.materials_theme,
            
            # Settings data
            column_visibility=self.column_visibility,
            hide_provided=self.hide_provided,
            sort_by_system=self.sort_by_system,
            cargo_capacity=self.cargo_capacity,
            data=self.data,
            
            # Callback functions
            toggle_column_callback=self.toggle_column,
            toggle_hide_provided_callback=self.toggle_hide_provided,
            toggle_sort_mode_callback=self.toggle_sort_mode,
            update_cargo_capacity_callback=self.update_cargo_capacity,
            remove_station_callback=self.remove_station,
            change_theme_callback=self.change_theme,
            change_materials_theme_callback=self.change_materials_theme
        )
        
    def remove_station(self, full_station_key=None):
        """Remove a station from tracking.
        
        Args:
            full_station_key: The key of the station to remove. If None, uses the selected station.
        """
        if full_station_key is None:
            # Get the selected station from dropdown
            selected = self.remove_station_var.get()
            if not selected:
                logger.error("No station selected for removal")
                tk.messagebox.showwarning("Warning", "Please select a station to remove", parent=self)
                return
                
            # Get the full station key directly from our mapping
            full_station_key = self.remove_station_map.get(selected)
            
        if not full_station_key:
            logger.error(f"Could not find station key for the selected station")
            tk.messagebox.showerror("Error", "Could not identify the selected station", parent=self)
            return
        
        # Extract station display name (for confirmation message)
        if ':' in full_station_key:
            station_display = full_station_key.split(':', 1)[-1].strip()
        elif ';' in full_station_key:
            station_display = full_station_key.split(';', 1)[-1].strip()
        else:
            station_display = full_station_key
            
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
            # Clear transport and cargo labels
            self.transport_label['text'] = ""
            self.cargo_label['text'] = ""

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

        # Calculate and display total ship cargo
        total_cargo = get_total_ship_cargo()
        self.cargo_label['text'] = f"Current Cargo: {total_cargo}/{self.cargo_capacity} tons"

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
            stock_qty = market_lookup.get(mat, {}).get('Stock', 0)
            for_sale = f"✔ {stock_qty}" if stock_qty > 0 else ''
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
        # Create new window with appropriate theme
        ARCHITECT_GUI = ArchitectTrackerGUI(None)
    else:
        # Update existing window
        ARCHITECT_GUI.lift()
        
        # We no longer automatically follow EDMC theme changes - using fixed defaults instead
        # Refresh the UI to ensure proper rendering
        ARCHITECT_GUI.setStyle()
        
        ARCHITECT_GUI.refresh()


def plugin_start3(plugin_dir):
    logger.info("Starting Architect Tracker plugin")
    # Don't automatically show GUI to avoid any theme issues at startup
    # show_gui()  # Commented out to prevent startup theme interference
    
    # Check if window should be reopened based on previous state
    settings = load_gui_settings()
    if settings.get('window_was_open', False):
        # We can't use parent.after here since we don't have the parent reference yet
        # We'll handle the actual window opening in plugin_app
        logger.info("Window was open on last exit, will reopen")
    
    return "Architect Tracker"


def plugin_app(parent: tk.Frame) -> tk.Frame:
    global frame
    # Create a standard frame with NO custom styling
    frame = tk.Frame(parent)
    
    # Use a standard Tkinter button instead of a styled button
    # Don't apply any custom styles or configurations
    tk.Button(frame, text="Show Architect Tracker", command=show_gui).pack(fill=tk.X, padx=5, pady=5)
    
    # Check if we need to open the window based on previous state
    settings = load_gui_settings()
    if settings.get('window_was_open', False):
        # Use after to ensure EDMC is fully loaded before showing our window
        parent.after(1000, show_gui)
    
    # COMPLETELY REMOVED theme.update(frame) call to avoid any theme interference
    
    # Let EDMC apply its own themes naturally without our interference
    # Theme handling is only applied to our separate window
    
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
    event = entry.get("event")
    logger.info("Event detected: %s", event)

    if event == "ColonisationConstructionDepot":
        resources = entry.get("ResourcesRequired", [])
        materials = {r["Name"]: {"Name_Localised": r["Name_Localised"],
                                   "RequiredAmount": r["RequiredAmount"],
                                   "ProvidedAmount": r["ProvidedAmount"]}
                     for r in resources}
        save_facility_requirements(materials, station, system )

    elif event == "Docked":
        logger.info(f"Docked at station: {station} in system: {system}")
        
        # Check if this is a construction station we're tracking
        data = load_facility_requirements()
        
        # Try to find the station in our tracking list
        found_station = None
        for station_key, info in data.items():
            # Check if the current station matches any tracked station
            if station and station.lower() in station_key.lower():
                found_station = station_key
                logger.info(f"Found matching construction station: {found_station}")
                break
        
        # Refresh the GUI and select the station if found
        if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
            ARCHITECT_GUI.refresh()
            
            # After refresh, try to select the station if we found it
            if found_station:
                # Get the display name from the station_map
                for display_name, full_key in ARCHITECT_GUI.station_map.items():
                    if full_key == found_station:
                        logger.info(f"Auto-selecting construction station: {display_name}")
                        ARCHITECT_GUI.station_var.set(display_name)
                        ARCHITECT_GUI.display_station()
                        break

    elif event in ("Market", "Cargo", "CollectCargo", "EjectCargo", "MarketBuy", "MarketSell", "MiningRefined", "MissionCompleted",
                  "BuyDrones", "SellDrones", "FetchRemoteModule", "MissionAccepted", "RedeemVoucher", "CarrierBuy", "CarrierSell", 
                  "EngineerCraft", "ModuleBuy", "ModuleSell", "ModuleRetrieve", "ModuleStore",
                  "ApproachSettlement", "Location", "MarketData", "FSSDiscoveryScan"):
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
    logger.info("Received fleet carrier CAPI data")
    carrier_tracker.update(data)
    if ARCHITECT_GUI and ARCHITECT_GUI.winfo_exists():
        ARCHITECT_GUI.refresh()



