import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Callable, List, Optional, Tuple

class SettingsWindow:
    """Class that handles the settings window for Architect Tracker plugin."""
    
    def __init__(self, parent, 
                 # Theme-related properties
                 theme_constants: Dict,
                 current_theme: int,
                 materials_theme: int,
                 
                 # Settings data
                 column_visibility: Dict[str, bool],
                 hide_provided: bool,
                 sort_by_system: bool,
                 cargo_capacity: int,
                 data: Dict,
                 
                 # Callback functions
                 toggle_column_callback: Callable[[str, bool], None],
                 toggle_hide_provided_callback: Callable[[], None],
                 toggle_sort_mode_callback: Callable[[], None],
                 update_cargo_capacity_callback: Callable[[int], None],
                 remove_station_callback: Callable[[str], None],
                 change_theme_callback: Callable[[int], None],
                 change_materials_theme_callback: Callable[[int], None]):
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
        self.hide_provided = hide_provided
        self.sort_by_system = sort_by_system
        self.cargo_capacity = cargo_capacity
        self.data = data
        
        # Store callback functions
        self.toggle_column_callback = toggle_column_callback
        self.toggle_hide_provided_callback = toggle_hide_provided_callback
        self.toggle_sort_mode_callback = toggle_sort_mode_callback
        self.update_cargo_capacity_callback = update_cargo_capacity_callback
        self.remove_station_callback = remove_station_callback
        self.change_theme_callback = change_theme_callback
        self.change_materials_theme_callback = change_materials_theme_callback
        
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
        
        # Create three tabs: Display Settings, Theme Settings, and Station Management
        self.display_tab = ttk.Frame(self.notebook, style="Main.TFrame")
        self.theme_tab = ttk.Frame(self.notebook, style="Main.TFrame")
        self.station_tab = ttk.Frame(self.notebook, style="Main.TFrame")
        
        # Add tabs to the notebook
        self.notebook.add(self.display_tab, text="Display Settings")
        self.notebook.add(self.theme_tab, text="Theme")
        self.notebook.add(self.station_tab, text="Station Management")
        
        # --------- DISPLAY SETTINGS TAB ---------
        ttk.Label(self.display_tab, text="Select columns to display:", style="TLabel").pack(padx=10, pady=5, anchor="w")
        
        # Column visibility checkboxes
        for idx, (col, visible) in enumerate(self.column_visibility.items()):
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
        self.system_var = tk.StringVar(value="Wszystkie Systemy")  # Default to "All Systems"
        self.system_dropdown = ttk.Combobox(system_frame, textvariable=self.system_var, state="readonly", width=25)
        system_values = ["Wszystkie Systemy"] + sorted(list(systems))
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
        self.system_station_data = {"Wszystkie Systemy": []}  # Store station data by system
        
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
            self.system_station_data["Wszystkie Systemy"].append((display_text, station_key))
            
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
    
    def destroy(self):
        """Destroy the settings window."""
        if self.window and self.window.winfo_exists():
            self.window.destroy()
    
    def winfo_exists(self):
        """Check if the window exists."""
        return self.window and self.window.winfo_exists()

