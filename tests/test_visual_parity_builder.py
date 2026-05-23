import pytest
from geoviz_well_log.qpainter_builder import build_qpainter_tracks
from geoviz_well_log.models import WellLogData, CurveData, WellIntervals, IntervalItem


def _make_full_data():
    return WellLogData(
        well_name="TEST-1",
        top_depth=0.0,
        bottom_depth=100.0,
        curves=[
            CurveData(name="AC", depth=list(range(100)), values=[60.0]*100, display_range=(40, 80)),
            CurveData(name="GR", depth=list(range(100)), values=[50.0]*100, display_range=(0, 150)),
            CurveData(name="RT", depth=list(range(100)), values=[10.0]*100, display_range=(0.1, 1000)),
            CurveData(name="RXO", depth=list(range(100)), values=[5.0]*100, display_range=(0.1, 1000)),
        ],
        intervals=WellIntervals(
            system=[IntervalItem(top=0, bottom=50, name="C"), IntervalItem(top=50, bottom=100, name="P")],
            series=[IntervalItem(top=0, bottom=50, name="C1"), IntervalItem(top=50, bottom=100, name="P1")],
            formation=[IntervalItem(top=0, bottom=50, name="F1"), IntervalItem(top=50, bottom=100, name="F2")],
        ),
    )


def test_builder_merges_curves(qtbot):
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    for t in tracks:
        qtbot.addWidget(t)
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve_tracks = [t for t in tracks if isinstance(t, CurveTrack)]
    assert len(curve_tracks) <= 2  # AC/GR merged, RT/RXO merged
    total_curves = sum(len(t._curves) for t in curve_tracks)
    assert total_curves == 4


def test_builder_adds_group_name_to_stratigraphy(qtbot):
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    for t in tracks:
        qtbot.addWidget(t)
    strat_tracks = [t for t in tracks if getattr(t, 'group_name', '') == '地层系统']
    assert len(strat_tracks) >= 2


def test_builder_reduces_total_width(qtbot):
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    for t in tracks:
        qtbot.addWidget(t)
    total = sum(t.width for t in tracks)
    assert total < 1200


def test_builder_track_order_depth_first(qtbot):
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    for t in tracks:
        qtbot.addWidget(t)
    from geoviz_well_log.renderer.depth_track import DepthTrack
    assert isinstance(tracks[0], DepthTrack)
