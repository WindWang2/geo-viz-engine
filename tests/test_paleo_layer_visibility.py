"""Task 22a.2 — PaleoMapPage layer visibility toggles (TDD)."""
import pytest


def test_paleo_map_canvas_has_layers_property(qtbot):
    """PaleoMapCanvas must expose a public `layers` property."""
    from geoviz_paleo_map import PaleoMapCanvas
    canvas = PaleoMapCanvas()
    qtbot.addWidget(canvas)
    assert hasattr(canvas, "layers"), "PaleoMapCanvas needs a public `layers` property"
    assert isinstance(canvas.layers, list), "layers should return a list"


def test_paleo_layer_has_visible_attr():
    """PaleoLayer must have a `visible` attribute defaulting to True."""
    from geoviz_paleo_map.layers.base import PaleoLayer
    assert hasattr(PaleoLayer, "visible") or any(
        hasattr(cls, "visible") for cls in PaleoLayer.__mro__
    ), "PaleoLayer must have a visible attribute"


def test_layer_visible_defaults_true():
    """New layers should default to visible=True."""
    from geoviz_paleo_map.layers.wells_scatter import WellsScatterLayer
    layer = WellsScatterLayer([])
    assert getattr(layer, "visible", True) is True


def test_wells_scatter_checks_visible():
    """WellsScatterLayer must have visible attr."""
    from geoviz_paleo_map.layers.wells_scatter import WellsScatterLayer
    layer = WellsScatterLayer([])
    assert hasattr(layer, "visible"), "WellsScatterLayer must have visible attr"


def test_region_labels_checks_visible():
    """RegionLabelsLayer must have visible attr (inherited from PaleoLayer)."""
    from geoviz_paleo_map.layers.region_labels import RegionLabelsLayer
    from geoviz_paleo_map.style import FaciesStyleResolver
    from geoviz_well_log.renderer.pattern_engine import PatternEngine
    engine = PatternEngine()
    resolver = FaciesStyleResolver(engine)
    layer = RegionLabelsLayer([], resolver)
    assert hasattr(layer, "visible"), "RegionLabelsLayer must have visible attr"


def test_layer_toggle_handler_does_not_crash(qtbot):
    """Toggling wells/labels must flip the matching canvas layer.visible flags."""
    from src.pages.paleo_map.page import PaleoMapPage
    page = PaleoMapPage()
    qtbot.addWidget(page)
    assert hasattr(page.map_view, "layers"), "map_view must expose layers"

    wells = [layer for layer in page.map_view.layers if "Well" in type(layer).__name__]
    labels = [layer for layer in page.map_view.layers if "Label" in type(layer).__name__]
    assert wells, "PaleoMapCanvas must expose a wells layer"
    assert labels, "PaleoMapCanvas must expose a labels layer"

    page.toggle_wells.setChecked(False)
    assert all(layer.visible is False for layer in wells)
    assert all(layer.visible is True for layer in labels)

    page.toggle_labels.setChecked(False)
    assert all(layer.visible is False for layer in labels)

    page.toggle_wells.setChecked(True)
    page.toggle_labels.setChecked(True)
    assert all(layer.visible is True for layer in wells)
    assert all(layer.visible is True for layer in labels)
