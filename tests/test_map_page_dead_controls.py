"""Task 22a.4 — MapPage dead controls (TDD)."""
import pytest


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


def test_map_page_ruler_hidden(qtbot):
    """Ruler button should be hidden (no backend)."""
    from src.pages.map.page import MapPage
    from src.data.cache import DataCache
    cache = DataCache()
    page = MapPage(cache)
    qtbot.addWidget(page)
    assert page.btn_ruler.isHidden(), "Ruler button should be hidden (no implementation)"
