import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF


def test_depth_track_creation(qtbot):
    from geoviz_well_log.renderer.depth_track import DepthTrack
    track = DepthTrack(top_depth=0.0, bottom_depth=1000.0)
    qtbot.addWidget(track)
    assert track.label == "Depth"
    assert track.depth_top == 0.0
    assert track.depth_bottom == 1000.0


def test_depth_track_set_range(qtbot):
    from geoviz_well_log.renderer.depth_track import DepthTrack
    track = DepthTrack(top_depth=0.0, bottom_depth=1000.0)
    qtbot.addWidget(track)
    track.set_depth_range(100.0, 300.0)
    assert track.depth_top == 100.0
    assert track.depth_bottom == 300.0


def test_depth_track_paint_does_not_crash(qtbot):
    from geoviz_well_log.renderer.depth_track import DepthTrack
    track = DepthTrack(top_depth=0.0, bottom_depth=500.0)
    qtbot.addWidget(track)
    pm = QPixmap(60, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 60, 800))
    painter.end()


def test_depth_track_export_render(qtbot):
    from geoviz_well_log.renderer.depth_track import DepthTrack
    track = DepthTrack(top_depth=0.0, bottom_depth=500.0)
    qtbot.addWidget(track)
    pm = QPixmap(60, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 60, 832))
    painter.end()


def test_depth_track_tick_interval_adaptive(qtbot):
    """Tick interval adapts to visible depth range."""
    from geoviz_well_log.renderer.depth_track import DepthTrack
    track = DepthTrack(top_depth=0.0, bottom_depth=10000.0)
    qtbot.addWidget(track)

    # Large range -> larger tick interval
    track.set_depth_range(0, 10000)
    pm = QPixmap(60, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 60, 800))
    painter.end()
    assert track.tick_interval >= 50

    # Small range -> smaller tick interval
    track.set_depth_range(2500, 2520)
    pm2 = QPixmap(60, 800)
    painter2 = QPainter(pm2)
    track.paint_content(painter2, QRectF(0, 0, 60, 800))
    painter2.end()
    assert track.tick_interval <= 10
