"""Path resolution utilities for PyInstaller frozen environment support."""
import sys
from pathlib import Path

def get_data_dir() -> Path:
    """Get the dynamic data directory.
    If frozen (PyInstaller executable), we first search for a 'data' folder next to the .exe.
    This allows the user to view, edit, or add well logs / seismic files dynamically.
    If not found, we fallback to the internal sys._MEIPASS/data directory.
    In development, we use the project's root 'data/' directory.
    """
    if getattr(sys, "frozen", False):
        # Path of the directory containing the executable
        exe_dir = Path(sys.executable).parent
        data_dir = exe_dir / "data"
        if data_dir.exists() and data_dir.is_dir():
            return data_dir
        
        # Fallback to internal _MEIPASS data directory if bundled
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / "data"
            
    # Development mode
    return Path(__file__).resolve().parent.parent.parent / "data"

def get_patterns_dir() -> Path:
    """Get the patterns directory.
    Normally under src/patterns in dev, or bundled under sys._MEIPASS/src/patterns.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "src" / "patterns"
    return Path(__file__).resolve().parent.parent / "patterns"

def get_resources_dir() -> Path:
    """Get the resources directory.
    Normally under src/resources in dev, or bundled under sys._MEIPASS/src/resources.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "src" / "resources"
    return Path(__file__).resolve().parent.parent / "resources"
