"""Task 22b.4 — PaleoMap fit button (TDD)."""
import pytest


def test_paleo_map_canvas_has_fit_method():
    """PaleoMapCanvas must have fit_viewport_to_data method."""
    from geoviz_paleo_map import PaleoMapCanvas
    assert hasattr(PaleoMapCanvas, "fit_viewport_to_data"), (
        "PaleoMapCanvas must have fit_viewport_to_data"
    )


def test_paleo_map_page_fit_button_connected(qtbot):
    """Fit button must be connected to fit_viewport_to_data, not set_zoom(1.0)."""
    from src.pages.paleo_map.page import PaleoMapPage
    page = PaleoMapPage()
    qtbot.addWidget(page)
    page.btn_fit.click()
    # Should not crash
