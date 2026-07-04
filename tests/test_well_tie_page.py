"""Unit tests for WellTieSidebar and WellTiePage integration."""
import pytest
from geoviz_well_tie.sidebar import WellTieSidebar
from src.pages.well_tie.page import WellTiePage

def test_well_tie_sidebar_initialization(qtbot):
    sidebar = WellTieSidebar()
    qtbot.addWidget(sidebar)
    assert sidebar.width() > 0

def test_well_tie_page_initialization(qtbot):
    page = WellTiePage()
    qtbot.addWidget(page)
    assert page._canvas is not None
    assert page._sidebar is not None
