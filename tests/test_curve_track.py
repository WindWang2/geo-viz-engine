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
        assert 380 <= d <= 620


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


def test_curve_track_path_caching(qtbot):
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve = _make_curve(n=200)
    track = CurveTrack(curves=[curve], label="GR", width=150)
    qtbot.addWidget(track)
    track.set_depth_range(0, 1000)

    # Render 1st time
    pm1 = QPixmap(150, 800)
    painter1 = QPainter(pm1)
    track.paint_content(painter1, QRectF(0, 0, 150, 800))
    painter1.end()

    # Assert downsampled-array cache is populated
    assert hasattr(track, "_downsampled_cache")
    assert curve.name in track._downsampled_cache
    _, depths1, values1 = track._downsampled_cache[curve.name]

    # Render 2nd time with exact same geometry
    pm2 = QPixmap(150, 800)
    painter2 = QPainter(pm2)
    track.paint_content(painter2, QRectF(0, 0, 150, 800))
    painter2.end()

    # Assert cached arrays were reused (identical memory ID)
    _, depths2, values2 = track._downsampled_cache[curve.name]
    assert depths1 is depths2
    assert values1 is values2

    # Alter depth range to invalidate cache
    track.set_depth_range(100, 900)
    pm3 = QPixmap(150, 800)
    painter3 = QPainter(pm3)
    track.paint_content(painter3, QRectF(0, 0, 150, 800))
    painter3.end()

    # Assert cache entry changed and arrays were re-generated (new objects)
    _, depths3, values3 = track._downsampled_cache[curve.name]
    assert depths1 is not depths3


def test_curve_track_multi_scale_rendering(qtbot):
    from geoviz_well_log.renderer.curve_track import CurveTrack
    c1 = CurveData(name="GR", unit="API", depth=[0, 100], values=[10, 150], display_range=(0.0, 150.0), color="green")
    c2 = CurveData(name="AC", unit="us/ft", depth=[0, 100], values=[40, 140], display_range=(40.0, 140.0), color="blue")
    track = CurveTrack(curves=[c1, c2], label="GR/AC", width=150)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pm = QPixmap(150, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 150, 800))
    painter.end()
    assert len(track._curves) == 2


