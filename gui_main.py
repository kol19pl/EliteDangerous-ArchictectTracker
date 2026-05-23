"""Main GUI module - contains ArchitectTrackerGUI and UpdateNotificationDialog."""
import os
import logging
import tkinter as tk
from tkinter import ttk
from config import config
from typing import Optional

from settings import USER_DIR, load_gui_settings, save_gui_settings, get_skipped_version, save_skipped_version
from GUI_settings import SettingsWindow
from tabelka import DEFAULT_COLS, build_material_table, initialize_treeview_tags, refresh_tree_columns
from capi_tracker import FleetCarrierCargoTracker, CapiAutoRefresh
from data_manager import (
    SAVE_FILE, load_facility_requirements, save_facility_requirements,
    load_market_data, load_cargo_data, get_total_ship_cargo, get_construction_system_name
)
import updater

# Global GUI instance - set from plugin_hooks
ARCHITECT_GUI: Optional['ArchitectTrackerGUI'] = None

# Configure logger (if not already configured by parent)
logger = logging.getLogger("ArchitectTracker")

# Carrier tracker instance
carrier_tracker = FleetCarrierCargoTracker()


class ArchitectTrackerGUI(tk.Toplevel):
    """Main GUI window for the Architect Tracker plugin."""
    
    # Get EDMC's active theme to use as default if no user preference is set
    @staticmethod
    def get_edmc_theme():
        """Convert EDMC theme to plugin theme constant without affecting EDMC itself"""
        try:
            active_theme = config.get_int('theme')
            if active_theme == 1:  # theme.THEME_DARK
                return ArchitectTrackerGUI.THEME_BLACK
            elif active_theme == 2:  # theme.THEME_TRANSPARENT
                return ArchitectTrackerGUI.THEME_BLACK
            elif active_theme == 0:  # theme.THEME_DEFAULT
                return ArchitectTrackerGUI.THEME_WHITE
            else:
                return ArchitectTrackerGUI.THEME_BLACK
        except Exception as e:
            logger.error(f"Error detecting EDMC theme: {e}")
            return ArchitectTrackerGUI.THEME_BLACK

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
        self.parent = parent
        self.title("Architect Tracker")

        # Set initial default geometry BEFORE transient() call
        self.geometry("800x400")
        
        if self.parent:
            self.transient(self.parent)
            self.lift()
            self.attributes('-topmost', True)
            self.after(10, lambda: self.attributes('-topmost', False))

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        settings = load_gui_settings()

        self.hide_provided = settings.get('hide_provided', False)
        self.sort_by_system = settings.get('sort_by_system', False)
        self.selected_system = settings.get('selected_system', "All Systems")
        self.cargo_capacity = settings.get('cargo_capacity', 720)
        
        # CAPI auto-refresh
        self.capi_auto_refresh = CapiAutoRefresh(
            refresh_callback=self.refresh,
            save_settings_callback=self.save_settings
        )
        capi_interval = settings.get('capi_refresh_interval', 60)
        self.capi_auto_refresh.set_interval(capi_interval)
        
        self.settings_window = None
        
        # Theme settings
        if 'current_theme' in settings:
            self.current_theme = settings.get('current_theme')
        else:
            self.current_theme = self.THEME_WHITE
            
        if 'materials_theme' in settings:
            self.materials_theme = settings.get('materials_theme')
        else:
            self.materials_theme = self.THEME_BLACK
            
        self.configure(bg=self.THEME_COLORS[self.current_theme]["background"])
        
        cols = ("Material", "Required", "Provided", "Needed",
                "ON LAST STATION", "Carrier Qty", "Ship Qty", "Shortfall")
        default_visibility = {c: True for c in cols}
        self.column_visibility = settings.get('column_visibility', default_visibility)
        self.column_order = settings.get('column_order', list(default_visibility.keys()))
        self.column_order = [c for c in self.column_order if c in default_visibility]
        for c in default_visibility:
            if c not in self.column_order:
                self.column_order.append(c)

        self.setStyle()
        
        # Initialize data attributes
        self.data = {}
        self.station_map = {}

        if not os.path.exists(SAVE_FILE):
            self._build_info_widgets()
        else:
            self._build_widgets()
            self.refresh()
        
        # Restore geometry after all widgets are built
        saved_geometry = settings.get('window_geometry')
        if saved_geometry:
            try:
                self.geometry(saved_geometry)
                self.update_idletasks()
                x = self.winfo_x()
                y = self.winfo_y()
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                if x > screen_width - 50 or y > screen_height - 50:
                    self.center_window()
            except Exception:
                self.geometry("800x400")
                self.update_idletasks()
                self.center_window()
        else:
            self.update_idletasks()
            self.center_window()
        
        # Set up CAPI timer after tkinter is fully initialized
        self.after(100, self._init_capi_timer)
    
    def _init_capi_timer(self):
        """Initialize the CAPI auto-refresh timer with tkinter functions."""
        self.capi_auto_refresh.set_tk_after_funcs(self.after, self.after_cancel)
        self.capi_auto_refresh.start()

    def center_window(self):
        """Center the window on the screen."""
        try:
            self.update_idletasks()
            width = self.winfo_width()
            height = self.winfo_height()
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x = (screen_width // 2) - (width // 2)
            y = (screen_height // 2) - (height // 2)
            x = max(0, x)
            y = max(0, y)
            self.geometry(f'{width}x{height}+{x}+{y}')
            logger.debug(f"Window centered on screen at: {x}x{y}")
        except Exception as e:
            logger.warning(f"Could not center window: {e}")

    def setStyle(self):
        """Apply theme styles to the window."""
        main_theme_colors = self.THEME_COLORS[self.current_theme]
        materials_theme_colors = self.THEME_COLORS[self.materials_theme]
        
        style = ttk.Style()
        style.theme_use("default")
        
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
                  
        style.configure("TButton",
                       background=main_theme_colors["button_bg"],
                       foreground=main_theme_colors["button_fg"])
        style.map("TButton",
                  background=[("active", main_theme_colors["highlight"])],
                  foreground=[("active", main_theme_colors["button_fg"])])
        
        style.configure("TLabel",
                       background=main_theme_colors["background"],
                       foreground=main_theme_colors["label_fg"])
                       
        style.configure("TEntry",
                       fieldbackground=main_theme_colors["background"],
                       foreground=main_theme_colors["foreground"])
        style.map("TEntry",
                 fieldbackground=[("active", main_theme_colors["background"])])
                       
        style.configure("Materials.TFrame", 
                       background=materials_theme_colors["background"])
        
        style.configure("Main.TFrame",
                       background=main_theme_colors["background"])
                       
        style.configure("TCheckbutton",
                       background=main_theme_colors["background"],
                       foreground=main_theme_colors["foreground"])
        style.map("TCheckbutton",
                  background=[("active", main_theme_colors["background"])],
                  foreground=[("active", main_theme_colors["highlight"])])
                  
        style.configure("TRadiobutton",
                       background=main_theme_colors["background"],
                       foreground=main_theme_colors["foreground"])
        style.map("TRadiobutton",
                  background=[("active", main_theme_colors["background"])],
                  foreground=[("active", main_theme_colors["highlight"])])

        if hasattr(self, 'tree'):
            initialize_treeview_tags(self.tree, self.materials_theme)

    def _build_info_widgets(self):
        """Build info widgets when no save file exists."""
        frame = ttk.Frame(self, padding=8, style="Main.TFrame")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Architect Tracker",
                 font=("Segoe UI", 14, "bold")).pack(pady=20)
        ttk.Label(frame, text="No facility data found.\nVisit a construction site to start tracking.").pack(pady=10)

    def _build_widgets(self):
        """Build the main window widgets."""
        frame = ttk.Frame(self, padding=8, style="Main.TFrame")
        frame.pack(fill=tk.BOTH, expand=True)

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

        # Settings button
        ttk.Button(frame, text="Settings", command=self.open_settings) \
            .grid(row=2, column=0, sticky="w", padx=5, pady=(8, 0))
        
        # Transport trips estimation
        self.transport_label = ttk.Label(frame, text="")
        self.transport_label.grid(row=2, column=1, sticky="w", padx=5, pady=(8, 0))
        
        # Current cargo display
        self.cargo_label = ttk.Label(frame, text="")
        self.cargo_label.grid(row=2, column=2, sticky="e", padx=5, pady=(8, 0))
        
        # Treeview
        materials_frame = ttk.Frame(frame, style="Materials.TFrame")
        materials_frame.grid(row=3, column=0, columnspan=8, sticky="nsew")
        
        self.tree = build_material_table(materials_frame, DEFAULT_COLS)
        initialize_treeview_tags(self.tree, self.materials_theme)

        frame.rowconfigure(3, weight=1)
        for i in range(8):
            frame.columnconfigure(i, weight=1 if i in [1, 3] else 0)

        self.refresh_columns()

    def toggle_column(self, column, is_visible: bool):
        self.column_visibility[column] = is_visible
        self.refresh_columns()
        self.save_settings()

    def toggle_hide_provided(self, value=None):
        if value is not None:
            self.hide_provided = value
            if hasattr(self, 'hide_var'):
                self.hide_var.set(value)
        else:
            self.hide_provided = self.hide_var.get()
        self.refresh()
        self.save_settings()

    def toggle_sort_mode(self):
        self.sort_by_system = self.sort_var.get()
        self.refresh()
        self.save_settings()
    
    def update_cargo_capacity(self, value=None):
        try:
            if value is not None:
                capacity = value
                if hasattr(self, 'cargo_var'):
                    self.cargo_var.set(str(capacity))
            else:
                capacity = int(self.cargo_var.get())
                
            if capacity < 1:
                capacity = 1
                
            self.cargo_capacity = capacity
            self.display_station()
            self.save_settings()
            logger.info(f"Cargo capacity updated to: {capacity}")
        except ValueError:
            if hasattr(self, 'cargo_var'):
                self.cargo_var.set(str(self.cargo_capacity))
            logger.warning("Invalid cargo capacity value provided")
        
    def filter_by_system(self):
        self.selected_system = self.system_var.get()
        self.refresh()
        self.save_settings()

    def change_theme(self, value=None):
        if value is not None:
            self.current_theme = value
            if hasattr(self, 'theme_var'):
                self.theme_var.set(value)
        else:
            self.current_theme = self.theme_var.get()
            
        self.configure(bg=self.THEME_COLORS[self.current_theme]["background"])
        self.setStyle()
        self.refresh()
        
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.update_theme()
        
        self.save_settings()
        logger.info(f"Main window - Changed theme to: {self.current_theme}")

    def change_materials_theme(self, value=None):
        if value is not None:
            self.materials_theme = value
            if hasattr(self, 'materials_theme_var'):
                self.materials_theme_var.set(value)
        else:
            self.materials_theme = self.materials_theme_var.get()
        
        self.setStyle()
        if hasattr(self, 'tree'):
            initialize_treeview_tags(self.tree, self.materials_theme)
        
        self.refresh()
        
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.update_theme()
        
        self.save_settings()
        logger.info(f"Main window - Changed materials theme to: {self.materials_theme}")
    
    def update_window_size(self, width: int, height: int, x: int = None, y: int = None):
        try:
            if width < 400:
                width = 400
            if height < 300:
                height = 300
                
            if x is not None and y is not None:
                self.geometry(f"{width}x{height}+{x}+{y}")
                logger.info(f"Window resized to {width}x{height} and repositioned to +{x}+{y}")
            else:
                current_x = self.winfo_x()
                current_y = self.winfo_y()
                self.geometry(f"{width}x{height}+{current_x}+{current_y}")
                logger.info(f"Window resized to {width}x{height}")
            
            self.save_settings()
        except Exception as e:
            logger.error(f"Error updating window size: {e}")
    
    def reset_window_size(self):
        try:
            self.geometry("800x400")
            self.update_idletasks()
            self.center_window()
            self.save_settings()
            logger.info("Window reset to default size and centered")
        except Exception as e:
            logger.error(f"Error resetting window size: {e}")
    
    def open_settings(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
            
        theme_constants = {
            "THEME_COLORS": self.THEME_COLORS,
            "THEME_BLACK": self.THEME_BLACK,
            "THEME_WHITE": self.THEME_WHITE
        }
        
        try:
            window_width = self.winfo_width()
            window_height = self.winfo_height()
            window_x = self.winfo_x()
            window_y = self.winfo_y()
        except Exception:
            window_width = 800
            window_height = 400
            window_x = 0
            window_y = 0
        
        self.settings_window = SettingsWindow(
            parent=self,
            theme_constants=theme_constants,
            current_theme=self.current_theme,
            materials_theme=self.materials_theme,
            column_visibility=self.column_visibility,
            column_order=self.column_order,
            hide_provided=self.hide_provided,
            sort_by_system=self.sort_by_system,
            cargo_capacity=self.cargo_capacity,
            data=self.data,
            window_width=window_width,
            window_height=window_height,
            window_x=window_x,
            window_y=window_y,
            capi_refresh_interval=self.capi_auto_refresh.get_interval(),
            toggle_column_callback=self.toggle_column,
            reorder_columns_callback=self.reorder_columns,
            toggle_hide_provided_callback=self.toggle_hide_provided,
            toggle_sort_mode_callback=self.toggle_sort_mode,
            update_cargo_capacity_callback=self.update_cargo_capacity,
            remove_station_callback=self.remove_station,
            change_theme_callback=self.change_theme,
            change_materials_theme_callback=self.change_materials_theme,
            update_window_size_callback=self.update_window_size,
            reset_window_size_callback=self.reset_window_size,
            force_refresh_capi_callback=self.force_refresh_capi,
            update_capi_interval_callback=self.update_capi_refresh_interval
        )
        
    def remove_station(self, full_station_key=None):
        if full_station_key is None:
            selected = self.remove_station_var.get()
            if not selected:
                logger.error("No station selected for removal")
                tk.messagebox.showwarning("Warning", "Please select a station to remove", parent=self)
                return
            full_station_key = self.remove_station_map.get(selected)
            
        if not full_station_key:
            logger.error("Could not find station key for the selected station")
            tk.messagebox.showerror("Error", "Could not identify the selected station", parent=self)
            return
        
        if ':' in full_station_key:
            station_display = full_station_key.split(':', 1)[-1].strip()
        elif ';' in full_station_key:
            station_display = full_station_key.split(';', 1)[-1].strip()
        else:
            station_display = full_station_key
            
        if not tk.messagebox.askyesno("Confirm Removal", 
                                      f"Are you sure you want to remove '{station_display}' from tracking?", 
                                      parent=self):
            return
            
        try:
            from data_manager import SAVE_FILE
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if full_station_key in data:
                del data[full_station_key]
                with open(SAVE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                logger.info(f"Successfully removed station '{station_display}' with key '{full_station_key}'")
                self.refresh()
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
        refresh_tree_columns(self.tree, self.column_order, self.column_visibility)

    def save_settings(self):
        settings = load_gui_settings()
        settings.update({
            'column_visibility': self.column_visibility,
            'column_order': self.column_order,
            'hide_provided': self.hide_provided,
            'sort_by_system': self.sort_by_system,
            'selected_system': self.selected_system,
            'current_theme': self.current_theme,
            'materials_theme': self.materials_theme,
            'cargo_capacity': self.cargo_capacity,
            'capi_refresh_interval': self.capi_auto_refresh.get_interval(),
            'window_geometry': self.geometry()
        })
        save_gui_settings(settings)
        logger.debug("All settings saved")

    def update_capi_refresh_interval(self, minutes: int):
        self.capi_auto_refresh.set_interval(minutes)
        self.save_settings()
        logger.info(f"CAPI refresh interval updated to {minutes} minutes")

    def force_refresh_capi(self):
        self.capi_auto_refresh.force_refresh()

    def on_close(self):
        try:
            if self.winfo_exists():
                settings = load_gui_settings()
                settings['window_was_open'] = False
                try:
                    settings['window_geometry'] = self.geometry()
                except Exception:
                    pass
                save_gui_settings(settings)
                logger.info("Window closed")
        except Exception as e:
            logger.error(f"Error during window close: {e}")
        finally:
            self.destroy()

    def reorder_columns(self, new_order):
        self.column_order = [col for col in new_order if col in self.column_visibility]
        for col in self.column_visibility:
            if col not in self.column_order:
                self.column_order.append(col)
        self.refresh_columns()
        self.save_settings()

    def refresh(self):
        """Refresh the station list and display."""
        current_selection = self.station_var.get()
        data = load_facility_requirements()
        self.data = data
        
        systems = set()
        for station, info in data.items():
            system_name = info.get('system', 'Unknown')
            if system_name:
                systems.add(system_name)
        
        current_system = self.system_var.get()
        system_values = ["All Systems"] + sorted(list(systems))
        self.system_dropdown['values'] = system_values
        
        if current_system in system_values:
            self.system_var.set(current_system)
        else:
            self.system_var.set("All Systems")
            self.selected_system = "All Systems"

        display = [
            (
              (full.split(':', 1)[-1].strip() if ':' in full else 
               full.split(';', 1)[-1].strip() if ';' in full else full),
              full
            )
            for full in data
            if self.selected_system == "All Systems" or 
               self.data.get(full, {}).get('system', '') == self.selected_system
        ]
        
        if self.sort_by_system:
            display.sort(key=lambda x: (self.data.get(x[1], {}).get('system', ''), x[0]))
        else:
            display.sort(key=lambda x: x[0])
            
        self.station_map = {name: full for name, full in display}
        values = [name for name, _ in display]
        self.dropdown['values'] = values

        if values:
            if current_selection in values:
                self.station_var.set(current_selection)
            else:
                self.station_var.set(values[0])
            self.display_station()
        else:
            self.tree.delete(*self.tree.get_children())
            self.transport_label['text'] = ""
            self.cargo_label['text'] = ""

    def calculate_completion_percentage(self, materials):
        total_required = 0
        total_provided = 0
        
        for mat, vals in materials.items():
            req = vals['RequiredAmount']
            prov = vals['ProvidedAmount']
            total_required += req
            total_provided += min(prov, req)
        
        if total_required == 0:
            return 100.0
            
        return (total_provided / total_required) * 100.0
        
    def calculate_required_trips(self, materials):
        total_needed = 0
        for mat, vals in materials.items():
            req = vals['RequiredAmount']
            prov = vals['ProvidedAmount']
            if prov < req:
                total_needed += (req - prov)
        
        if total_needed <= 0:
            return 0
        
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
        cargo_items = load_cargo_data()

        total_cargo = get_total_ship_cargo()
        self.cargo_label['text'] = f"Current Cargo: {total_cargo}/{self.cargo_capacity} tons"

        market_lookup = {i.get('Name'): i for i in market_items}
        cargo_lookup = {i.get('Name'): i for i in cargo_items}

        self.market_name_label['text'] = market_name or 'N/A'
        self.carrier_label['text'] = carrier_tracker.carrier_name or 'N/A'

        visible_materials = []
        for mat, vals in materials.items():
            req = vals['RequiredAmount']
            prov = vals['ProvidedAmount']
            if not (self.hide_provided and prov >= req):
                visible_materials.append((mat, vals))

        for idx, (mat, vals) in enumerate(visible_materials):
            req = vals['RequiredAmount']
            prov = vals['ProvidedAmount']
            safeMat = mat.replace("$", "").replace("_name;", "")
            locName = vals['Name_Localised']
            need = req - prov
            stock_qty = market_lookup.get(mat, {}).get('Stock', 0)
            for_sale = f"✔ {stock_qty}" if stock_qty > 0 else ''
            fc_qty = carrier_tracker.get_quantity(safeMat)
            ship_qty = cargo_lookup.get(safeMat, {}).get('Count', 0)
            short = max(0, need - (fc_qty + ship_qty))
            
            base_tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            
            if prov >= req:
                status_tag = 'fullDelivery'
            elif prov == 0:
                status_tag = 'noDelivery'
            else:
                status_tag = base_tag
            
            self.tree.insert("", "end", values=(locName, req, prov, need, for_sale,
                                                   fc_qty, ship_qty, short), tags=(base_tag, status_tag))
            
        required_trips = self.calculate_required_trips(materials)
        completion_percentage = self.calculate_completion_percentage(materials)
        
        if required_trips > 0:
            self.transport_label['text'] = f"Est. trips: {required_trips} (based on {self.cargo_capacity} ton capacity) - Completion: {completion_percentage:.1f}%"
        else:
            self.transport_label['text'] = f"All materials delivered! - Completion: 100%"


# --- Update Notification Dialog ---
class UpdateNotificationDialog(tk.Toplevel):
    """Dialog that notifies user about available updates in Polish."""
    
    def __init__(self, parent, current_version, latest_version, latest_release_data):
        super().__init__(parent)
        self.parent = parent
        self.current_version = current_version
        self.latest_version = latest_version
        self.latest_release_data = latest_release_data
        
        self.title("Dostępna aktualizacja")
        self.transient(parent)
        self.grab_set()
        
        if hasattr(parent, 'current_theme') and hasattr(parent, 'THEME_COLORS'):
            theme_colors = parent.THEME_COLORS[parent.current_theme]
            self.configure(bg=theme_colors["background"])
            fg_color = theme_colors["foreground"]
            button_bg = theme_colors["button_bg"]
            button_fg = theme_colors["button_fg"]
        else:
            self.configure(bg="#1a1a1a")
            fg_color = "#ff8500"
            button_bg = "#333333"
            button_fg = "#ffffff"
        
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, 
                  text=f"Dostępna jest nowa wersja Architect Tracker!",
                  font=("Segoe UI", 12, "bold")).pack(pady=(0, 10))
        
        ttk.Label(frame, 
                  text=f"Twoja wersja: {current_version}").pack(anchor="w", pady=2)
        
        ttk.Label(frame, 
                  text=f"Dostępna wersja: {latest_version}",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=2)
        
        desc_frame = ttk.Frame(frame)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        desc_scrollbar = ttk.Scrollbar(desc_frame)
        desc_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        desc_text = tk.Text(desc_frame, height=6, width=50, wrap=tk.WORD, 
                          yscrollcommand=desc_scrollbar.set)
        desc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        desc_scrollbar.config(command=desc_text.yview)
        
        desc = self.latest_release_data.get('description', 'Brak informacji o zmianach.')
        desc_text.insert(tk.END, desc)
        desc_text.config(state=tk.DISABLED)
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(button_frame, text="Otwórz Ustawienia", 
                 command=self.open_settings).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Pomiń tę wersję", 
                 command=self.skip_version).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Zamknij", 
                 command=self.destroy).pack(side=tk.RIGHT, padx=5)
        
        self.update_idletasks()
        if parent:
            x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        else:
            x = (self.winfo_screenwidth() - self.winfo_width()) // 2
            y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def open_settings(self):
        if hasattr(self.parent, 'open_settings'):
            self.parent.open_settings()
            if hasattr(self.parent, 'settings_window') and self.parent.settings_window:
                if hasattr(self.parent.settings_window, 'notebook'):
                    for i in range(self.parent.settings_window.notebook.index('end')):
                        if self.parent.settings_window.notebook.tab(i, 'text') == 'Updates':
                            self.parent.settings_window.notebook.select(i)
                            break
        self.destroy()
    
    def skip_version(self):
        save_skipped_version(self.latest_version)
        self.destroy()
