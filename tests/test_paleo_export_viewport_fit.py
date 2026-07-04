"""Regression tests for the professional export viewport fit.

Guards against the bug where the export copied the canvas zoom verbatim into a
page-sized viewport, leaving the map as a tiny square (~15% of the page) with
huge blank margins and microscopic chrome elements. The export must re-fit the
viewport so the data fills the page map area (matching the on-screen fit), and
the fixed-pixel chrome layers must scale up to the page resolution.
"""
import math

import pytest

pytest.importorskip("PySide6.QtPrintSupport")

from PySide6.QtGui import QImage

from geoviz_paleo_map import PaleoMapCanvas
from geoviz_paleo_map.export_professional import (
    export_professional_figure,
    _fit_zoom_for_bounds,
    _compute_data_bounds,
    _nice_step,
    _numeric_scale_denominator,
)


# 20 deg x 20 deg data box, same shape the page-export smoke tests use.
SAMPLE_FEATURES = [
    {
        "type": "Feature",
        "properties": {"name": "测试相区", "facies": "砂岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [110.0, 20.0], [120.0, 20.0], [120.0, 30.0],
                [110.0, 30.0], [110.0, 20.0],
            ]],
        },
    }
]


def test_fit_zoom_fills_page_with_max_scale():
    """20x20 deg data on a 4606x3153 (A4 landscape @300dpi) map area must
    produce the fill-and-crop zoom, not the canvas widget zoom (~6)."""
    # data 10x10 deg here (110..120, 20..30)
    zoom = _fit_zoom_for_bounds((110.0, 120.0, 20.0, 30.0), 4606, 3153)
    expected = math.log2(max(4606 / 10.0, 3153 / 10.0)) + 1.0
    assert zoom == pytest.approx(expected, abs=0.02)
    assert zoom > 8.0  # must be the fitted page zoom, nowhere near the old ~6


def test_compute_data_bounds_from_features():
    bounds = _compute_data_bounds(SAMPLE_FEATURES)
    assert bounds == pytest.approx((110.0, 120.0, 20.0, 30.0))


def test_nice_step_picks_round_values():
    assert _nice_step(20.0) == 5.0
    assert _nice_step(10.0) == 2.0
    assert _nice_step(50.0) == 10.0


def test_numeric_scale_denominator_is_round_and_sane():
    from geoviz_paleo_map.viewport import PaleoMapViewport
    # 20 deg lng extent at lat 30 on a 3153px-wide map (~A4 landscape map area)
    vp = PaleoMapViewport(center_lng=115.0, center_lat=30.0, zoom=8.30,
                          width=3153, height=2126)
    vp.clamp_to_bounds = False
    n = _numeric_scale_denominator(vp, 300)
    assert 1_000_000 <= n <= 50_000_000
    assert n % 1_000_000 == 0  # rounded to a whole million


def _non_background_fraction(path: str) -> float:
    """Fraction of sampled pixels that are clearly non-white (map content)."""
    img = QImage(path)
    assert not img.isNull(), f"could not load {path}"
    w, h = img.width(), img.height()
    total = 0
    colored = 0
    step = max(1, min(w, h) // 400)
    for y in range(0, h, step):
        for x in range(0, w, step):
            px = img.pixelColor(x, y)
            total += 1
            if min(px.red(), px.green(), px.blue()) < 230:
                colored += 1
    return colored / max(1, total)


def test_export_png_map_fills_the_page(qtbot, tmp_path):
    """The exported map must fill most of the page, not sit as a tiny square.

    Before the fix this was ~5-15% (tiny map, huge margins). After the fix the
    data is re-fit to fill the page, so the coloured map area dominates.
    """
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE_FEATURES, period_name="K1")
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    qtbot.waitExposed(canvas)

    out = tmp_path / "out.png"
    export_professional_figure(canvas, out, "png", title="K1岩相古地理图", dpi=150)

    frac = _non_background_fraction(str(out))
    # 35% cleanly separates the broken (~10%) from the fixed (>60%).
    assert frac > 0.35, f"map fills only {frac:.1%} of the page (expected >35%)"
