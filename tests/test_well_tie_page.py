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
    assert "0.85" not in page._sidebar._score_label.text()
    assert "0.925" not in page._sidebar._score_label.text()


def test_well_tie_page_auto_tie_uses_computed_metrics(qtbot):
    """#675: Auto-Tie must not stamp a hardcoded R=0.925."""
    page = WellTiePage()
    qtbot.addWidget(page)
    page._on_auto_tie()
    text = page._sidebar._score_label.text()
    assert "0.925" not in text
    assert "R:" in text
    assert page._last_tie is not None
    assert "r_score" in page._last_tie
