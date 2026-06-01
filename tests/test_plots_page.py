import pytest
import numpy as np
from PySide6.QtWidgets import QApplication
from src.pages.plots.page import PlotsPage

def test_plots_page_ui_and_demo_generation(qtbot):
    """Verify that PlotsPage initializes, generates demo discrete points, and populates the table."""
    page = PlotsPage()
    qtbot.addWidget(page)

    # 1. Assert UI controls are loaded
    assert page.points_table is not None
    assert page.method_combo is not None
    assert page.power_slider is not None
    assert page.mask_checkbox is not None
    assert page.res_combo is not None
    assert page.cmap_combo is not None
    assert page.step_spin is not None
    assert page.surface_plot is not None

    # 2. Assert demo points are generated and table populated
    assert len(page.points_x) == 15
    assert len(page.points_y) == 15
    assert len(page.points_z) == 15
    assert page.points_table.rowCount() == 15
    assert page.points_table.columnCount() == 3

    # Wait for async interpolation worker to finish initial run
    qtbot.waitUntil(lambda: "插值完成" in page.status_bar.text(), timeout=8000)
    assert page.surface_plot.grid_z is not None
    assert page.surface_plot.grid_x is not None

def test_plots_page_method_and_styling_changes(qtbot):
    """Verify that changing settings properly triggers new interpolation and updates visualization."""
    page = PlotsPage()
    qtbot.addWidget(page)
    
    # Wait for first calculation to finish
    qtbot.waitUntil(lambda: "插值完成" in page.status_bar.text(), timeout=8000)
    
    # 1. Change interpolation method to SciPy RBF
    page.method_combo.setCurrentIndex(4)  # SciPy RBF
    assert page.method_combo.currentText() == "SciPy RBF (径向基)"
    
    # Wait for new async run to complete
    qtbot.waitUntil(lambda: "SciPy RBF" in page.status_bar.text(), timeout=8000)
    assert page.surface_plot.grid_z is not None

    # 2. Change colormap
    page.cmap_combo.setCurrentIndex(2)  # viridis
    assert page.surface_plot.colormap_name == "viridis"

    # 3. Change step
    page.step_spin.setValue(0.5)
    qtbot.waitUntil(lambda: "等值线数" in page.status_bar.text(), timeout=8000)
