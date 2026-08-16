"""
Moduł zarządzania danymi - obsługuje operacje wejścia/wyjścia plików oraz funkcje pomocnicze.
"""
import json
import os
import logging
from settings import USER_DIR

# Konfiguracja loggera
logger = logging.getLogger("ArchitectTracker")

# Ścieżki do plików
SAVE_FILE = os.path.join(USER_DIR, "construction_requirements.json")  # Plik z wymaganiami budowlanymi
MARKET_JSON = os.path.join(os.getenv('USERPROFILE', os.path.expanduser('~')), 
                           'Saved Games', 'Frontier Developments', 'Elite Dangerous', 'Market.json')  # Dane rynku
CARGO_JSON = os.path.join(os.getenv('USERPROFILE', os.path.expanduser('~')), 
                          'Saved Games', 'Frontier Developments', 'Elite Dangerous', 'Cargo.json')  # Dane ładunku

# --- Trwałość danych wymagań ---
def is_station_complete(materials):
    """
    Sprawdza czy wszystkie materiały dla stacji zostały w pełni dostarczone.
    
    Args:
        materials: Słownik materiałów z polami 'ProvidedAmount' i 'RequiredAmount'
    
    Returns:
        True jeśli wszystkie materiały są w pełni dostarczone, False w przeciwnym razie
    """
    if not isinstance(materials, dict) or not materials:
        return True

    for info in materials.values():
        if not isinstance(info, dict):
            return False
        try:
            required = int(info.get('RequiredAmount', 0))
            provided = int(info.get('ProvidedAmount', 0))
        except (TypeError, ValueError):
            return False
        if provided < required:
            return False
    return True


def save_facility_requirements(materials, station_name, system, refresh_callback=None):
    """
    Zapisuje wymagania budowlane do pliku.
    
    Jeśli wszystkie materiały są już dostarczone, usuwa stację z pliku.
    
    Args:
        materials: Słownik materiałów do zapisania
        station_name: Nazwa stacji
        system: Nazwa systemu gwiezdnego
        refresh_callback: Opcjonalna funkcja do odświeżenia GUI po zapisie
    """
    if station_name is None:
        logger.warning("Attempted to save facility requirements without a station name")
        return

    materials = materials if isinstance(materials, dict) else {}

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
        logger.error("Błąd zapisu danych: %s", e)

    if refresh_callback:
        refresh_callback()


def load_facility_requirements():
    """
    Wczytuje wymagania budowlane z pliku.
    
    Automatycznie usuwa stacje, które zostały już ukończone.
    
    Returns:
        Słownik stacji i ich wymagań, lub pusty słownik jeśli plik nie istnieje
    """
    if not os.path.exists(SAVE_FILE):
        return {}
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Błąd odczytu pliku: %s", e)
        return {}

    if not isinstance(data, dict):
        logger.warning("Invalid facility requirements structure in save file; resetting to empty dict")
        return {}

    # Usuń ukończone stacje
    cleaned = {}
    for station_key, info in data.items():
        if not isinstance(info, dict):
            continue
        materials = info.get("materials", {})
        if not is_station_complete(materials):
            cleaned[station_key] = info
    if cleaned != data:
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(cleaned, f, indent=4)
        except Exception as e:
            logger.error("Błąd zapisu oczyszczonych danych: %s", e)
    return cleaned


# --- Rynek i ładunek ---
def load_market_data():
    """
    Wczytuje dane rynkowe z pliku Market.json.
    
    Returns:
        Krotka (lista przedmiotów, nazwa stacji) lub ([], None) w przypadku błędu
    """
    if not os.path.exists(MARKET_JSON):
        return [], None
    try:
        with open(MARKET_JSON, "r", encoding="utf-8") as f:
            market = json.load(f)
        return market.get("Items", []), market.get("StationName")
    except Exception as e:
        logger.error("Błąd wczytywania danych rynku: %s", e)
        return [], None


def load_cargo_data():
    """
    Wczytuje dane ładunku statku z pliku Cargo.json.
    
    Returns:
        Lista przedmiotów w ładowni, lub [] w przypadku błędu
    """
    if not os.path.exists(CARGO_JSON):
        return []
    try:
        with open(CARGO_JSON, "r", encoding="utf-8") as f:
            cargo = json.load(f)
        return cargo.get("Inventory", [])
    except Exception as e:
        logger.error("Błąd wczytywania danych ładunku: %s", e)
        return []


def get_total_ship_cargo():
    """
    Oblicza całkowitą ilość ładunku aktualnie w statku.
    
    Returns:
        Suma wszystkich przedmiotów w ładowni
    """
    cargo_items = load_cargo_data()
    total_cargo = sum(item.get('Count', 0) for item in cargo_items)
    return total_cargo


def get_construction_system_name(gui_instance):
    """
    Pobiera nazwę systemu dla wybranej stacji w GUI.
    
    Args:
        gui_instance: Instancja ArchitectTrackerGUI
    
    Returns:
        Nazwa systemu lub 'N/A' jeśli nie znaleziono
    """
    sel = gui_instance.station_var.get()
    full = gui_instance.station_map.get(sel)
    if not full:
        return 'N/A'
    entry = gui_instance.data.get(full, {})
    system_name = entry.get('system')
    return system_name or 'N/A'