import json
import os
import logging
import tkinter as tk
import platform
from tkinter import ttk, messagebox
from contextlib import suppress

# Architect Tracker - an EDMC plugin that shows commodity requirements for construction sites.

# Cross-platform plugin settings directory
if platform.system() == "Windows":
    USER_DIR = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")), "ArchitectTracker")
elif platform.system() == "Darwin":  # macOS
    USER_DIR = os.path.join(os.path.expanduser("~/Library/Application Support"), "ArchitectTracker")
else:  # Linux and others
    USER_DIR = os.path.join(os.path.expanduser("~/.config"), "ArchitectTracker")

os.makedirs(USER_DIR, exist_ok=True)

SAVE_FILE = os.path.join(USER_DIR, "construction_requirements.json")
LOG_FILE = os.path.join(USER_DIR, "EDMC_Construction_Log.txt")


# Set up logging
logger = logging.getLogger("BaseConstructionHelper")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

def is_station_complete(materials):
    return all(info["ProvidedAmount"] >= info["RequiredAmount"] for info in materials.values())

def save_facility_requirements(materials, station_name):
    try:
        with suppress(FileNotFoundError):
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                all_data = json.load(f)
        if not isinstance(all_data, dict):
            all_data = {}
    except Exception as e:
        logger.error("Error loading existing materials: %s", e)
        all_data = {}

    if is_station_complete(materials):
        logger.info("Station '%s' construction is complete. Removing from saved data.", station_name)
        all_data.pop(station_name, None)
        try:
            messagebox.showinfo("Station Complete", f"'{station_name}' construction is complete and has been removed from the list.")
        except tk.TclError:
            logger.warning("Could not show popup (GUI not initialized).")
    else:
        all_data[station_name] = {
            "materials": materials
        }

    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=4)
    except Exception as e:
        logger.error("Error saving materials: %s", e)

def load_facility_requirements():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            removed = []
            cleaned = {}

            for station, info in data.items():
                if is_station_complete(info["materials"]):
                    removed.append(station)
                else:
                    cleaned[station] = info

            if removed:
                logger.info("Removed completed stations on load: %s", ", ".join(removed))
                try:
                    messagebox.showinfo("Stations Cleared", f"The following completed stations were removed:\n\n" + "\n".join(removed))
                except tk.TclError:
                    logger.warning("Could not show popup (GUI not initialized).")

            if cleaned != data:
                with open(SAVE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cleaned, f, indent=4)

            return cleaned

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
        logger.info("ColonisationConstructionDepot event detected in journal entry: %s", json.dumps(entry, indent=4))
        save_facility_requirements(materials, station)

def show_facilities_gui():
    logger.info("Show Construction Requirements button pressed.")

    data = load_facility_requirements()

    if not data:
        messagebox.showinfo("Info", "No construction requirements found.")
        return

    def get_display_name(full_name):
        return full_name.split(":", 1)[-1].strip() if ":" in full_name else full_name

    def get_full_name(short_name):
        for full, short in station_display_map.items():
            if short == short_name:
                return full
        return short_name  # Fallback

    def display_station_materials(selected_station):
        for widget in frame.winfo_children():
            if isinstance(widget, ttk.Label) and widget.grid_info()['row'] > 1:
                widget.destroy()

        materials = data[selected_station]["materials"]
        display_name = get_display_name(selected_station)
        ttk.Label(frame, text=display_name, style="Dark.TLabel").grid(row=1, column=0, padx=5, pady=2, sticky="w", columnspan=5)

        for idx, (item, values) in enumerate(materials.items(), start=2):
            required = values["RequiredAmount"]
            provided = values["ProvidedAmount"]
            needed = required - provided

            ttk.Label(frame, text=item, style="Dark.TLabel").grid(row=idx, column=1, padx=5, pady=2, sticky="w")
            ttk.Label(frame, text=str(required), style="Dark.TLabel").grid(row=idx, column=2, padx=5, pady=2, sticky="w")
            ttk.Label(frame, text=str(provided), style="Dark.TLabel").grid(row=idx, column=3, padx=5, pady=2, sticky="w")
            ttk.Label(frame, text=str(needed), style="Dark.TLabel").grid(row=idx, column=4, padx=5, pady=2, sticky="w")

    root = tk.Tk()
    root.title("Construction Site Requirements")
    root.geometry("700x500")
    root.configure(bg="#1a1a1a")

    style = ttk.Style()
    style.configure("Dark.TFrame", background="#1a1a1a")
    style.configure("Dark.TLabel", background="#1a1a1a", foreground="white", font=("Arial", 12))
    style.configure("Dark.TButton", background="#333333", foreground="white", font=("Arial", 10))

    frame = ttk.Frame(root, padding=10, style="Dark.TFrame")
    frame.pack(fill=tk.BOTH, expand=True)

    # Prepare sorted dropdown data
    station_display_map = {
        full: get_display_name(full)
        for full in data.keys()
    }
    sorted_items = sorted(station_display_map.items(), key=lambda item: item[1])
    display_names = [short for _, short in sorted_items]
    full_names = [full for full, _ in sorted_items]

    ttk.Label(frame, text="Select Station:", style="Dark.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    station_var = tk.StringVar(value=display_names[0])
    station_dropdown = ttk.Combobox(frame, textvariable=station_var, values=display_names, state="readonly")
    station_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="w")

    station_dropdown.bind("<<ComboboxSelected>>", lambda event: display_station_materials(get_full_name(station_var.get())))

    # Initial display
    display_station_materials(get_full_name(station_var.get()))

    root.mainloop()

def plugin_start3(plugin_dir):
    return "Base Construction Helper"

def plugin_stop():
    pass

def plugin_app(parent):
    frame = ttk.Frame(parent, style="Dark.TFrame")
    ttk.Button(frame, text="Show Construction Requirements", command=show_facilities_gui, style="Dark.TButton").pack(padx=10, pady=10)
    return frame
