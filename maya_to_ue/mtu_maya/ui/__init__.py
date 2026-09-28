"""mtu_maya.ui

PySide6/PySide2 user interface for the Maya→UE animation pipeline tool.

Chinese, dark-themed. See style.py (theme) and strings.py (copy).

Launching inside Maya (Script Editor or shelf button):
    from mtu_maya.ui import show
    show()
"""

from .main_window import (
    MainWindow,
    show,
    CheckListPanel,
    DetailPanel,
    ClipTablePanel,
    ExportPanel,
)
from . import style, strings

__all__ = [
    "MainWindow",
    "show",
    "CheckListPanel",
    "DetailPanel",
    "ClipTablePanel",
    "ExportPanel",
    "style",
    "strings",
]
