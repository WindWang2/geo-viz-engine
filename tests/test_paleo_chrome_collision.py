"""Chrome-priority label placement: region labels must avoid decorations.

Decoration-priority placement — the legend / north arrow / scale bar paint at
fixed corners, and region labels steer clear of their footprints (registered
via reserved_rect into the collision detector) instead of overlapping them.
"""
import pytest

pytest.importorskip("PySide6.QtGui")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.legend import LegendLayer
from geoviz_paleo_map.layers.north_arrow import NorthArrowLayer
from geoviz_paleo_map.layers.scale_bar import ScaleBarLayer
from geoviz_paleo_map.layers.region_labels import RegionLabelsLayer
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_well_log.renderer.pattern_engine import PatternEngine


def _resolver():
    return FaciesStyleResolver(PatternEngine())


def _viewport():
    return PaleoMapViewport(center_lng=115.0, center_lat=31.5, zoom=4.0,
                            width=1200, height=800)


def test_chrome_layers_expose_reserved_rect():
    vp = _viewport()
    for layer in (NorthArrowLayer(), ScaleBarLayer(),
                  LegendLayer({"砂岩", "泥岩"}, _resolver())):
        r = layer.reserved_rect(vp)
        assert isinstance(r, QRectF)
        assert r.width() > 0 and r.height() > 0


def test_region_label_skips_chrome_footprint(qtbot):
    """A label whose centroid falls inside a reserved chrome rect is dropped."""
    vp = _viewport()
    # One big polygon covering the whole viewport; its centroid is screen-center.
    feat = {
        "type": "Feature",
        "properties": {"name": "测试相区", "facies": "砂岩"},
        "geometry": {"type": "Polygon", "coordinates": [[
            [100.0, 20.0], [130.0, 20.0], [130.0, 43.0],
            [100.0, 43.0], [100.0, 20.0],
        ]]},
    }
    layer = RegionLabelsLayer([feat], _resolver(), font_size=11)

    img = QImage(1200, 800, QImage.Format.Format_ARGB32)
    img.fill(0)

    # Without chrome reservation, the label paints.
    p = QPainter(img)
    layer.chrome_rects = []
    layer.paint(p, vp)
    p.end()
    assert "测试相区" in layer.visible_labels

    # Reserve a rect over the screen-center centroid → label must be skipped.
    layer.chrome_rects = [QRectF(550, 370, 100, 60)]
    p = QPainter(img)
    layer.paint(p, vp)
    p.end()
    assert "测试相区" not in layer.visible_labels


# --- huge-rect O(1) rejection (#146) ------------------------------------------


def test_huge_finite_rect_rejected_without_grid_walk():
    """A finite-but-huge rect (projection blow-up) used to walk ~1e14 hash
    cells and hang the UI thread; it must be rejected in O(1) (#146)."""
    from PySide6.QtCore import QRectF

    from geoviz_common.collision import CollisionDetector

    det = CollisionDetector(cell_size=120.0)
    huge = QRectF(-1e9, -1e9, 2e9, 2e9)
    assert det.try_add(huge) is False  # rejected, not walked
    # normal labels still work after the reject
    assert det.try_add(QRectF(0.0, 0.0, 80.0, 20.0)) is True
