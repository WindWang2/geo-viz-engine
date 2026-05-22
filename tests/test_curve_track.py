import pytest
import numpy as np
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.models import CurveData, LineStyle


def _make_curve(name="GR", n=100, lo=0, hi=1000):
    depths = np.linspace(lo, hi, n).tolist()
    values = np.random.uniform(10, 150, n).tolist()
    return CurveData(name=name, unit="API", depth=depths, values=values,
                     display_range=(0, 150), color="#00ff00", line_style=LineStyle.SOLID)


def test_curve_track_creation(qtbot):
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve = _make_curve()
    track = CurveTrack(curves=[curve], label="GR", width=150)
    qtbot.addWidget(track)
    assert track.label == "GR"


def test_curve_track_paint_no_crash(qtbot):
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve = _make_curve(n=500)
    track = CurveTrack(curves=[curve], label="GR", width=150)
    qtbot.addWidget(track)
    track.set_depth_range(0, 1000)
    pm = QPixmap(150, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 150, 800))
    painter.end()


def test_curve_track_viewport_culling(qtbot):
    """Only points within visible range are rendered."""
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve = _make_curve(n=1000)
    track = CurveTrack(curves=[curve], label="GR", width=150)
    qtbot.addWidget(track)
    track.set_depth_range(400, 600)
    visible = track._visible_data(curve)
    # All visible depths should be within [400, 600] (with small margin)
    for d in visible[0]:
        assert 395 <= d <= 605


def test_curve_track_downsampling(qtbot):
    """Large dataset gets downsampled but preserves peaks."""
    from geoviz_well_log.renderer.curve_track import CurveTrack
    depths = list(range(10000))
    values = [50.0] * 10000
    values[5000] = 999.0  # spike
    curve = CurveData(name="GR", depth=depths, values=values, display_range=(0, 1000))
    track = CurveTrack(curves=[curve], label="GR", width=150)
    qtbot.addWidget(track)
    track.set_depth_range(0, 10000)
    downsampled = track._downsample(depths, values, 800)
    # Spike should be preserved
    assert 999.0 in downsampled[1]
    # Downsampled should be fewer points than original
    assert len(downsampled[0]) < 10000


def test_curve_track_log_scale(qtbot):
    """Log scale curve renders without crash."""
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve = CurveData(name="RT", unit="ohm.m", depth=list(range(100)),
                      values=[10 ** (i / 20) for i in range(100)],
                      display_range=(0.1, 1000), color="red")
    track = CurveTrack(curves=[curve], label="RT", width=150, log_scale=True)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pm = QPixmap(150, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 150, 800))
    painter.end()


def test_curve_track_export_render(qtbot):
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve = _make_curve(n=200)
    track = CurveTrack(curves=[curve], label="GR", width=150)
    qtbot.addWidget(track)
    track.set_depth_range(0, 1000)
    pm = QPixmap(150, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 150, 832))
    painter.end()
