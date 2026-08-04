import pytest
import numpy as np

from geoviz_well_log.models import (
    WellLogData, CurveData, LithologyInterval, FaciesInterval,
    IntervalItem, WellIntervals, FaciesData, LineStyle,
)
from geoviz_well_log.qpainter_builder import build_qpainter_tracks
from geoviz_well_log.renderer import (
    DepthTrack, CurveTrack, IntervalTrack,
    LithologyTrack, FaciesTrack, SystemsTractTrack,
)


def _make_full_data():
    """Create a WellLogData with all track types populated."""
    depths = np.linspace(2500, 2600, 100).tolist()
    return WellLogData(
        well_name="Test-1",
        top_depth=2500.0,
        bottom_depth=2600.0,
        curves=[
            CurveData(name="GR", unit="API", depth=depths,
                      values=np.random.uniform(10, 120, 100).tolist(),
                      display_range=(0, 150), color="#22c55e"),
            CurveData(name="AC", unit="us/ft", depth=depths,
                      values=np.random.uniform(40, 80, 100).tolist(),
                      display_range=(40, 240), color="#3b82f6",
                      line_style=LineStyle.DASHED),
            CurveData(name="RT", unit="ohm.m", depth=depths,
                      values=np.random.uniform(0.5, 200, 100).tolist(),
                      display_range=(0.2, 2000), color="#ef4444"),
        ],
        lithology=[
            LithologyInterval(top=2500, bottom=2530, lithology="砂岩", description="中砂岩"),
            LithologyInterval(top=2530, bottom=2560, lithology="泥岩", description="深灰色泥岩"),
            LithologyInterval(top=2560, bottom=2600, lithology="灰岩", description="生物灰岩"),
        ],
        facies=[
            FaciesInterval(top=2500, bottom=2530, facies="三角洲前缘"),
            FaciesInterval(top=2530, bottom=2600, facies="碳酸盐台地"),
        ],
        intervals=WellIntervals(
            system=[IntervalItem(top=2500, bottom=2600, name="中生界")],
            series=[IntervalItem(top=2500, bottom=2550, name="白垩系"),
                    IntervalItem(top=2550, bottom=2600, name="侏罗系")],
            formation=[IntervalItem(top=2500, bottom=2600, name="Test组")],
            systems_tract=[
                IntervalItem(top=2500, bottom=2550, name="TST"),
                IntervalItem(top=2550, bottom=2600, name="HST"),
            ],
            sequence=[IntervalItem(top=2500, bottom=2600, name="SQ1")],
            facies=FaciesData(
                phase=[IntervalItem(top=2500, bottom=2600, name="三角洲")],
                sub_phase=[IntervalItem(top=2500, bottom=2550, name="前三角洲"),
                           IntervalItem(top=2550, bottom=2600, name="三角洲前缘")],
                micro_phase=[IntervalItem(top=2500, bottom=2530, name="河口坝"),
                             IntervalItem(top=2530, bottom=2600, name="远砂坝")],
            ),
        ),
    )


def test_build_tracks_full_data(qtbot):
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    for t in tracks:
        qtbot.addWidget(t)
    assert len(tracks) >= 8
    types = [type(t).__name__ for t in tracks]
    assert "DepthTrack" in types
    assert "CurveTrack" in types
    assert "LithologyTrack" in types
    # Commit a60b7b44 redesigned the top-level `data.facies` path to emit a flat
    # IntervalTrack (沉积相 as flat items) instead of a nested FaciesTrack. The
    # nested FaciesTrack is now only built from `data.intervals.facies`. This
    # test feeds both, so the top-level path wins → IntervalTrack, not FaciesTrack.
    assert "IntervalTrack" in types
    assert "SystemsTractTrack" in types


def test_build_tracks_has_depth(qtbot):
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    for t in tracks:
        qtbot.addWidget(t)
    depth_tracks = [t for t in tracks if isinstance(t, DepthTrack)]
    assert len(depth_tracks) == 1


def test_build_tracks_curves_count(qtbot):
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    for t in tracks:
        qtbot.addWidget(t)
    curve_tracks = [t for t in tracks if isinstance(t, CurveTrack)]
    # AC+GR merged into 1 track, RT standalone (no RXO in data) = 2 tracks
    assert len(curve_tracks) == 2


def test_build_tracks_rt_is_log_scale(qtbot):
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    for t in tracks:
        qtbot.addWidget(t)
    rt_track = [t for t in tracks if isinstance(t, CurveTrack) and "RT" in t.label]
    assert len(rt_track) == 1
    assert rt_track[0]._log_scale is True


def test_build_tracks_empty_data(qtbot):
    """Minimal data — only DepthTrack created."""
    data = WellLogData(well_name="Empty", top_depth=0, bottom_depth=100)
    tracks = build_qpainter_tracks(data)
    for t in tracks:
        qtbot.addWidget(t)
    assert len(tracks) == 1
    assert isinstance(tracks[0], DepthTrack)


def test_build_tracks_no_intervals(qtbot):
    """Curves + lithology but no intervals."""
    data = WellLogData(
        well_name="Partial",
        top_depth=0,
        bottom_depth=100,
        curves=[CurveData(name="GR", depth=list(range(100)),
                          values=[50.0] * 100, display_range=(0, 150))],
        lithology=[LithologyInterval(top=0, bottom=50, lithology="砂岩"),
                   LithologyInterval(top=50, bottom=100, lithology="泥岩")],
    )
    tracks = build_qpainter_tracks(data)
    for t in tracks:
        qtbot.addWidget(t)
    types = [type(t).__name__ for t in tracks]
    assert "DepthTrack" in types
    assert "CurveTrack" in types
    assert "LithologyTrack" in types
    interval_tracks = [t for t in tracks if isinstance(t, IntervalTrack)]
    assert len(interval_tracks) == 0
