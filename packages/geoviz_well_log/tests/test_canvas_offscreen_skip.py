"""Off-screen WellLogCanvas skips rasterization until visible."""
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


def test_hidden_canvas_skips_repaint(qapp):
    canvas = _make_canvas()  # never shown -> visibleRegion empty
    canvas.set_depth_range(2000.0, 3000.0)
    assert canvas._cache_dirty is True
    canvas.repaint()  # synchronous paint; should early-return while hidden
    qapp.processEvents()
    assert canvas._cache_dirty is True  # deferred, not rasterized
