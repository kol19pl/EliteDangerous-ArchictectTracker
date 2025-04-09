import json
import os
import logging
import tkinter as tk
from tkinter import ttk
import glob

# Architect Tracker - displays commodities required, provided and needed when you land at a construction site.

# File paths
SAVE_FILE = os.path.join(os.path.expanduser("~"), "Documents", "construction_requirements.json")
LOG_FILE = os.path.join(os.path.expanduser("~"), "Documents", "EDMC_Construction_Log.txt")

# Set up logging
logger = logging.getLogger("BaseConstructionHelper")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

def save_facility_requirements(materials, station_name):
    try:
        data = {
            "station_name": station_name,
            "materials": materials
        }
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error("Error saving materials: %s", e)

def load_facility_requirements():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error loading saved materials: %s", e)
    return {}

def journal_entry(cmdr, is_beta, system, station, entry, state):
    if entry.get("event") == "ColonisationConstructionDepot":
        resources = entry.get("ResourcesRequired", [])
        materials = {
            res["Name_Localised"]: {
                "RequiredAmount": res["RequiredAmount"],
                "ProvidedAmount": res["ProvidedAmount"]
            }
            for res in resources
        }
        
        # Log the event and materials saved
        logger.info("ColonisationConstructionDepot event detected in journal entry: %s", json.dumps(entry, indent=4))
        save_facility_requirements(materials, station)

def show_facilities_gui():
    logger.info("Show Construction Requirements button pressed.")
    
    data = load_facility_requirements()
    
    if not data:
        logger.info("No construction requirements found in the saved file.")
        return
    
    station_name = data.get("station_name", "Unknown Station")
    materials = data.get("materials", {})
    
    root = tk.Tk()
    root.title("Construction Site Requirements")
    root.geometry("600x400")
    root.configure(bg="#1a1a1a")
    
    frame = ttk.Frame(root, padding=10, style="Dark.TFrame")
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Style configuration
    style = ttk.Style()
    style.configure("Dark.TFrame", background="#1a1a1a")
    style.configure("Dark.TLabel", background="#1a1a1a", foreground="white", font=("Arial", 12))
    style.configure("Dark.TButton", background="#333333", foreground="white", font=("Arial", 10))
    
    ttk.Label(frame, text="Station", style="Dark.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    ttk.Label(frame, text="Resource", style="Dark.TLabel").grid(row=0, column=1, padx=5, pady=5, sticky="w")
    ttk.Label(frame, text="Required", style="Dark.TLabel").grid(row=0, column=2, padx=5, pady=5, sticky="w")
    ttk.Label(frame, text="Provided", style="Dark.TLabel").grid(row=0, column=3, padx=5, pady=5, sticky="w")
    ttk.Label(frame, text="Needed", style="Dark.TLabel").grid(row=0, column=4, padx=5, pady=5, sticky="w")  # New column
    
    # Display Station name
    ttk.Label(frame, text=station_name, style="Dark.TLabel").grid(row=1, column=0, padx=5, pady=2, sticky="w", columnspan=5)
    
    for idx, (item, values) in enumerate(materials.items(), start=2):
        required = values["RequiredAmount"]
        provided = values["ProvidedAmount"]
        needed = required - provided  # Calculate the "Needed" amount
        
        ttk.Label(frame, text=item, style="Dark.TLabel").grid(row=idx, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(frame, text=str(required), style="Dark.TLabel").grid(row=idx, column=2, padx=5, pady=2, sticky="w")
        ttk.Label(frame, text=str(provided), style="Dark.TLabel").grid(row=idx, column=3, padx=5, pady=2, sticky="w")
        ttk.Label(frame, text=str(needed), style="Dark.TLabel").grid(row=idx, column=4, padx=5, pady=2, sticky="w")  # New "Needed" column
    
    root.mainloop()

def plugin_start3(plugin_dir):
    return "Base Construction Helper"

def plugin_stop():
    pass

def plugin_app(parent):
    frame = ttk.Frame(parent, style="Dark.TFrame")
    ttk.Button(frame, text="Show Construction Requirements", command=show_facilities_gui, style="Dark.TButton").pack(padx=10, pady=10)
    return frame
