"""Performance tests for QPainter track building."""

import time

import pytest

from geoviz_well_log.models import CurveData, WellLogData
from geoviz_well_log.qpainter_builder import build_qpainter_tracks


def test_track_build_speed(qtbot):
    n = 5000
    data = WellLogData(
        well_name="PERF-1",
        top_depth=0.0,
        bottom_depth=float(n),
        curves=[
            CurveData(
                name="GR",
                depth=list(range(n)),
                values=[50.0] * n,
                display_range=(0, 150),
            ),
            CurveData(
                name="RT",
                depth=list(range(n)),
                values=[10.0] * n,
                display_range=(0.1, 1000),
            ),
        ],
    )
    start = time.monotonic()
    tracks = build_qpainter_tracks(data)
    elapsed = time.monotonic() - start
    for t in tracks:
        qtbot.addWidget(t)
    assert elapsed < 0.5, f"Track building took {elapsed:.3f}s, expected <0.5s"
    assert len(tracks) > 0
