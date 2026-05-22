"""Integration test: load data -> build tracks -> render -> export."""
import os
import tempfile

from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.models import CurveData, LineStyle, WellLogData
from geoviz_well_log.export_qpainter import export_svg, export_pdf, export_png
import numpy as np


def _make_well_log_data(n_curves=3, n_points=2000):
    """Simulate a realistic well with 3 curves and 2000 sample points."""
    depths = np.linspace(2500, 2600, n_points).tolist()
    curves = [
        CurveData(name="GR", unit="API", depth=depths,
                  values=np.random.uniform(10, 120, n_points).tolist(),
                  display_range=(0, 150), color="#22c55e"),
        CurveData(name="AC", unit="us/ft", depth=depths,
                  values=np.random.uniform(40, 80, n_points).tolist(),
                  display_range=(40, 240), color="#3b82f6", line_style=LineStyle.DASHED),
        CurveData(name="RT", unit="ohm.m", depth=depths,
                  values=np.random.uniform(0.5, 200, n_points).tolist(),
                  display_range=(0.2, 2000), color="#ef4444"),
    ]
    return WellLogData(well_name="Test-1", top_depth=2500, bottom_depth=2600, curves=curves)


def test_full_pipeline_svg_export(qtbot):
    data = _make_well_log_data()
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(360, 800)

    # Build tracks
    canvas.add_track(DepthTrack(top_depth=data.top_depth, bottom_depth=data.bottom_depth))
    for c in data.curves:
        is_log = c.name in ("RT", "RXO")
        canvas.add_track(CurveTrack(curves=[c], label=f"{c.name} ({c.unit})",
                                    width=100, log_scale=is_log))
    canvas.set_depth_range(data.top_depth, data.bottom_depth)

    # Export SVG
    with tempfile.TemporaryDirectory() as tmp:
        svg_path = os.path.join(tmp, "integration.svg")
        export_svg(canvas, svg_path)
        assert os.path.exists(svg_path)
        content = open(svg_path).read()
        # SVG should contain path elements (vector curves)
        assert "path" in content.lower()
        assert os.path.getsize(svg_path) > 500


def test_full_pipeline_pdf_export(qtbot):
    data = _make_well_log_data(n_points=5000)
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(360, 800)
    canvas.add_track(DepthTrack(top_depth=data.top_depth, bottom_depth=data.bottom_depth))
    for c in data.curves:
        is_log = c.name in ("RT", "RXO")
        canvas.add_track(CurveTrack(curves=[c], label=f"{c.name} ({c.unit})",
                                    width=100, log_scale=is_log))
    canvas.set_depth_range(data.top_depth, data.bottom_depth)

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "integration.pdf")
        export_pdf(canvas, pdf_path)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 500


def test_depth_zoom_performance(qtbot):
    """Zooming should be fast even with 5000 points."""
    import time
    data = _make_well_log_data(n_points=5000)
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(260, 800)
    canvas.add_track(DepthTrack(top_depth=data.top_depth, bottom_depth=data.bottom_depth))
    canvas.add_track(CurveTrack(curves=[data.curves[0]], label="GR", width=200))
    canvas.set_depth_range(data.top_depth, data.bottom_depth)

    # Force layout
    canvas.show()

    # Simulate zoom
    start = time.time()
    for _ in range(10):
        canvas.set_depth_range(2520, 2540)
        canvas.set_depth_range(2500, 2600)
    elapsed = time.time() - start
    assert elapsed < 1.0, f"10 zoom cycles took {elapsed:.2f}s -- too slow"
