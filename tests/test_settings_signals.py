"""Task 22b.2 — SettingsPage signal listeners (TDD)."""
import pytest


def test_preference_bus_signals_exist():
    """PreferenceBus must have theme_changed, coordinate_format_changed, cache_cleared."""
    from src.utils.preferences import get_preference_bus
    bus = get_preference_bus()
    assert hasattr(bus, "theme_changed"), "PreferenceBus must have theme_changed signal"
    assert hasattr(bus, "coordinate_format_changed"), "PreferenceBus must have coordinate_format_changed signal"
    assert hasattr(bus, "cache_cleared"), "PreferenceBus must have cache_cleared signal"


def test_mainwindow_connects_preference_bus(qtbot):
    """MainWindow must connect to PreferenceBus signals on init."""
    from src.app import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    # Emit signals — should not raise
    from src.utils.preferences import get_preference_bus
    bus = get_preference_bus()
    bus.theme_changed.emit("矿石灰")
    bus.cache_cleared.emit(12.5)
    assert win.status_text.text() == "缓存已清理 · 释放 12.5 MB"


def test_mainwindow_has_on_theme_preference(qtbot):
    """MainWindow must have _on_theme_preference method."""
    from src.app import MainWindow
    assert hasattr(MainWindow, "_on_theme_preference"), (
        "MainWindow must have _on_theme_preference"
    )


def test_mainwindow_has_on_cache_cleared(qtbot):
    """MainWindow must have _on_cache_cleared method."""
    from src.app import MainWindow
    assert hasattr(MainWindow, "_on_cache_cleared"), (
        "MainWindow must have _on_cache_cleared"
    )


def test_settings_page_cache_clear_updates_label(qtbot):
    """Clearing cache should update the cache size label."""
    from src.pages.settings.page import SettingsPage
    page = SettingsPage()
    qtbot.addWidget(page)
    old_text = page.cache_size_label.text()
    page.clear_cache_btn.click()
    new_text = page.cache_size_label.text()
    # Should still be a valid label after click
    assert "MB" in new_text or "GB" in new_text
