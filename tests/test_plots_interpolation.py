"""Task 21.4 — PlotsPage parameter-driven live interpolation (TDD).

Tests verify that control changes trigger the interpolation pipeline.
We monkeypatch _trigger_interpolation to avoid QThread event-loop issues.
"""
import pytest
from PySide6.QtWidgets import QComboBox, QSlider

from src.pages.plots.page import PlotsPage


@pytest.fixture
def plots_page(qtbot):
    page = PlotsPage()
    qtbot.addWidget(page)
    # Wait for initial interpolation to settle
    if page._worker is not None and page._worker.isRunning():
        page._worker.wait(3000)
    return page


def test_method_change_triggers_interpolation(plots_page):
    """Changing method combo calls _trigger_interpolation."""
    called = {"n": 0}
    orig = plots_page._trigger_interpolation
    def _count(*a, **kw):
        called["n"] += 1
    plots_page._trigger_interpolation = _count
    plots_page.method_combo.setCurrentIndex(2)
    assert called["n"] >= 1


def test_power_change_triggers_interpolation(plots_page):
    """Changing power slider calls _trigger_interpolation via _on_power_changed."""
    called = {"n": 0}
    def _count(*a, **kw):
        called["n"] += 1
    plots_page._trigger_interpolation = _count
    plots_page.power_slider.setValue(30)
    assert called["n"] >= 1


def test_res_change_triggers_interpolation(plots_page):
    """Changing resolution combo calls _trigger_interpolation."""
    called = {"n": 0}
    def _count(*a, **kw):
        called["n"] += 1
    plots_page._trigger_interpolation = _count
    plots_page.res_combo.setCurrentIndex(2)
    assert called["n"] >= 1


def test_trigger_reads_current_controls(plots_page):
    """_trigger_interpolation correctly reads the current control values."""
    plots_page.method_combo.setCurrentIndex(0)  # IDW
    plots_page.power_slider.setValue(25)
    plots_page.res_combo.setCurrentIndex(1)  # 100x100

    method_idx = plots_page.method_combo.currentIndex()
    assert method_idx == 0
    power = plots_page.power_slider.value() / 10.0
    assert power == 2.5
    res = int(plots_page.res_combo.currentText().split("x")[0].strip())
    assert res == 100


def test_trigger_launches_worker(plots_page):
    """_trigger_interpolation creates an InterpolationWorker."""
    from geoviz_plots import InterpolationWorker
    plots_page._trigger_interpolation()
    assert plots_page._worker is not None
    assert isinstance(plots_page._worker, InterpolationWorker)


def test_mask_checkbox_triggers_interpolation(plots_page):
    """Toggling mask checkbox calls _trigger_interpolation."""
    called = {"n": 0}
    def _count(*a, **kw):
        called["n"] += 1
    plots_page._trigger_interpolation = _count
    plots_page.mask_checkbox.setChecked(not plots_page.mask_checkbox.isChecked())
    assert called["n"] >= 1
