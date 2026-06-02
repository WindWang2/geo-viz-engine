"""PreferenceBus — global signal bus for app-wide preference changes (theme, coords, cache)."""
from PySide6.QtCore import QObject, Signal


class PreferenceBus(QObject):
    """Singleton signal bus for preference broadcasts."""

    theme_changed = Signal(str)              # "浅米白" / "矿石灰"
    coordinate_format_changed = Signal(str)  # "DD" / "DMS"
    cache_cleared = Signal(float)            # MB released


_instance: PreferenceBus | None = None


def get_preference_bus() -> PreferenceBus:
    global _instance
    if _instance is None:
        _instance = PreferenceBus()
    return _instance
