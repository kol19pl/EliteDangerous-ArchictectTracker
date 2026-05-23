import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Tuple

DEFAULT_COLS: Tuple[str, ...] = (
    "Material",
    "Required",
    "Provided",
    "Needed",
    "ON LAST STATION",
    "Carrier Qty",
    "Ship Qty",
    "Shortfall"
)


def build_material_table(parent: tk.Widget, cols: Tuple[str, ...] = DEFAULT_COLS) -> ttk.Treeview:
    """Build the material table and attach a vertical scrollbar."""
    tree = ttk.Treeview(parent, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, anchor='w' if c == "Material" else 'center')

    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    return tree


def initialize_treeview_tags(tree: ttk.Treeview, materials_theme: int) -> None:
    """Initialize row tag colors for the material table."""
    if materials_theme == 0:
        evenrow_bg = "#252525"
        oddrow_bg = "#1a1a1a"
        full_delivery_bg = "#1e3a1e"
        no_delivery_bg = "#3a1e1e"
    else:
        evenrow_bg = "#ffffff"
        oddrow_bg = "#f0f0f0"
        full_delivery_bg = "#e0ffe0"
        no_delivery_bg = "#ffe0e0"

    tree.tag_configure('evenrow', background=evenrow_bg)
    tree.tag_configure('oddrow', background=oddrow_bg)
    tree.tag_configure('fullDelivery', background=full_delivery_bg)
    tree.tag_configure('noDelivery', background=no_delivery_bg)


def refresh_tree_columns(tree: ttk.Treeview, column_order: List[str], column_visibility: Dict[str, bool]) -> None:
    """Refresh the visible columns in the table according to order and visibility."""
    visible_columns = [col for col in column_order if column_visibility.get(col, True)]
    tree["displaycolumns"] = visible_columns
    for col in visible_columns:
        tree.heading(col, text=col)
        tree.column(col, width=100)
