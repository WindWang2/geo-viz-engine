"""FilledContourLayer tests - banded filled contours painted under the facies stack.

Phase-2, T3 / #247. The layer consumes ``list[BandedFill]`` produced by
``geoviz_plots.surface.marching_squares.extract_filled_contours``; these
tests build small synthetic bands and assert the layer paints visible,
non-white pixels inside the viewport and respects ``study_area_clip``.
"""
import numpy as np
from PySide6.QtGui import QColor, QImage, QPainter

from geoviz_paleo_map.layers.filled_contour import FilledContourLayer
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_plots.surface.marching_squares import BandedFill


def _band(level_min=0.0, level_max=1.0, color=None, ring=None):
    """Build a single-band BandedFill over a unit-square ring."""
    if ring is None:
        ring = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
    pts = np.array(ring, dtype=np.float64)
    return BandedFill(
        level_min=level_min,
        level_max=level_max,
        polygons=[pts],
        offsets=[np.array([0, len(pts)])],
        color=color or QColor(255, 0, 0),
        label=f"{level_min:g}-{level_max:g}",
    )


def _setup(width=200, height=200):
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)  # white background so any fill shows as non-white
    vp = PaleoMapViewport(5.0, 5.0, zoom=4.0, width=width, height=height)
    return img, vp


def test_filled_contour_layer_paints_band_pixels():
    """A band covering the viewport center must leave non-white pixels."""
    img, vp = _setup()
    layer = FilledContourLayer([_band()])
    p = QPainter(img); layer.paint(p, vp); p.end()
    c = img.pixelColor(100, 100)
    assert not (c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF), \
        "center pixel should be colored by the band fill"


def test_filled_contour_layer_empty_bands_paints_nothing():
    """No bands -> layer is a no-op (viewport stays white)."""
    img, vp = _setup()
    layer = FilledContourLayer([])
    p = QPainter(img); layer.paint(p, vp); p.end()
    c = img.pixelColor(100, 100)
    assert c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF


def test_filled_contour_layer_none_bands_is_noop():
    img, vp = _setup()
    layer = FilledContourLayer(None)
    p = QPainter(img); layer.paint(p, vp); p.end()
    c = img.pixelColor(100, 100)
    assert c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF


def test_filled_contour_layer_is_not_chrome():
    """FilledContourLayer goes through LayerPixmapCache (is_chrome=False)."""
    layer = FilledContourLayer([_band()])
    assert layer.is_chrome is False
    assert layer.visible is True


def test_filled_contour_layer_set_bands_replaces_content():
    img, vp = _setup()
    layer = FilledContourLayer([])
    layer.set_bands([_band()])
    p = QPainter(img); layer.paint(p, vp); p.end()
    c = img.pixelColor(100, 100)
    assert not (c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF)


def test_filled_contour_layer_study_area_clip_paints():
    """#853: painting with study_area_clip used to raise TypeError on the
    first paint — QPainter.setClipPath only accepts a QPainterPath and
    PySide6 does not implicitly convert a QPolygonF. The layer must clip
    via an explicit path: colored inside the clip, white outside it."""
    img, vp = _setup()
    # Clip polygon in lng/lat (world == plate-carree identity).
    clip = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    layer = FilledContourLayer([_band()], study_area_clip=clip)
    p = QPainter(img)
    try:
        layer.paint(p, vp)
    finally:
        p.end()
    c = img.pixelColor(100, 100)
    assert not (c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF), \
        "band must paint inside the clip region (no TypeError)"


def test_filled_contour_layer_study_area_clip_excludes_outside():
    """#853: the clip polygon must actually clip — a clip that does not cover
    the band leaves the viewport uncolored."""
    img, vp = _setup()
    # Clip polygon far away from the band at the viewport center.
    clip = [(90.0, 90.0), (95.0, 90.0), (95.0, 95.0), (90.0, 95.0), (90.0, 90.0)]
    layer = FilledContourLayer([_band()], study_area_clip=clip)
    p = QPainter(img)
    try:
        layer.paint(p, vp)
    finally:
        p.end()
    c = img.pixelColor(100, 100)
    assert c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF, \
        "band outside the clip polygon must not paint"
