import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Callable, List, Optional, Tuple
import threading

# Import the updater module
import updater
# Import bug report module
import bug_report
from settings import get_overlay_settings, save_overlay_settings, OVERLAY_COLORS

class SettingsWindow:
    """Class that handles the settings window for Architect Tracker plugin."""
    
    def __init__(self, parent, 
                 # Theme-related properties
                 theme_constants: Dict,
                 current_theme: int,
                 materials_theme: int,
                 
                 # Settings data
                 column_visibility: Dict[str, bool],
                 column_order: List[str],
                 hide_provided: bool,
                 sort_by_system: bool,
                 cargo_capacity: int,
                 data: Dict,
                 
                 # Window geometry settings
                 window_width: int = 800,
                 window_height: int = 400,
                 window_x: int = 0,
                 window_y: int = 0,
                 
                 # CAPI refresh settings
                 capi_refresh_interval: int = 60,
                 
                 # Callback functions
                 toggle_column_callback: Callable[[str, bool], None] = None,
                 reorder_columns_callback: Callable[[List[str]], None] = None,
                 toggle_hide_provided_callback: Callable[[], None] = None,
                 toggle_sort_mode_callback: Callable[[], None] = None,
                 update_cargo_capacity_callback: Callable[[int], None] = None,
                 remove_station_callback: Callable[[str], None] = None,
                 change_theme_callback: Callable[[int], None] = None,
                 change_materials_theme_callback: Callable[[int], None] = None,
                 update_window_size_callback: Callable[[int, int, int, int], None] = None,
                 reset_window_size_callback: Callable[[], None] = None,
                 force_refresh_capi_callback: Callable[[], None] = None,
                 update_capi_interval_callback: Callable[[int], None] = None):
        """
        Initialize the settings window.
        
        Args:
            parent: The parent window
            theme_constants: Dictionary containing theme constants and colors
            current_theme: Current theme index
            materials_theme: Current materials theme index
            column_visibility: Dictionary mapping column names to visibility
            hide_provided: Whether to hide fully provided materials
            sort_by_system: Whether to sort stations by system
            cargo_capacity: Ship cargo capacity in tons
            data: Dictionary containing station data
            toggle_column_callback: Callback for toggling column visibility
            toggle_hide_provided_callback: Callback for toggling hide provided setting
            toggle_sort_mode_callback: Callback for toggling sort mode
            update_cargo_capacity_callback: Callback for updating cargo capacity
            remove_station_callback: Callback for removing a station
            change_theme_callback: Callback for changing theme
            change_materials_theme_callback: Callback for changing materials theme
        """
        self.parent = parent
        
        # Store theme constants
        self.THEME_COLORS = theme_constants["THEME_COLORS"]
        self.THEME_BLACK = theme_constants["THEME_BLACK"]
        self.THEME_WHITE = theme_constants["THEME_WHITE"]
        
        # Store current settings
        self.current_theme = current_theme
        self.materials_theme = materials_theme
        self.column_visibility = column_visibility
        self.column_order = column_order
        self.hide_provided = hide_provided
        self.sort_by_system = sort_by_system
        self.cargo_capacity = cargo_capacity
        self.data = data
        
        # Store window geometry settings
        self.window_width = window_width
        self.window_height = window_height
        self.window_x = window_x
        self.window_y = window_y
        
        # Store callback functions
        self.toggle_column_callback = toggle_column_callback
        self.reorder_columns_callback = reorder_columns_callback
        self.toggle_hide_provided_callback = toggle_hide_provided_callback
        self.toggle_sort_mode_callback = toggle_sort_mode_callback
        self.update_cargo_capacity_callback = update_cargo_capacity_callback
        self.remove_station_callback = remove_station_callback
        self.change_theme_callback = change_theme_callback
        self.change_materials_theme_callback = change_materials_theme_callback
        self.update_window_size_callback = update_window_size_callback
        self.reset_window_size_callback = reset_window_size_callback
        self.force_refresh_capi_callback = force_refresh_capi_callback
        self.update_capi_interval_callback = update_capi_interval_callback
        self.capi_refresh_interval = capi_refresh_interval
        
        # Create window
        self.window = None
        self.create_window()
    
    def create_window(self):
        """Create and show the settings window."""
        # Close existing window if open
        if self.window and self.window.winfo_exists():
            self.window.destroy()
            
        # Create new settings window with proper theme
        self.window = tk.Toplevel(self.parent)
        self.window.transient(self.parent)
        self.window.title("Settings")
        
        # Apply current theme to the settings window
        theme_colors = self.THEME_COLORS[self.current_theme]
        self.window.configure(bg=theme_colors["background"])
        
        # Create a tabbed interface instead of a scrollable frame
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create tabs: Display Settings, Theme Settings, and Station Management
        self.display_tab = ttk.Frame(self.notebook, style="Main.TFrame")
        self.theme_tab = ttk.Frame(self.notebook, style="Main.TFrame")
        self.window_tab = ttk.Frame(self.notebook, style="Main.TFrame")
        self.station_tab = ttk.Frame(self.notebook, style="Main.TFrame")
        
        # Add tabs to the notebook (Window Settings is hidden by default)
        self.notebook.add(self.display_tab, text="Display Settings")
        self.notebook.add(self.theme_tab, text="Theme")
        self.notebook.add(self.station_tab, text="Station Management")
        
        # Window Settings tab is created but not added - hidden unless debug mode is enabled
        self.window_settings_visible = False
        
        # Create a fourth tab for Updates
        self.update_tab = ttk.Frame(self.notebook, style="Main.TFrame")
        self.notebook.add(self.update_tab, text="Updates")
        
        # Create a fifth tab for Info
        self.info_tab = ttk.Frame(self.notebook, style="Main.TFrame")
        self.notebook.add(self.info_tab, text="Info")
        
        # --------- INFO TAB ---------
        # Add title
        ttk.Label(self.info_tab, 
                  text="Architect Tracker", 
                  style="TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor="center", padx=10, pady=(20, 10))
        
        # Add developer information
        info_text = "This is a version of Architect Tracker developed by kol19pl, originally created by kfpopeye."
        ttk.Label(self.info_tab, 
                  text=info_text,
                  style="TLabel",
                  wraplength=400).pack(anchor="center", padx=10, pady=(10, 20))
        
        # Add current version (double-click to toggle debug mode / Window Settings tab)
        version_text = f"Current Version: {updater.get_current_version()}"
        version_label = ttk.Label(self.info_tab,
                  text=version_text,
                  style="TLabel")
        version_label.pack(anchor="center", padx=10, pady=(5, 5))
        version_label.bind("<Double-Button-1>", lambda e: self.toggle_window_settings_tab())
        
        # Debug mode status (hidden by default)
        self.debug_status_label = ttk.Label(self.info_tab,
                  text="",
                  style="TLabel",
                  font=("Segoe UI", 8))
        self.debug_status_label.pack(anchor="center", padx=10, pady=(0, 20))
        
        # --------- UPDATES TAB ---------
        ttk.Label(self.update_tab, text=f"Current Version: {updater.get_current_version()}", style="TLabel").pack(anchor="w", padx=10, pady=(10, 5))

        # Create frame for update controls
        update_frame = ttk.Frame(self.update_tab, style="Main.TFrame")
        update_frame.pack(anchor="w", padx=10, pady=5, fill="x")

        # Button to check for updates
        ttk.Button(update_frame, text="Check for Updates", command=self.check_for_updates, style="TButton").pack(side="left", padx=(0, 5))
        
        # Add Report Bugs button
        ttk.Button(update_frame, text="Report Bugs", command=self.show_bug_report, style="TButton").pack(side="left", padx=(5, 5))

        # Version dropdown for selection
        ttk.Label(self.update_tab, text="Available Versions:", style="TLabel").pack(anchor="w", padx=10, pady=(10, 5))
        self.version_var = tk.StringVar()
        self.version_dropdown = ttk.Combobox(self.update_tab, textvariable=self.version_var, state="readonly", width=30)
        self.version_dropdown.pack(anchor="w", padx=10, pady=(0, 5), fill="x")

        # Store version data for lookup
        self.available_releases = []

        # Update button
        self.update_button = ttk.Button(self.update_tab, text="Download Selected Version", command=self.download_update, state="disabled", style="TButton")
        self.update_button.pack(anchor="w", padx=10, pady=(5, 10))

        # Progress bar and status
        self.progress_frame = ttk.Frame(self.update_tab, style="Main.TFrame")
        self.progress_frame.pack(anchor="w", padx=10, pady=5, fill="x", expand=True)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", expand=True, pady=(0, 5))

        self.status_label = ttk.Label(self.progress_frame, text="", style="TLabel")
        self.status_label.pack(anchor="w", pady=5)
        
        # --------- DISPLAY SETTINGS TAB ---------
        ttk.Label(self.display_tab, text="Select columns to display:", style="TLabel").pack(padx=10, pady=5, anchor="w")
        
        # Column visibility checkboxes
        for idx, col in enumerate(self.column_order):
            visible = self.column_visibility.get(col, True)
            var = tk.BooleanVar(value=visible)
            if idx == 0:
                chk = ttk.Checkbutton(
                    self.display_tab,
                    text=col,
                    variable=var,
                    state="disabled",
                    style="TCheckbutton"
                )
                var.set(True)
            else:
                chk = ttk.Checkbutton(
                    self.display_tab,
                    text=col,
                    variable=var,
                    command=lambda c=col, v=var: self.toggle_column(c, v.get()),
                    style="TCheckbutton"
                )
            chk.pack(anchor="w", padx=10)

        ttk.Label(self.display_tab, text="Change column order:", style="TLabel").pack(anchor="w", padx=10, pady=(10, 5))
        order_frame = ttk.Frame(self.display_tab, style="Main.TFrame")
        order_frame.pack(anchor="w", padx=10, pady=(0, 5), fill="x")

        self.order_listbox = tk.Listbox(order_frame, height=len(self.column_order), activestyle="none", exportselection=False)
        for col in self.column_order:
            self.order_listbox.insert(tk.END, col)
        self.order_listbox.pack(side="left", fill="y")

        button_frame = ttk.Frame(order_frame, style="Main.TFrame")
        button_frame.pack(side="left", padx=5, fill="y")
        ttk.Button(button_frame, text="Move Up", command=self.move_column_up, style="TButton").pack(fill="x", pady=2)
        ttk.Button(button_frame, text="Move Down", command=self.move_column_down, style="TButton").pack(fill="x", pady=2)
        
        # Add gameplay settings to Display tab
        ttk.Separator(self.display_tab, orient="horizontal").pack(fill="x", padx=10, pady=10)
        ttk.Label(self.display_tab, text="Display options:", style="TLabel").pack(anchor="w", padx=10, pady=(5, 5))
        
        # Hide provided materials option
        self.hide_var = tk.BooleanVar(value=self.hide_provided)
        chk_hide = ttk.Checkbutton(
            self.display_tab,
            text="Hide fully provided materials",
            variable=self.hide_var,
            command=self.toggle_hide_provided,
            style="TCheckbutton"
        )
        chk_hide.pack(anchor="w", padx=10, pady=(5, 0))
        
        # Sort by system option
        self.sort_var = tk.BooleanVar(value=self.sort_by_system)
        chk_sort = ttk.Checkbutton(
            self.display_tab,
            text="Sort stations by system",
            variable=self.sort_var,
            command=self.toggle_sort_mode,
            style="TCheckbutton"
        )
        chk_sort.pack(anchor="w", padx=10, pady=(5, 0))
        
        # Cargo capacity setting
        ttk.Separator(self.display_tab, orient="horizontal").pack(fill="x", padx=10, pady=10)
        ttk.Label(self.display_tab, text="Ship cargo capacity (tons):", style="TLabel").pack(anchor="w", padx=10, pady=(5, 0))
        cargo_frame = ttk.Frame(self.display_tab, style="Main.TFrame")
        cargo_frame.pack(anchor="w", padx=10, pady=(5, 0), fill="x")
        
        self.cargo_var = tk.StringVar(value=str(self.cargo_capacity))
        cargo_entry = ttk.Entry(cargo_frame, width=6, textvariable=self.cargo_var, style="TEntry")
        cargo_entry.pack(side="left", padx=(0, 5))
        
        ttk.Button(cargo_frame, text="Apply", command=self.update_cargo_capacity, style="TButton").pack(side="left")
        
        # --------- THEME SETTINGS TAB ---------
        # Main window theme selection
        ttk.Label(self.theme_tab, text="Main window theme:", style="TLabel").pack(anchor="w", padx=10, pady=(10, 5))
        
        theme_frame = ttk.Frame(self.theme_tab, style="Main.TFrame")
        theme_frame.pack(anchor="w", padx=10, pady=(0, 5), fill="x")
        
        self.theme_var = tk.IntVar(value=self.current_theme)
        
        # Black theme radio button
        ttk.Radiobutton(
            theme_frame, 
            text="Black theme", 
            variable=self.theme_var, 
            value=self.THEME_BLACK,
            command=self.change_theme,
            style="TRadiobutton"
        ).pack(anchor="w", padx=5, pady=2)
        
        # White theme radio button
        ttk.Radiobutton(
            theme_frame, 
            text="White theme", 
            variable=self.theme_var, 
            value=self.THEME_WHITE,
            command=self.change_theme,
            style="TRadiobutton"
        ).pack(anchor="w", padx=5, pady=2)
        
        # Materials frame theme selection
        ttk.Separator(self.theme_tab, orient="horizontal").pack(fill="x", padx=10, pady=10)
        ttk.Label(self.theme_tab, text="Materials display theme:", style="TLabel").pack(anchor="w", padx=10, pady=(5, 5))
        
        materials_theme_frame = ttk.Frame(self.theme_tab, style="Main.TFrame")
        materials_theme_frame.pack(anchor="w", padx=10, pady=(0, 5), fill="x")
        
        self.materials_theme_var = tk.IntVar(value=self.materials_theme)
        
        # Black theme radio button for materials
        ttk.Radiobutton(
            materials_theme_frame, 
            text="Black theme", 
            variable=self.materials_theme_var, 
            value=self.THEME_BLACK,
            command=self.change_materials_theme,
            style="TRadiobutton"
        ).pack(anchor="w", padx=5, pady=2)
        
        # White theme radio button for materials
        ttk.Radiobutton(
            materials_theme_frame, 
            text="White theme", 
            variable=self.materials_theme_var, 
            value=self.THEME_WHITE,
            command=self.change_materials_theme,
            style="TRadiobutton"
        ).pack(anchor="w", padx=5, pady=2)

        # --------- WINDOW SETTINGS TAB ---------
        # Current window info
        ttk.Label(self.window_tab, text="Current Window Size and Position:", style="TLabel").pack(anchor="w", padx=10, pady=(10, 5))
        
        current_info_frame = ttk.Frame(self.window_tab, style="Main.TFrame")
        current_info_frame.pack(anchor="w", padx=10, pady=(0, 5), fill="x")
        
        self.current_info_label = ttk.Label(current_info_frame, text="", style="TLabel")
        self.current_info_label.pack(anchor="w", side="left", padx=(0, 5))
        
        ttk.Button(current_info_frame, text="Refresh", command=self.refresh_current_info, style="TButton").pack(side="left")
        
        # Refresh initial info after button is created
        self.window.update_idletasks()
        self.refresh_current_info()
        
        # Separator
        ttk.Separator(self.window_tab, orient="horizontal").pack(fill="x", padx=10, pady=10)
        
        # Set custom size and position
        ttk.Label(self.window_tab, text="Set Custom Window Size and Position:", style="TLabel").pack(anchor="w", padx=10, pady=(10, 5))
        
        # Window width setting
        width_frame = ttk.Frame(self.window_tab, style="Main.TFrame")
        width_frame.pack(anchor="w", padx=10, pady=5, fill="x")
        ttk.Label(width_frame, text="Width (pixels):", style="TLabel").pack(side="left", padx=(0, 5))
        self.width_var = tk.StringVar(value=str(self.window_width))
        width_entry = ttk.Entry(width_frame, width=10, textvariable=self.width_var, style="TEntry")
        width_entry.pack(side="left", padx=(0, 5))
        
        # Window height setting
        height_frame = ttk.Frame(self.window_tab, style="Main.TFrame")
        height_frame.pack(anchor="w", padx=10, pady=5, fill="x")
        ttk.Label(height_frame, text="Height (pixels):", style="TLabel").pack(side="left", padx=(0, 5))
        self.height_var = tk.StringVar(value=str(self.window_height))
        height_entry = ttk.Entry(height_frame, width=10, textvariable=self.height_var, style="TEntry")
        height_entry.pack(side="left", padx=(0, 5))
        
        # Window X position
        x_frame = ttk.Frame(self.window_tab, style="Main.TFrame")
        x_frame.pack(anchor="w", padx=10, pady=5, fill="x")
        ttk.Label(x_frame, text="X Position (pixels):", style="TLabel").pack(side="left", padx=(0, 5))
        self.x_var = tk.StringVar(value=str(self.window_x))
        x_entry = ttk.Entry(x_frame, width=10, textvariable=self.x_var, style="TEntry")
        x_entry.pack(side="left", padx=(0, 5))
        
        # Window Y position
        y_frame = ttk.Frame(self.window_tab, style="Main.TFrame")
        y_frame.pack(anchor="w", padx=10, pady=5, fill="x")
        ttk.Label(y_frame, text="Y Position (pixels):", style="TLabel").pack(side="left", padx=(0, 5))
        self.y_var = tk.StringVar(value=str(self.window_y))
        y_entry = ttk.Entry(y_frame, width=10, textvariable=self.y_var, style="TEntry")
        y_entry.pack(side="left", padx=(0, 5))
        
        # Info label
        ttk.Separator(self.window_tab, orient="horizontal").pack(fill="x", padx=10, pady=10)
        info_label = ttk.Label(self.window_tab, 
                               text="Minimum size: 400x300 pixels",
                               style="TLabel")
        info_label.pack(anchor="w", padx=10, pady=(5, 10))
        
        # Apply button
        button_frame = ttk.Frame(self.window_tab, style="Main.TFrame")
        button_frame.pack(anchor="w", padx=10, pady=5, fill="x")
        ttk.Button(button_frame, text="Apply Settings", command=self.apply_window_settings, style="TButton").pack(side="left", padx=(0, 5))
        ttk.Button(button_frame, text="Reset to Default", command=self.reset_window_settings, style="TButton").pack(side="left")

        # --------- STATION MANAGEMENT TAB ---------

        # --------- STATION MANAGEMENT TAB ---------
        ttk.Label(self.station_tab, text="Remove station from tracking:", style="TLabel").pack(anchor="w", padx=10, pady=(10, 5))
        
        # System selection for filtering stations
        system_frame = ttk.Frame(self.station_tab, style="Main.TFrame")
        system_frame.pack(anchor="w", padx=10, pady=(5, 5), fill="x")
        ttk.Label(system_frame, text="System:", style="TLabel").pack(side="left", padx=(0, 5))
        
        # Extract all unique system names from the data
        systems = set()
        for info in self.data.values():
            system_name = info.get('system', 'Unknown')
            if system_name:
                systems.add(system_name)
        
        # Prepare system dropdown
        self.system_var = tk.StringVar(value="All Systems")  # Default to "All Systems"
        self.system_dropdown = ttk.Combobox(system_frame, textvariable=self.system_var, state="readonly", width=25)
        system_values = ["All Systems"] + sorted(list(systems))
        self.system_dropdown['values'] = system_values
        self.system_dropdown.pack(side="left", padx=(0, 5))
        self.system_dropdown.bind("<<ComboboxSelected>>", lambda e: self.filter_stations_by_system())
        
        # Station removal controls
        removal_frame = ttk.Frame(self.station_tab, style="Main.TFrame")
        removal_frame.pack(anchor="w", padx=10, pady=(10, 5), fill="x")
        ttk.Label(removal_frame, text="Station:", style="TLabel").pack(side="left", padx=(0, 5))
        
        self.remove_station_var = tk.StringVar()
        self.remove_station_dropdown = ttk.Combobox(removal_frame, textvariable=self.remove_station_var, state="readonly", width=25)
        self.remove_station_dropdown.pack(side="left", padx=(0, 5))
        
        # Remove button
        ttk.Button(removal_frame, text="Remove", command=self.remove_station, style="TButton").pack(side="left")
        
        # --------- OVERLAY TAB ---------
        self.overlay_tab = ttk.Frame(self.notebook, style="Main.TFrame")
        self.notebook.add(self.overlay_tab, text="Overlay")
        self._build_overlay_tab()

        # --------- CAPI REFRESH SECTION ---------
        ttk.Separator(self.station_tab, orient="horizontal").pack(fill="x", padx=10, pady=10)
        ttk.Label(self.station_tab, text="Fleet Carrier Data Refresh:", style="TLabel").pack(anchor="w", padx=10, pady=(5, 5))
        
        # Manual refresh button
        capi_refresh_frame = ttk.Frame(self.station_tab, style="Main.TFrame")
        capi_refresh_frame.pack(anchor="w", padx=10, pady=5, fill="x")
        
        self.capi_refresh_button = ttk.Button(capi_refresh_frame, text="Refresh Fleet Carrier Data", command=self.force_capi_refresh, style="TButton")
        self.capi_refresh_button.pack(side="left", padx=(0, 10))
        
        self.capi_status_label = ttk.Label(capi_refresh_frame, text="", style="TLabel")
        self.capi_status_label.pack(side="left")
        
        # Auto-refresh interval setting
        auto_refresh_frame = ttk.Frame(self.station_tab, style="Main.TFrame")
        auto_refresh_frame.pack(anchor="w", padx=10, pady=5, fill="x")
        
        ttk.Label(auto_refresh_frame, text="Auto-refresh interval (minutes):", style="TLabel").pack(side="left", padx=(0, 5))
        self.capi_interval_var = tk.StringVar(value=str(self.capi_refresh_interval))
        capi_interval_entry = ttk.Entry(auto_refresh_frame, width=6, textvariable=self.capi_interval_var, style="TEntry")
        capi_interval_entry.pack(side="left", padx=(0, 5))
        
        ttk.Button(auto_refresh_frame, text="Apply", command=self.apply_capi_interval, style="TButton").pack(side="left", padx=(0, 5))
        
        ttk.Label(auto_refresh_frame, text="(0 = disable auto-refresh)", style="TLabel").pack(side="left")
        
        # Prepare the mapping from display names to full station keys
        self.remove_station_map = {}  # Map display names to full station keys
        self.system_station_data = {}  # Store station data by system for filtering
        
        # Initialize the station dropdown with all stations
        self.update_station_data()
        self.filter_stations_by_system()
        
        # Position settings window over parent
        self.window.update_idletasks()
        px = self.parent.winfo_x()
        py = self.parent.winfo_y() 
        pw = self.parent.winfo_width()
        ph = self.parent.winfo_height()
        sw = self.window.winfo_width()
        sh = self.window.winfo_height()
        x = px + (pw - sw) // 2
        y = py + (ph - sh) // 2
        self.window.geometry(f"+{x}+{y}")
        
        # Make sure the window is not too small
        self.window.minsize(400, 450)

    def toggle_column(self, column, is_visible: bool):
        """Toggle column visibility in the main window."""
        self.toggle_column_callback(column, is_visible)
    
    def toggle_hide_provided(self):
        """Toggle hide provided setting in the main window."""
        self.hide_provided = self.hide_var.get()
        self.toggle_hide_provided_callback(self.hide_provided)
    
    def toggle_sort_mode(self):
        """Toggle sort mode in the main window."""
        self.sort_by_system = self.sort_var.get()
        self.toggle_sort_mode_callback()

    def move_column_up(self):
        selected = self.order_listbox.curselection()
        if not selected:
            return
        idx = selected[0]
        if idx == 0:
            return
        self.column_order[idx - 1], self.column_order[idx] = self.column_order[idx], self.column_order[idx - 1]
        self.update_order_listbox()
        self.order_listbox.select_set(idx - 1)
        self.reorder_columns()

    def move_column_down(self):
        selected = self.order_listbox.curselection()
        if not selected:
            return
        idx = selected[0]
        if idx >= len(self.column_order) - 1:
            return
        self.column_order[idx + 1], self.column_order[idx] = self.column_order[idx], self.column_order[idx + 1]
        self.update_order_listbox()
        self.order_listbox.select_set(idx + 1)
        self.reorder_columns()

    def update_order_listbox(self):
        self.order_listbox.delete(0, tk.END)
        for col in self.column_order:
            self.order_listbox.insert(tk.END, col)

    def reorder_columns(self):
        if self.reorder_columns_callback:
            self.reorder_columns_callback(self.column_order)
    
    def update_cargo_capacity(self):
        """Update cargo capacity in the main window."""
        try:
            capacity = int(self.cargo_var.get())
            if capacity < 1:
                capacity = 1  # Ensure minimum capacity
            
            self.cargo_capacity = capacity
            self.update_cargo_capacity_callback(capacity)
            
            # Add logging to help debug
            print(f"Settings window - Cargo capacity updated to: {capacity}")
        except ValueError:
            # Reset to previous value if entry is not a valid number
            self.cargo_var.set(str(self.cargo_capacity))
            print("Settings window - Invalid cargo capacity value provided")
            
    def update_station_data(self):
        """Update the internal station data structure for filtering."""
        self.remove_station_map = {}  # Map display names to full station keys
        self.system_station_data = {"All Systems": []}  # Store station data by system
        
        for station_key, info in self.data.items():
            # Use same display format as main UI
            display_name = (station_key.split(':', 1)[-1].strip() if ':' in station_key else 
                           station_key.split(';', 1)[-1].strip() if ';' in station_key else station_key)
            system_name = info.get('system', 'Unknown')
            
            # Use display name without system in dropdown for cleaner display
            display_text = display_name
            
            # Store data by system for filtering
            if system_name not in self.system_station_data:
                self.system_station_data[system_name] = []
            
            # Add to the system-specific list
            self.system_station_data[system_name].append((display_text, station_key))
            
            # Also add to the "All Systems" list
            self.system_station_data["All Systems"].append((display_text, station_key))
            
            # Update the mapping
            self.remove_station_map[display_text] = station_key
    
    def filter_stations_by_system(self):
        """Filter stations by the selected system."""
        selected_system = self.system_var.get()
        
        # Get stations for the selected system
        station_data = self.system_station_data.get(selected_system, [])
        
        # Sort stations alphabetically
        station_data.sort(key=lambda x: x[0])
        
        # Update dropdown values
        station_values = [name for name, _ in station_data]
        self.remove_station_dropdown['values'] = station_values
        
        # Select first item if available
        if station_values:
            self.remove_station_dropdown.current(0)
            
    def remove_station(self):
        """Remove a station from tracking."""
        selected = self.remove_station_var.get()
        if selected and selected in self.remove_station_map:
            station_key = self.remove_station_map[selected]
            self.remove_station_callback(station_key)
            
            # Update our internal data structures
            if station_key in self.data:
                del self.data[station_key]
                
            # Refresh the station dropdowns
            self.update_station_data()
            self.filter_stations_by_system()
    
    def change_theme(self):
        """Change the main window theme."""
        new_theme = self.theme_var.get()
        self.current_theme = new_theme
        
        # Update settings window with new theme
        self.update_theme()
        
        # Call the callback to update the main window
        self.change_theme_callback(new_theme)
        
        # Add logging to help debug
        print(f"Settings window - Changed main theme to: {new_theme}")
    
    def change_materials_theme(self):
        """Change the materials display theme."""
        new_theme = self.materials_theme_var.get()
        self.materials_theme = new_theme
        self.change_materials_theme_callback(new_theme)
        
        # Add logging to help debug
        print(f"Settings window - Changed materials theme to: {new_theme}")
    
    def update_theme(self):
        """Update the settings window theme when the main theme changes."""
        if not self.window or not self.window.winfo_exists():
            return
            
        # Get theme colors for current theme
        theme_colors = self.THEME_COLORS[self.current_theme]
        
        # Update settings window background
        self.window.configure(bg=theme_colors["background"])
    
    def check_for_updates(self):
        """Check for available updates from GitHub."""
        # Disable the button during check
        for widget in self.update_tab.winfo_children():
            if isinstance(widget, ttk.Button) and widget.cget("text") == "Check for Updates":
                widget.configure(state="disabled")
        
        self.status_label.configure(text="Checking for updates...")
        self.progress_var.set(0)
        
        # Use threading to avoid freezing the UI
        def _check_worker():
            success, result = updater.get_available_releases()
            
            # Update UI in the main thread
            self.window.after(0, lambda: self._process_update_check_result(success, result))
        
        check_thread = threading.Thread(target=_check_worker)
        check_thread.daemon = True
        check_thread.start()

    def _process_update_check_result(self, success, result):
        """Process the result of the update check."""
        # Re-enable the check button
        for widget in self.update_tab.winfo_children():
            if isinstance(widget, ttk.Button) and widget.cget("text") == "Check for Updates":
                widget.configure(state="normal")
        
        if not success:
            self.status_label.configure(text=f"Error: {result}")
            self.update_button.configure(state="disabled")
            return
        
        # Store release information
        self.available_releases = result
        
        if not self.available_releases:
            self.status_label.configure(text="No releases found.")
            self.update_button.configure(state="disabled")
            return
        
        # Populate dropdown with version information
        version_options = []
        current_version = updater.get_current_version()
        has_newer_version = False
        
        for release in self.available_releases:
            version_str = release['version']
            is_newer = updater.is_newer_version(current_version, version_str)
            
            if is_newer:
                version_options.append(f"{version_str} (New!)")
                has_newer_version = True
            else:
                version_options.append(version_str)
        
        self.version_dropdown['values'] = version_options
        
        # Select the latest version by default
        if version_options:
            self.version_dropdown.current(0)
            self.update_button.configure(state="normal")
        
        # Update status
        if has_newer_version:
            self.status_label.configure(text="New version available!")
        else:
            self.status_label.configure(text="You have the latest version.")

    def download_update(self):
        """Download and install the selected version."""
        # Get selected version
        selected = self.version_var.get()
        if not selected:
            return
        
        # Remove " (New!)" suffix if present
        if "(New!)" in selected:
            selected = selected.split(" (New!)")[0]
        
        # Find the release data
        release_data = None
        for release in self.available_releases:
            if release['version'] == selected:
                release_data = release
                break
        
        if not release_data:
            self.status_label.configure(text="Error: Selected version not found.")
            return
        
        # Confirm update
        current_version = updater.get_current_version()
        message = f"Are you sure you want to update from version {current_version} to {selected}?\n\n"
        message += "The application will need to restart after the update."
        
        if not messagebox.askyesno("Confirm Update", message, parent=self.window):
            return
        
        # Disable controls during update
        self.update_button.configure(state="disabled")
        self.version_dropdown.configure(state="disabled")
        
        # Start the update
        updater.download_and_install_update(
            release_data,
            progress_callback=self._update_progress,
            completion_callback=self._update_complete
        )

    def _update_progress(self, progress, message):
        """Update the progress bar and status message."""
        if progress < 0:  # Error
            self.progress_var.set(0)
        else:
            self.progress_var.set(progress)
        self.status_label.configure(text=message)

    def _update_complete(self, success, message):
        """Handle update completion."""
        if success:
            messagebox.showinfo("Update Complete", message, parent=self.window)
            # Re-enable controls
            self.version_dropdown.configure(state="readonly")
        else:
            messagebox.showerror("Update Failed", message, parent=self.window)
            self.update_button.configure(state="normal")
            self.version_dropdown.configure(state="readonly")

    def refresh_current_info(self):
        """Refresh and display current window size and position."""
        try:
            # Get parent window geometry
            geometry = self.parent.geometry()
            # Parse geometry string: WIDTHxHEIGHT+X+Y
            parts = geometry.replace('x', '+').split('+')
            if len(parts) >= 4:
                width = parts[0]
                height = parts[1]
                x = parts[2]
                y = parts[3]
                info_text = f"Size: {width}×{height}  |  Position: X={x}, Y={y}"
                self.current_info_label.configure(text=info_text)
        except Exception as e:
            self.current_info_label.configure(text="Error reading window info")

    def force_capi_refresh(self):
        """Force an immediate CAPI refresh."""
        if self.force_refresh_capi_callback:
            self.force_refresh_capi_callback()
            self.capi_status_label.configure(text="Refreshing...")
            # Clear status after 2 seconds
            self.window.after(2000, lambda: self.capi_status_label.configure(text=""))
    
    def apply_capi_interval(self):
        """Apply the CAPI refresh interval."""
        try:
            minutes = int(self.capi_interval_var.get())
            if minutes < 0:
                minutes = 0
            self.capi_interval_var.set(str(minutes))
            if self.update_capi_interval_callback:
                self.update_capi_interval_callback(minutes)
                self.capi_status_label.configure(text=f"Auto-refresh set to {minutes} min")
                self.window.after(2000, lambda: self.capi_status_label.configure(text=""))
        except ValueError:
            messagebox.showerror("Invalid Input", 
                               "Please enter a valid number of minutes",
                               parent=self.window)
            self.capi_interval_var.set(str(self.capi_refresh_interval))

    def destroy(self):
        """Destroy the settings window."""
        if self.window and self.window.winfo_exists():
            self.window.destroy()
    
    def winfo_exists(self):
        """Check if the window exists."""
        return self.window and self.window.winfo_exists()
        
    def _build_overlay_tab(self):
        """Zbuduj zakładkę Overlay w ustawieniach."""
        ov = get_overlay_settings()
        
        # Kolor - rozwijana lista
        ttk.Label(self.overlay_tab, text="Kolor tekstu:", style="TLabel").pack(anchor="w", padx=10, pady=(10, 5))
        self.overlay_color_var = tk.StringVar()
        self.overlay_color_dropdown = ttk.Combobox(self.overlay_tab, textvariable=self.overlay_color_var, state="readonly", width=30)
        
        # Zbuduj listę nazw + hexów
        color_values = [f"{name} ({hexval})" for name, hexval in OVERLAY_COLORS]
        self.overlay_color_dropdown['values'] = color_values
        
        # Znajdź aktualny kolor
        current_color = ov.get('color', '#003399')
        default_idx = 0
        for i, (name, hexval) in enumerate(OVERLAY_COLORS):
            if hexval == current_color:
                default_idx = i
                break
        self.overlay_color_dropdown.current(default_idx)
        self.overlay_color_dropdown.pack(anchor="w", padx=10, pady=(0, 5))
        
        # Pozycja X
        ttk.Label(self.overlay_tab, text="Pozycja X (piksele):", style="TLabel").pack(anchor="w", padx=10, pady=(10, 5))
        self.overlay_x_var = tk.StringVar(value=str(ov.get('x', 20)))
        x_entry = ttk.Entry(self.overlay_tab, width=10, textvariable=self.overlay_x_var, style="TEntry")
        x_entry.pack(anchor="w", padx=10, pady=(0, 5))
        
        # Pozycja Y
        ttk.Label(self.overlay_tab, text="Pozycja Y (piksele):", style="TLabel").pack(anchor="w", padx=10, pady=(10, 5))
        self.overlay_y_var = tk.StringVar(value=str(ov.get('y', 100)))
        y_entry = ttk.Entry(self.overlay_tab, width=10, textvariable=self.overlay_y_var, style="TEntry")
        y_entry.pack(anchor="w", padx=10, pady=(0, 5))
        
        # Rozmiar czcionki
        ttk.Label(self.overlay_tab, text="Rozmiar czcionki:", style="TLabel").pack(anchor="w", padx=10, pady=(10, 5))
        self.overlay_size_var = tk.StringVar(value=ov.get('size', 'normal'))
        size_dropdown = ttk.Combobox(self.overlay_tab, textvariable=self.overlay_size_var, state="readonly", width=15)
        size_dropdown['values'] = ('normal', 'small', 'large')
        size_dropdown.pack(anchor="w", padx=10, pady=(0, 5))
        
        # Przycisk Zastosuj
        ttk.Separator(self.overlay_tab, orient="horizontal").pack(fill="x", padx=10, pady=15)
        ttk.Button(self.overlay_tab, text="Zastosuj", command=self.apply_overlay_settings, style="TButton").pack(anchor="w", padx=10)
        
    def apply_overlay_settings(self):
        """Zapisz ustawienia overlay z GUI do pliku settings."""
        try:
            # Odczytaj wybrany kolor
            selected = self.overlay_color_var.get()
            hex_color = '#003399'
            for name, hexval in OVERLAY_COLORS:
                if name in selected:  # szukaj po nazwie w tekscie "Nazwa (#hex)"
                    hex_color = hexval
                    break
            
            # Odczytaj X i Y
            x = int(self.overlay_x_var.get())
            y = int(self.overlay_y_var.get())
            if x < 0:
                x = 0
            if y < 0:
                y = 0
            
            # Odczytaj rozmiar
            size = self.overlay_size_var.get()
            
            overlay_dict = {
                'color': hex_color,
                'x': x,
                'y': y,
                'size': size
            }
            save_overlay_settings(overlay_dict)
            messagebox.showinfo("Overlay", "Ustawienia overlay zostały zapisane.", parent=self.window)
        except ValueError:
            messagebox.showerror("Błąd", "Podaj prawidłowe wartości liczbowe dla pozycji X i Y.", parent=self.window)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się zapisać ustawień: {e}", parent=self.window)

    def toggle_window_settings_tab(self):
        """Toggle the visibility of the Window Settings debug tab."""
        self.window_settings_visible = not self.window_settings_visible
        
        if self.window_settings_visible:
            # Add the Window Settings tab to the notebook
            self.notebook.insert("end", self.window_tab, text="Window Settings")
            self.notebook.select(self.window_tab)
            self.debug_status_label.configure(text="Debug mode: ON (Window Settings tab visible)")
        else:
            # Remove the Window Settings tab
            self.notebook.forget(self.window_tab)
            self.debug_status_label.configure(text="")
            
    def show_bug_report(self):
        """Show the bug report dialog."""
        # Get theme colors for current theme to pass to the bug report dialog
        theme_colors = self.THEME_COLORS[self.current_theme]
        bug_report.show_bug_report_dialog(self.window, theme_colors)

    def apply_window_settings(self):
        """Apply the window size and position settings."""
        try:
            width = int(self.width_var.get())
            height = int(self.height_var.get())
            x = int(self.x_var.get())
            y = int(self.y_var.get())
            
            # Validate sizes
            if width < 400:
                width = 400
                self.width_var.set(str(width))
            if height < 300:
                height = 300
                self.height_var.set(str(height))
            
            if self.update_window_size_callback:
                self.update_window_size_callback(width, height, x, y)
                messagebox.showinfo("Settings Applied", 
                                  f"Window size set to {width}x{height} at position +{x}+{y}",
                                  parent=self.window)
        except ValueError:
            messagebox.showerror("Invalid Input", 
                               "Please enter valid integer values for all fields",
                               parent=self.window)
    
    def reset_window_settings(self):
        """Reset window to default size and position."""
        if messagebox.askyesno("Reset Window", 
                              "Reset window to default size (800x400) and centered position?",
                              parent=self.window):
            if self.reset_window_size_callback:
                self.reset_window_size_callback()
            
            # Update the display values
            self.width_var.set("800")
            self.height_var.set("400")
            self.x_var.set("0")
            self.y_var.set("0")
            
            messagebox.showinfo("Reset Complete",
                              "Window has been reset to default settings",
                              parent=self.window)

