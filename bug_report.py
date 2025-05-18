import tkinter as tk
from tkinter import ttk, messagebox
import json
import platform
import sys
import os
import requests
import logging
import datetime
import threading
from typing import Callable, Optional, Dict, Any

# Import the updater to get version info
import updater

# Configure logger
logger = logging.getLogger("ArchitectTracker.BugReport")

# Discord webhook URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1373770213098524904/qqZEXP80Q5Z5A46BqeIHLi6lJlseIlKVFODMnlngEJac3RQDRjeQqbMnXTuEzhBMxoqy"

class BugReportDialog(tk.Toplevel):
    """Dialog for collecting bug report information from users."""
    
    def __init__(self, parent, theme_colors=None):
        super().__init__(parent)
        self.parent = parent
        self.title("Report a Bug")
        self.transient(parent)
        self.grab_set()
        
        # Apply theme if provided
        if theme_colors:
            self.configure(bg=theme_colors["background"])
            self.theme_colors = theme_colors
        else:
            # Default colors if parent theme not available
            self.configure(bg="#1a1a1a")
            self.theme_colors = {
                "background": "#1a1a1a",
                "foreground": "#ff8500",
                "button_bg": "#333333",
                "button_fg": "#ffffff"
            }
        
        # Main frame
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(frame, 
                  text="Report a Bug",
                  font=("Segoe UI", 14, "bold")).pack(pady=(0, 15))
        
        # Form elements
        ttk.Label(frame, text="Bug Title:").pack(anchor="w", pady=(10, 2))
        self.title_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.title_var, width=50).pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(frame, text="Description:").pack(anchor="w", pady=(5, 2))
        
        # Text area with scrollbar for description
        desc_frame = ttk.Frame(frame)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        desc_scrollbar = ttk.Scrollbar(desc_frame)
        desc_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.desc_text = tk.Text(desc_frame, height=10, width=50, wrap=tk.WORD,
                               yscrollcommand=desc_scrollbar.set)
        self.desc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        desc_scrollbar.config(command=self.desc_text.yview)
        
        # Include system info checkbox
        self.include_system_info = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, 
                      text="Include system information", 
                      variable=self.include_system_info).pack(anchor="w", pady=(5, 10))
        
        # Version info (always included, not optional)
        version_frame = ttk.Frame(frame)
        version_frame.pack(fill=tk.X, pady=(5, 15))
        ttk.Label(version_frame, text="Plugin Version:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(version_frame, text=updater.get_current_version(), font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Submit", command=self.submit_report).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Center the dialog over the parent window
        self.update_idletasks()
        if parent:
            x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        else:
            x = (self.winfo_screenwidth() - self.winfo_width()) // 2
            y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        # Set minimum window size
        self.minsize(400, 450)
        
        # Pre-select the title entry for immediate typing
        self.after(100, lambda: self.focus_force())
    
    def get_system_info(self) -> Dict[str, str]:
        """Gather system information for the bug report."""
        try:
            return {
                "OS": f"{platform.system()} {platform.release()} {platform.version()}",
                "Architecture": platform.machine(),
                "Python": f"{platform.python_version()}",
                "Processor": platform.processor(),
            }
        except Exception as e:
            logger.error(f"Error gathering system info: {e}")
            return {"Error": f"Failed to gather system information: {e}"}
    
    def submit_report(self):
        """Submit the bug report to Discord webhook."""
        # Validate inputs
        title = self.title_var.get().strip()
        description = self.desc_text.get("1.0", tk.END).strip()
        
        if not title:
            messagebox.showwarning("Missing Information", "Please enter a bug title.", parent=self)
            return
        
        if not description:
            messagebox.showwarning("Missing Information", "Please enter a bug description.", parent=self)
            return
        
        # Confirm submission
        if not messagebox.askyesno("Confirm Submission", 
                                  "Are you sure you want to submit this bug report?", 
                                  parent=self):
            return
        
        # Disable inputs during submission
        self.title_var.set("Submitting report...")
        self.desc_text.config(state=tk.DISABLED)
        for widget in self.winfo_children():
            if isinstance(widget, ttk.Button):
                widget.config(state=tk.DISABLED)
        
        # Create report data
        report_data = {
            "title": title,
            "description": description,
            "version": updater.get_current_version(),
            "timestamp": datetime.datetime.now().isoformat(),
            "include_system_info": self.include_system_info.get()
        }
        
        if self.include_system_info.get():
            report_data["system_info"] = self.get_system_info()
        
        # Submit in background thread
        threading.Thread(target=self._submit_report_thread, 
                        args=(report_data,), 
                        daemon=True).start()
    
    def _submit_report_thread(self, report_data: Dict[str, Any]):
        """Thread function to submit the report to Discord."""
        try:
            # Create Discord embed
            embed = {
                "title": f"Bug Report: {report_data['title']}",
                "description": report_data['description'],
                "color": 15105570,  # Orange color (decimal value)
                "timestamp": report_data['timestamp'],
                "fields": [
                    {
                        "name": "Version",
                        "value": report_data['version'],
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "Architect Tracker Bug Report"
                }
            }
            
            # Add system info if included
            if report_data.get("include_system_info", False) and "system_info" in report_data:
                system_info_text = "\n".join([f"{k}: {v}" for k, v in report_data["system_info"].items()])
                embed["fields"].append({
                    "name": "System Information",
                    "value": f"```\n{system_info_text}\n```",
                    "inline": False
                })
            
            # Prepare webhook payload
            payload = {
                "content": f"New bug report from Architect Tracker",
                "embeds": [embed]
            }
            
            # Send to Discord
            response = requests.post(DISCORD_WEBHOOK_URL, 
                                    json=payload,
                                    headers={"Content-Type": "application/json"},
                                    timeout=10)
            response.raise_for_status()
            
            # Handle success in main thread
            self.after(0, lambda: self._handle_submission_success())
            
        except Exception as e:
            logger.error(f"Error submitting bug report: {e}")
            # Handle error in main thread
            self.after(0, lambda: self._handle_submission_error(str(e)))
    
    def _handle_submission_success(self):
        """Handle successful submission in the main thread."""
        messagebox.showinfo("Success", 
                          "Your bug report has been submitted successfully. Thank you!", 
                          parent=self)
        self.destroy()
    
    def _handle_submission_error(self, error_message: str):
        """Handle submission error in the main thread."""
        messagebox.showerror("Error", 
                           f"Failed to submit bug report: {error_message}\n\nPlease try again later.", 
                           parent=self)
        # Re-enable inputs
        self.title_var.set(self.title_var.get().replace("Submitting report...", ""))
        self.desc_text.config(state=tk.NORMAL)
        for widget in self.winfo_children():
            if isinstance(widget, ttk.Button):
                widget.config(state=tk.NORMAL)

def show_bug_report_dialog(parent, theme_colors=None):
    """Show the bug report dialog."""
    dialog = BugReportDialog(parent, theme_colors)
    return dialog

