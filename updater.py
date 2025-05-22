import os
import sys
import json
import logging
import tkinter as tk
from tkinter import ttk, messagebox
import requests
import zipfile
import shutil
import re
from contextlib import suppress
import threading

# Configure logger
logger = logging.getLogger("ArchitectTracker.Updater")

# Constants
CURRENT_VERSION = "1.8.2"
GITHUB_API_URL = "https://api.github.com/repos/kol19pl/EliteDangerous-ArchictectTracker/releases"
GITHUB_RELEASES_URL = "https://github.com/kol19pl/EliteDangerous-ArchictectTracker/releases"
TEMP_DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_download")

def parse_version(version_str):
    """
    Parse a version string into a tuple for comparison.
    
    Args:
        version_str (str): Version string like '1.7' or 'v1.7.2'
        
    Returns:
        tuple: Version components as integers
    """
    # Remove 'v' prefix if present
    if version_str.lower().startswith('v'):
        version_str = version_str[1:]
        
    # Split version string by dots and convert to integers
    try:
        return tuple(map(int, version_str.split('.')))
    except ValueError:
        # If conversion fails, return a tuple that will compare lower than any valid version
        return (0,)

def get_available_releases():
    """
    Fetch available releases from GitHub API.
    
    Returns:
        tuple: (success flag, list of releases or error message)
    """
    try:
        response = requests.get(GITHUB_API_URL, timeout=10)
        response.raise_for_status()
        
        releases = response.json()
        if not releases:
            return False, "No releases found"
        
        # Format releases for display
        formatted_releases = []
        for release in releases:
            release_name = release.get('name', '').strip()
            tag_name = release.get('tag_name', '').strip()
            
            # Extract version from tag_name (v1.7 -> 1.7)
            version_match = re.search(r'v?(\d+\.\d+(?:\.\d+)?)', tag_name)
            version_str = version_match.group(1) if version_match else tag_name
            
            # Get asset download URL
            assets = release.get('assets', [])
            download_url = None
            for asset in assets:
                if asset.get('name', '').endswith('.zip'):
                    download_url = asset.get('browser_download_url')
                    break
            
            if download_url:
                formatted_releases.append({
                    'version': version_str,
                    'name': release_name,
                    'tag': tag_name,
                    'download_url': download_url,
                    'published_at': release.get('published_at', ''),
                    'description': release.get('body', '')
                })
        
        # Sort releases by version (descending)
        formatted_releases.sort(key=lambda x: parse_version(x['version']), reverse=True)
        return True, formatted_releases
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch releases: {e}")
        return False, f"Failed to fetch releases: {e}"
    except Exception as e:
        logger.error(f"Error processing releases: {e}")
        return False, f"Error processing releases: {e}"

def is_newer_version(current, target):
    """
    Check if target version is newer than current version.
    
    Args:
        current (str): Current version string
        target (str): Target version string
        
    Returns:
        bool: True if target is newer than current
    """
    try:
        current_parsed = parse_version(current)
        target_parsed = parse_version(target)
        return target_parsed > current_parsed
    except Exception as e:
        logger.error(f"Error comparing versions: {e}")
        # If parsing fails, fall back to string comparison
        return target > current

def download_and_install_update(release, progress_callback=None, completion_callback=None):
    """
    Download and install the selected release.
    
    Args:
        release (dict): Release information including download URL
        progress_callback (callable): Function to call with progress updates
        completion_callback (callable): Function to call when installation completes
    """
    def _update_worker():
        try:
            # Ensure temp directory exists and is empty
            if os.path.exists(TEMP_DOWNLOAD_DIR):
                shutil.rmtree(TEMP_DOWNLOAD_DIR)
            os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
            
            download_url = release['download_url']
            version_str = release['version']
            zip_path = os.path.join(TEMP_DOWNLOAD_DIR, f"architect_tracker_v{version_str}.zip")
            
            # Report starting download
            if progress_callback:
                progress_callback(0, f"Downloading version {version_str}...")
            
            # Download the release zip file
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            # Get file size for progress reporting
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = int((downloaded_size / total_size) * 50)  # 0-50% for download
                            progress_callback(progress, f"Downloading: {downloaded_size/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB")
            
            if progress_callback:
                progress_callback(50, "Download complete. Extracting files...")
            
            # Extract the zip file
            extract_dir = os.path.join(TEMP_DOWNLOAD_DIR, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            if progress_callback:
                progress_callback(70, "Extraction complete. Installing update...")
            
            # Determine the plugin directory
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Backup current version - save essential user data
            backup_dir = os.path.join(plugin_dir, "backup")
            os.makedirs(backup_dir, exist_ok=True)
            
            # Files to preserve (settings, saved stations, etc.)
            preserve_files = [
                "construction_requirements.json",
                "settings.json",
                "fleet_carrier_cargo.json",
                "EDMC_Architect_Log.txt"
            ]
            
            # Backup preserved files
            for filename in preserve_files:
                src_path = os.path.join(plugin_dir, filename)
                if os.path.exists(src_path):
                    shutil.copy2(src_path, os.path.join(backup_dir, filename))
            
            # Find the extracted plugin directory
            # This assumes the zip contains a directory with the plugin files
            extracted_contents = os.listdir(extract_dir)
            source_dir = extract_dir
            
            # If the zip contains a single directory, use that as the source
            if len(extracted_contents) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_contents[0])):
                source_dir = os.path.join(extract_dir, extracted_contents[0])
            
            # Copy new files to plugin directory
            for item in os.listdir(source_dir):
                src_path = os.path.join(source_dir, item)
                dst_path = os.path.join(plugin_dir, item)
                
                # Skip preserved files
                if item in preserve_files:
                    continue
                
                # Remove existing files/dirs before copying
                if os.path.exists(dst_path):
                    if os.path.isdir(dst_path):
                        shutil.rmtree(dst_path)
                    else:
                        os.remove(dst_path)
                
                # Copy the new file/directory
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path)
                else:
                    shutil.copy2(src_path, dst_path)
            
            # Restore preserved files
            for filename in preserve_files:
                backup_path = os.path.join(backup_dir, filename)
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, os.path.join(plugin_dir, filename))
            
            if progress_callback:
                progress_callback(90, "Cleaning up temporary files...")
            
            # Clean up
            shutil.rmtree(TEMP_DOWNLOAD_DIR)
            shutil.rmtree(backup_dir)
            
            if progress_callback:
                progress_callback(100, f"Update to version {version_str} complete! Please restart EDMC to apply the update.")
            
            # Report success
            if completion_callback:
                completion_callback(True, f"Successfully updated to version {version_str}. Please restart EDMC to apply the update.")
        
        except Exception as e:
            logger.error(f"Update failed: {e}")
            if progress_callback:
                progress_callback(-1, f"Update failed: {e}")
            if completion_callback:
                completion_callback(False, f"Update failed: {e}")
    
    # Start update in a separate thread
    update_thread = threading.Thread(target=_update_worker)
    update_thread.daemon = True
    update_thread.start()
    return update_thread

def get_current_version():
    """
    Get the current installed version.
    
    Returns:
        str: Current version string
    """
    return CURRENT_VERSION

