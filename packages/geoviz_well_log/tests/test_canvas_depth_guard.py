"""WellLogCanvas.set_depth_range no-op guard tests."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_canvas():
    from geoviz_well_log.models import CurveData
    from geoviz_well_log.renderer.canvas import WellLogCanvas
    from geoviz_well_log.renderer.curve_track import CurveTrack

    curve = CurveData(
        name="GR", unit="API",
        depth=[float(i) for i in range(100)],
        values=[float(i) for i in range(100)],
        display_range=(0.0, 100.0),
    )
    canvas = WellLogCanvas()
    canvas.add_track(CurveTrack([curve]))
    return canvas


def test_identical_range_is_noop(qapp):
    canvas = _make_canvas()
    canvas.set_depth_range(2000.0, 3000.0)
    canvas._cache_dirty = False

    emissions = []
    canvas.depth_range_changed.connect(lambda t, b: emissions.append((t, b)))
    canvas.set_depth_range(2000.0, 3000.0)

    assert emissions == []
    assert canvas._cache_dirty is False


def test_changed_range_invalidates_and_emits(qapp):
    canvas = _make_canvas()
    canvas.set_depth_range(2000.0, 3000.0)
    canvas._cache_dirty = False

    emissions = []
    canvas.depth_range_changed.connect(lambda t, b: emissions.append((t, b)))
    canvas.set_depth_range(2100.0, 3000.0)

    assert emissions == [(2100.0, 3000.0)]
    assert canvas._cache_dirty is True
