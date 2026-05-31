"""Tests for shared chrome panel in compare mode (Phase 11.7-C)."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget


@pytest.fixture
def simple_features():
    return [{
        "type": "Feature",
        "properties": {"facies": "潮坪", "name": "潮坪区"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[110.0, 25.0], [120.0, 25.0],
                             [120.0, 35.0], [110.0, 35.0], [110.0, 25.0]]],
        },
    }]


@pytest.fixture
def other_features():
    return [{
        "type": "Feature",
        "properties": {"facies": "陆棚", "name": "陆棚区"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[100.0, 25.0], [110.0, 25.0],
                             [110.0, 35.0], [100.0, 35.0], [100.0, 25.0]]],
        },
    }]


class TestShowChromeFlag:
    def test_default_includes_chrome_layers(self, qtbot, simple_features):
        from geoviz_paleo_map import PaleoMapCanvas
        from geoviz_paleo_map.layers.title import TitleLayer
        from geoviz_paleo_map.layers.north_arrow import NorthArrowLayer
        from geoviz_paleo_map.layers.scale_bar import ScaleBarLayer
        from geoviz_paleo_map.layers.legend import LegendLayer

        canvas = PaleoMapCanvas()
        qtbot.addWidget(canvas)
        canvas.load_features(simple_features, period_name="震旦纪")

        layer_types = {type(layer) for layer in canvas._layers}
        assert TitleLayer in layer_types
        assert NorthArrowLayer in layer_types
        assert ScaleBarLayer in layer_types
        assert LegendLayer in layer_types

    def test_show_chrome_false_omits_chrome(self, qtbot, simple_features):
        from geoviz_paleo_map import PaleoMapCanvas
        from geoviz_paleo_map.layers.title import TitleLayer
        from geoviz_paleo_map.layers.north_arrow import NorthArrowLayer
        from geoviz_paleo_map.layers.scale_bar import ScaleBarLayer
        from geoviz_paleo_map.layers.legend import LegendLayer

        canvas = PaleoMapCanvas(show_chrome=False)
        qtbot.addWidget(canvas)
        canvas.load_features(simple_features, period_name="震旦纪")

        layer_types = {type(layer) for layer in canvas._layers}
        assert TitleLayer not in layer_types
        assert NorthArrowLayer not in layer_types
        assert ScaleBarLayer not in layer_types
        assert LegendLayer not in layer_types

    def test_facies_names_exposed(self, qtbot, simple_features):
        from geoviz_paleo_map import PaleoMapCanvas

        canvas = PaleoMapCanvas(show_chrome=False)
        qtbot.addWidget(canvas)
        canvas.load_features(simple_features, period_name="震旦纪")
        assert canvas.facies_names() == {"潮坪"}


class TestSharedChromePanel:
    def test_merges_facies_from_both_canvases(self, qtbot, simple_features,
                                              other_features):
        from geoviz_paleo_map import PaleoMapCanvas
        from geoviz_paleo_map.shared_chrome_panel import SharedChromePanel

        canvas_a = PaleoMapCanvas(show_chrome=False)
        canvas_b = PaleoMapCanvas(show_chrome=False)
        qtbot.addWidget(canvas_a)
        qtbot.addWidget(canvas_b)
        canvas_a.load_features(simple_features, period_name="震旦纪")
        canvas_b.load_features(other_features, period_name="寒武纪")

        panel = SharedChromePanel(canvas_a, canvas_b)
        qtbot.addWidget(panel)
        assert panel.merged_facies() == {"潮坪", "陆棚"}

    def test_refreshes_when_canvas_reloads(self, qtbot, simple_features,
                                           other_features):
        from geoviz_paleo_map import PaleoMapCanvas
        from geoviz_paleo_map.shared_chrome_panel import SharedChromePanel

        canvas_a = PaleoMapCanvas(show_chrome=False)
        canvas_b = PaleoMapCanvas(show_chrome=False)
        qtbot.addWidget(canvas_a)
        qtbot.addWidget(canvas_b)
        canvas_a.load_features(simple_features, period_name="震旦纪")
        canvas_b.load_features([], period_name="")

        panel = SharedChromePanel(canvas_a, canvas_b)
        qtbot.addWidget(panel)
        assert panel.merged_facies() == {"潮坪"}

        canvas_b.load_features(other_features, period_name="寒武纪")
        assert panel.merged_facies() == {"潮坪", "陆棚"}

    def test_panel_paints_without_error(self, qtbot, simple_features,
                                        other_features):
        from PySide6.QtGui import QPixmap

        from geoviz_paleo_map import PaleoMapCanvas
        from geoviz_paleo_map.shared_chrome_panel import SharedChromePanel

        canvas_a = PaleoMapCanvas(show_chrome=False)
        canvas_b = PaleoMapCanvas(show_chrome=False)
        qtbot.addWidget(canvas_a)
        qtbot.addWidget(canvas_b)
        canvas_a.load_features(simple_features, period_name="震旦纪")
        canvas_b.load_features(other_features, period_name="寒武纪")

        panel = SharedChromePanel(canvas_a, canvas_b)
        qtbot.addWidget(panel)
        panel.resize(200, 600)
        # render() should produce a pixmap without errors
        pixmap = panel.grab()
        assert isinstance(pixmap, QPixmap)
        assert pixmap.width() > 0
