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
    from unittest.mock import patch

    from src.pages.paleo_map.page import PaleoMapPage
    page = PaleoMapPage()
    qtbot.addWidget(page)
    with (
        patch.object(page.map_view, "fit_viewport_to_data") as fit_spy,
        patch.object(page.map_view, "set_zoom") as zoom_spy,
    ):
        page.btn_fit.click()
    fit_spy.assert_called_once()
    zoom_spy.assert_not_called()
