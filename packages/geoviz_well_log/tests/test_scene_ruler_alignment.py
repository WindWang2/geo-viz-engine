"""#114: scene depth ruler must align with the well columns' content.

DepthRulerItem.depth_to_y mapped depth over the full item height with no
inset, and CrossWellScene._update_ruler sized the ruler with column_height
(header included) while wells sit at scene y=28 with content starting at
their track header — so the same depth sat a constant 28..84 px apart on
ruler vs columns (measured depth 0: ruler 0.0 vs well 84.0).

Mirrors tests/test_depth_ruler_sync.py::test_ruler_aligns_with_canvas_content
(the widget version) for the QGraphicsScene version.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from geoviz_well_log.models import CurveData
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.scene.cross_well_scene import CrossWellScene
from geoviz_well_log.scene.depth_ruler_item import DepthRulerItem


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _scene_with_well(qapp, top: float = 0.0, bottom: float = 1000.0):
    curve = CurveData(
        name="GR",
        unit="API",
        depth=[top, bottom],
        values=[1.0, 2.0],
        display_range=(0.0, 10.0),
    )
    scene = CrossWellScene()
    scene.add_well("W1", [CurveTrack([curve])])
    scene.set_well_depth_range("W1", top, bottom)
    return scene, scene.well_by_name("W1")


def _assert_ruler_aligns(scene, well):
    ruler = scene._ruler
    for depth in (well.depth_top, 500.0, 800.0, 123.456, well.depth_bottom):
        well_y = well.scenePos().y() + well.depth_to_y(depth)
        assert abs(ruler.depth_to_y(depth) - well_y) <= 1.0, (
            f"depth {depth}: ruler y={ruler.depth_to_y(depth)} "
            f"well y={well_y}"
        )


def test_scene_ruler_aligns_with_well_columns(qapp):
    """Same depth has the same scene Y on ruler and well content (<=1 px)."""
    scene, well = _scene_with_well(qapp)
    ruler = scene._ruler
    assert ruler._label_inset == pytest.approx(28.0)
    assert ruler._header_inset == pytest.approx(well.header_height)
    _assert_ruler_aligns(scene, well)


def test_scene_ruler_alignment_holds_after_depth_scale_change(qapp):
    scene, well = _scene_with_well(qapp)
    scene.set_depth_scale(2.0)
    _assert_ruler_aligns(scene, well)
    scene.set_depth_scale(0.3)
    _assert_ruler_aligns(scene, well)


def test_scene_ruler_height_spans_content_only(qapp):
    """Ruler height = label inset + header + tallest content; depth ticks
    span the content area, not the label/header bands."""
    scene, well = _scene_with_well(qapp)
    ruler = scene._ruler
    assert ruler._height == pytest.approx(
        28.0 + well.header_height + well.content_height
    )
    assert ruler.depth_to_y(well.depth_top) == pytest.approx(
        28.0 + well.header_height
    )
    assert ruler.depth_to_y(well.depth_bottom) == pytest.approx(
        28.0 + well.header_height + well.content_height
    )


def test_ruler_item_without_insets_keeps_full_height_mapping(qapp):
    """Zero-inset default preserves the raw mapping (widget parity)."""
    ruler = DepthRulerItem()
    ruler.set_depth_range(0.0, 1000.0)
    ruler.set_height(800.0)
    assert ruler.depth_to_y(0.0) == pytest.approx(0.0)
    assert ruler.depth_to_y(500.0) == pytest.approx(400.0)
    assert ruler.depth_to_y(1000.0) == pytest.approx(800.0)

    ruler.set_geometry_insets(28.0, 56.0)
    ruler.set_height(28.0 + 56.0 + 800.0)
    assert ruler.depth_to_y(0.0) == pytest.approx(84.0)
    assert ruler.depth_to_y(500.0) == pytest.approx(84.0 + 400.0)
    assert ruler.depth_to_y(1000.0) == pytest.approx(84.0 + 800.0)
