"""TDD tests for Task 21.1 — SettingsPage + PreferenceBus."""
import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton
from PySide6.QtCore import QObject


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_preference_bus_singleton_has_signals(app):
    """Global PreferenceBus must expose theme_changed and coordinate_format_changed signals."""
    from src.utils.preferences import PreferenceBus, get_preference_bus

    bus = get_preference_bus()
    assert isinstance(bus, QObject)
    assert get_preference_bus() is bus  # singleton
    assert hasattr(bus, "theme_changed")
    assert hasattr(bus, "coordinate_format_changed")
    assert hasattr(bus, "cache_cleared")
    # smoke connect/emit
    received = []
    bus.theme_changed.connect(lambda name: received.append(("theme", name)))
    bus.coordinate_format_changed.connect(lambda fmt: received.append(("coord", fmt)))
    bus.theme_changed.emit("light")
    bus.coordinate_format_changed.emit("DMS")
    assert ("theme", "light") in received
    assert ("coord", "DMS") in received


def test_settings_page_exists_with_controls(app):
    from src.pages.settings import SettingsPage

    page = SettingsPage()
    # Theme combo: at least 2 options (浅米白 / 矿石灰)
    assert hasattr(page, "theme_combo")
    assert isinstance(page.theme_combo, QComboBox)
    items = [page.theme_combo.itemText(i) for i in range(page.theme_combo.count())]
    assert any("浅米白" in it for it in items)
    assert any("矿石灰" in it for it in items)

    # Coordinate format toggle (DD / DMS)
    assert hasattr(page, "coord_dd_btn")
    assert hasattr(page, "coord_dms_btn")
    assert isinstance(page.coord_dd_btn, QPushButton)
    assert page.coord_dd_btn.isCheckable()
    assert page.coord_dms_btn.isCheckable()

    # Cache clear button with capacity label
    assert hasattr(page, "clear_cache_btn")
    assert hasattr(page, "cache_size_label")


def test_settings_page_emits_theme_signal(app):
    from src.pages.settings import SettingsPage
    from src.utils.preferences import get_preference_bus

    page = SettingsPage()
    received = []
    get_preference_bus().theme_changed.connect(lambda name: received.append(name))

    # Switch to 矿石灰 — find its index
    for i in range(page.theme_combo.count()):
        if "矿石灰" in page.theme_combo.itemText(i):
            page.theme_combo.setCurrentIndex(i)
            break
    assert len(received) >= 1
    assert any("矿石灰" in r or "ore" in r.lower() for r in received)


def test_settings_page_emits_coordinate_format(app):
    from src.pages.settings import SettingsPage
    from src.utils.preferences import get_preference_bus

    page = SettingsPage()
    received = []
    get_preference_bus().coordinate_format_changed.connect(lambda fmt: received.append(fmt))

    page.coord_dms_btn.click()
    assert "DMS" in received
    page.coord_dd_btn.click()
    assert "DD" in received


def test_mainwindow_registers_settings_as_ninth_page(app):
    """Sidebar 设置 按钮应切换到第 9 页 (index=8) SettingsPage."""
    from src.app import MainWindow
    from src.pages.settings import SettingsPage

    win = MainWindow()
    assert win.stack.count() >= 9
    settings_widget = win.stack.widget(8)
    assert isinstance(settings_widget, SettingsPage)

    # Click sidebar settings button
    win.settings_btn.click()
    assert win.stack.currentIndex() == 8


def test_coordinate_format_propagates_to_paleo_map(app):
    """坐标格式变更必须能通过 bus 广播到 PaleoMapPage（订阅器存在即可）。"""
    from src.utils.preferences import get_preference_bus
    from src.pages.paleo_map.page import PaleoMapPage

    page = PaleoMapPage()
    assert hasattr(page, "_apply_coordinate_format"), "PaleoMapPage 必须暴露 _apply_coordinate_format 以接收坐标格式信号"
    # 触发应不抛异常
    get_preference_bus().coordinate_format_changed.emit("DMS")
    get_preference_bus().coordinate_format_changed.emit("DD")


def test_purge_all_caches_includes_registered_well_adjacent(tmp_path, monkeypatch):
    """#701: well-adjacent .cache dirs must be counted and purged."""
    from src.utils import cache_metrics as cm

    user_root = tmp_path / "user_cache"
    well_cache = tmp_path / "wells" / ".cache"
    well_cache.mkdir(parents=True)
    stale = well_cache / "OutOfDir_deadbeef.json"
    stale.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(cm, "_user_cache_root", lambda: user_root)
    monkeypatch.setattr(cm, "get_data_dir", lambda: tmp_path / "appdata")

    cm.register_well_cache_dir(well_cache)
    assert cm.compute_total_cache_mb() > 0
    released = cm.purge_all_caches()
    assert released > 0
    assert not stale.exists()
