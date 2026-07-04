import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.models import IntervalItem
from geoviz_well_log.renderer.interval_track import IntervalTrack


def _make_intervals():
    return [
        IntervalItem(top=0, bottom=100, name="System A"),
        IntervalItem(top=100, bottom=200, name="System B"),
        IntervalItem(top=200, bottom=300, name="System C"),
    ]


def test_interval_track_creation(qtbot):
    track = IntervalTrack(intervals=_make_intervals(), label="System", width=80)
    qtbot.addWidget(track)
    assert track.label == "System"
    assert track.width == 80


def test_interval_track_paint_no_crash(qtbot):
    track = IntervalTrack(intervals=_make_intervals(), label="System", width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_interval_track_export_render(qtbot):
    track = IntervalTrack(intervals=_make_intervals(), label="System", width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 80, 832))
    painter.end()


def test_interval_track_custom_colors(qtbot):
    colors = {"System A": "#ff0000", "System B": "#00ff00"}
    track = IntervalTrack(intervals=_make_intervals(), label="System", width=80,
                          colors=colors)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_interval_track_empty_intervals(qtbot):
    track = IntervalTrack(intervals=[], label="Empty", width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_interval_track_computes_one_label_policy_per_paint(qtbot, monkeypatch):
    from geoviz_well_log.renderer.label_layout import LabelPolicy

    calls = []

    def fake_policy(rect, depth_span, interval_heights):
        calls.append((depth_span, list(interval_heights)))
        return LabelPolicy(font_px=13, max_lines=1, min_label_height=14)

    monkeypatch.setattr("geoviz_well_log.renderer.interval_track.compute_label_policy", fake_policy)
    track = IntervalTrack(intervals=_make_intervals(), label="System", width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()

    assert calls == [(300, [pytest.approx(800 / 3)] * 3)]
