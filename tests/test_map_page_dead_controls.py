"""Task 22a.4 — MapPage dead controls (TDD)."""
import pytest
from PySide6.QtCore import Qt


# ---------------------------------------------------------------------------
# Layer visibility tests
# ---------------------------------------------------------------------------

def test_map_layer_has_visible_attr():
    """MapLayer base must have a visible attribute."""
    from geoviz_map.layers.base import MapLayer
    assert hasattr(MapLayer, "visible"), "MapLayer must have visible attr"


def test_wells_layer_visible_defaults_true():
    """WellsLayer should default to visible=True."""
    from geoviz_map.layers.wells import WellsLayer
    layer = WellsLayer([])
    assert layer.visible is True


def test_graticule_layer_visible_defaults_true():
    """GraticuleLayer should default to visible=True."""
    from geoviz_map.layers.graticule import GraticuleLayer
    layer = GraticuleLayer()
    assert layer.visible is True


# ---------------------------------------------------------------------------
# MapCanvas layers property
# ---------------------------------------------------------------------------

def test_map_canvas_has_layers_property(qtbot):
    """MapCanvas must expose a public layers property."""
    from geoviz_map import MapCanvas
    canvas = MapCanvas(wells=[], world_geojson={}, china_geojson={})
    qtbot.addWidget(canvas)
    assert hasattr(canvas, "layers"), "MapCanvas needs a public layers property"
    assert isinstance(canvas.layers, list), "layers should return a list"


# ---------------------------------------------------------------------------
# MapPage chip and checkbox wiring
# ---------------------------------------------------------------------------

def test_map_page_has_chips(qtbot):
    """MapPage must have three filter chips."""
    from src.pages.map.page import MapPage
    from src.data.cache import DataCache
    cache = DataCache()
    page = MapPage(cache)
    qtbot.addWidget(page)
    assert hasattr(page, "chip_all"), "MapPage must have chip_all"
    assert hasattr(page, "chip_interpreted"), "MapPage must have chip_interpreted"
    assert hasattr(page, "chip_gas"), "MapPage must have chip_gas"
    assert page.chip_all.isCheckable()
    assert page.chip_interpreted.isCheckable()
    assert page.chip_gas.isCheckable()


def test_map_page_layer_checkboxes_wired(qtbot):
    """chk_wells and chk_grids toggling must not crash."""
    from src.pages.map.page import MapPage
    from src.data.cache import DataCache
    cache = DataCache()
    page = MapPage(cache)
    qtbot.addWidget(page)
    page.chk_wells.setChecked(False)
    page.chk_grids.setChecked(False)
    page.chk_wells.setChecked(True)
    page.chk_grids.setChecked(True)


def test_map_page_chip_filter_does_not_crash(qtbot):
    """Clicking filter chips must not crash."""
    from src.pages.map.page import MapPage
    from src.data.cache import DataCache
    cache = DataCache()
    page = MapPage(cache)
    qtbot.addWidget(page)
    page.chip_all.setChecked(True)
    page.chip_interpreted.setChecked(True)
    page.chip_gas.setChecked(True)


def test_map_page_chip_filters_differ_by_has_data(qtbot):
    """#704: 有数据 / 无数据 chips must filter opposite sets, not both has_data."""
    from src.pages.map.page import MapPage
    from src.data.cache import DataCache

    page = MapPage(DataCache())
    qtbot.addWidget(page)
    if not page.wells:
        pytest.skip("no well markers to filter")

    for i in range(page.well_list.count()):
        item = page.well_list.item(i)
        name = item.data(Qt.UserRole)
        marker = next((w for w in page.wells if w.name == name), None)
        if marker is None:
            continue
        page.chip_interpreted.setChecked(True)
        assert item.isHidden() is (not marker.has_data)
        page.chip_gas.setChecked(True)
        assert item.isHidden() is marker.has_data


def test_map_page_callout_does_not_label_has_data_as_gas(qtbot):
    """#704: binding a log file is not a gas show."""
    from src.pages.map.page import MapPage
    from src.data.cache import DataCache

    page = MapPage(DataCache())
    qtbot.addWidget(page)
    with_data = next((w for w in page.wells if w.has_data), None)
    if with_data is None:
        pytest.skip("no well with bound logs")
    page._on_well_clicked(with_data.name)
    assert "含气" not in page.well_callout_desc.text()
    assert "有测井" in page.well_callout_desc.text()


def test_map_page_ruler_hidden(qtbot):
    """Ruler button should be hidden (no backend)."""
    from src.pages.map.page import MapPage
    from src.data.cache import DataCache
    cache = DataCache()
    page = MapPage(cache)
    qtbot.addWidget(page)
    assert page.btn_ruler.isHidden(), "Ruler button should be hidden (no implementation)"
