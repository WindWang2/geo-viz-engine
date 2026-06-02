"""Task 21.3 — DataPage KPI dynamic refresh + WellDetailPanel side-out (TDD)."""
import pytest
from PySide6.QtWidgets import QLabel, QFrame

from src.data.cache import DataCache
from src.pages.data.page import DataPage


@pytest.fixture
def data_page(qtbot):
    cache = DataCache()
    page = DataPage(cache)
    qtbot.addWidget(page)
    return page


def test_kpi_values_bound_to_cache(data_page):
    """KPI cards expose value labels accessible for dynamic refresh."""
    assert hasattr(data_page, "_kpi_value_labels")
    assert isinstance(data_page._kpi_value_labels, dict)
    assert "registered_wells" in data_page._kpi_value_labels
    assert "cache_size" in data_page._kpi_value_labels
    assert "data_format" in data_page._kpi_value_labels
    assert "engine_speed" in data_page._kpi_value_labels


def test_refresh_kpis_updates_well_count(data_page):
    """refresh_kpis recomputes registered well count from cache."""
    data_page.refresh_kpis()
    label = data_page._kpi_value_labels["registered_wells"]
    text = label.text()
    # Text should contain digit reflecting len(cache.wells) and "口"
    assert "口" in text
    # Default cache loads the well_coordinates.json — expect a real count, not the hard-coded 46
    import re
    m = re.search(r"(\d+)", text)
    assert m is not None
    count = int(m.group(1))
    # Real well count should be reflected
    from src.utils.paths import get_data_dir
    expected = len(data_page.cache.get_well_coordinates(get_data_dir() / "well_coordinates.json"))
    assert count == expected


def test_refresh_kpis_updates_cache_size(data_page):
    """Cache size KPI is recomputed as MB string."""
    data_page.refresh_kpis()
    label = data_page._kpi_value_labels["cache_size"]
    text = label.text()
    assert "MB" in text or "GB" in text


def test_well_detail_panel_exists(data_page):
    """DataPage has a WellDetailPanel as a hideable side panel."""
    assert hasattr(data_page, "_detail_panel")
    panel = data_page._detail_panel
    assert isinstance(panel, QFrame)
    # Initially hidden
    assert not panel.isVisible()


def test_show_well_detail_displays_panel(qtbot, data_page):
    """Calling _show_well_detail(name) reveals the panel with the well name."""
    from src.utils.paths import get_data_dir
    wells = data_page.cache.get_well_coordinates(get_data_dir() / "well_coordinates.json")
    if not wells:
        pytest.skip("No wells loaded")
    name = wells[0].name
    data_page.show()
    data_page._show_well_detail(name)
    qtbot.waitExposed(data_page._detail_panel)
    assert data_page._detail_panel.isVisible()
    assert hasattr(data_page, "_detail_name_label")
    assert name in data_page._detail_name_label.text()


def test_hide_well_detail(qtbot, data_page):
    """Closing the panel hides it."""
    data_page.show()
    data_page._show_well_detail("test_well")
    data_page._hide_well_detail()
    assert not data_page._detail_panel.isVisible()
