"""Task 21.5 — Map → WellLog bidirectional linkage (TDD)."""
import pytest
from PySide6.QtCore import QCoreApplication, Qt

from src.data.cache import DataCache
from src.pages.map.page import MapPage


@pytest.fixture
def map_page(qtbot):
    cache = DataCache()
    page = MapPage(cache)
    qtbot.addWidget(page)
    return page


def test_map_page_emits_open_well_log_requested_signal(map_page):
    """MapPage exposes an open_well_log_requested(str) signal."""
    assert hasattr(map_page, "open_well_log_requested")
    # Verify signal connectivity by connecting a slot
    received = []
    map_page.open_well_log_requested.connect(lambda name: received.append(name))
    # Emit via the callout button handler
    map_page.well_callout_title.setText("📍 test_well")
    map_page._on_open_log_clicked()
    assert "test_well" in received


def test_mainwindow_connects_open_well_log_signal(qtbot):
    """MainWindow connects MapPage.open_well_log_requested to WellLogPage.load_well + switch page."""
    from src.app import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    if win.map_page is None:
        pytest.skip("MapPage unavailable")

    # Verify the signal exists on the live map_page
    assert hasattr(win.map_page, "open_well_log_requested")

    # Track which page was switched to
    switched_to = []
    orig = win._switch_page
    def _capture(idx):
        switched_to.append(idx)
        orig(idx)
    win._switch_page = _capture

    # Track which well was loaded
    loaded = []
    orig_load = win.well_log_page.load_well
    def _cap_load(name):
        loaded.append(name)
    win.well_log_page.load_well = _cap_load

    # Emit the signal from the map page
    win.map_page.open_well_log_requested.emit("demo_well")

    # WellLogPage should have been asked to load + page switched to 2 (well_log index)
    assert "demo_well" in loaded
    assert 2 in switched_to


def test_open_log_button_emits_signal_with_well_name(map_page):
    """Clicking the callout's open_log_btn emits the signal with the current well name."""
    received = []
    map_page.open_well_log_requested.connect(lambda name: received.append(name))
    map_page.well_callout_title.setText("📍 well_xyz")
    map_page.open_log_btn.click()
    assert "well_xyz" in received
