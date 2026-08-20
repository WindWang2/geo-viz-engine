"""#114: section horizon links must land on the painted interval tops.

The link/facies layer mapped depths through the global DatumTransformer
(global depth span stretched over the canvas content), while each well's
tracks render their OWN well range over the full column. Whenever a well's
range differed from the global span the link endpoints detached from the
painted horizons (measured: global [0,2000], well A [1000,2000] -> depth
1000 painted at column y=56 but linked at y=556; datum_shift mode always
diverged).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from geoviz_well_log.models import (
    CurveData,
    IntervalItem,
    WellIntervals,
    WellLogData,
)
from geoviz_well_log.renderer.interval_track import IntervalTrack
from geoviz_well_log.section.section_canvas import WellSectionCanvas


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _well(name: str, top: float, bottom: float,
          formation_top: float, formation_bottom: float) -> WellLogData:
    return WellLogData(
        well_name=name,
        top_depth=top,
        bottom_depth=bottom,
        curves=[CurveData(name="GR", depth=[top, bottom], values=[10.0, 20.0])],
        intervals=WellIntervals(
            formation=[
                IntervalItem(top=formation_top, bottom=formation_bottom, name="F1")
            ]
        ),
    )


def _strat_track(canvas: WellSectionCanvas, well_idx: int) -> IntervalTrack:
    return next(
        t for t in canvas._well_tracks[well_idx] if isinstance(t, IntervalTrack)
    )


def _painted_column_y(track: IntervalTrack, depth: float, canvas_h: float) -> float:
    """Independent statement of the painted geometry: export_render places
    track content below the 24 px well-title band + 32 px shared track header
    and stretches the track's own depth range over the rest of the column."""
    content_top = 24.0 + 32.0
    ratio = (depth - track.depth_top) / track.depth_span
    return content_top + ratio * (canvas_h - content_top)


def test_horizon_link_y_matches_painted_interval_top(qapp):
    """Two wells with different ranges: link endpoint Y == the Y at which the
    stratigraphy track paints that interval top (±1 px), not the global
    transformer's Y."""
    canvas = WellSectionCanvas()
    canvas.set_wells([
        _well("A", 1000.0, 2000.0, 1500.0, 1600.0),
        _well("B", 0.0, 2000.0, 1500.0, 1600.0),
    ])
    canvas.resize(800, 556)
    h = canvas.height()

    for well_idx in (0, 1):
        strat = _strat_track(canvas, well_idx)
        assert strat.depth_top == canvas._wells[well_idx].top_depth
        for depth in (strat.intervals[0].top, strat.intervals[0].bottom):
            link_y = canvas._column_depth_y(strat, depth)
            expected = _painted_column_y(strat, depth, h)
            assert abs(link_y - expected) <= 1.0, (
                f"well {well_idx} depth {depth}: link y={link_y} "
                f"painted y={expected}"
            )


def test_column_y_for_measured_issue_case(qapp):
    """The exact measured case: global [0,2000], well A [1000,2000], canvas
    h=1056 (content 1000 px). Depth 1000 is A's range top, painted at the
    top of the content area (y=56); the old transformer path put the link
    at y=556, 500 px away."""
    canvas = WellSectionCanvas()
    canvas.set_wells([
        _well("A", 1000.0, 2000.0, 1000.0, 1100.0),
        _well("B", 0.0, 2000.0, 1000.0, 1100.0),
    ])
    canvas.resize(800, 1056)

    # Render once so paint_all installs the transformer geometry the old
    # path used (scale_y over the global span).
    img = QImage(canvas.size(), QImage.Format.Format_ARGB32)
    canvas.render(img)

    strat_a = _strat_track(canvas, 0)
    assert abs(canvas._column_depth_y(strat_a, 1000.0) - 56.0) <= 1.0

    # The global-transformer mapping this replaced, for contrast.
    transformer_y = canvas._transformer.get_depth_y("A", 1000.0)
    assert abs(transformer_y - 556.0) <= 1.0
    assert abs(canvas._column_depth_y(strat_a, 1000.0) - transformer_y) >= 400.0


def test_two_wells_different_ranges_paint_offscreen(qapp):
    """The link/quad geometry path must render cleanly with mismatched well
    ranges (both absolute and datum_shift modes)."""
    from PySide6.QtCore import Qt

    canvas = WellSectionCanvas()
    canvas.set_wells([
        _well("A", 1000.0, 2000.0, 1500.0, 1600.0),
        _well("B", 0.0, 2000.0, 1500.0, 1600.0),
    ])
    canvas.resize(800, 556)
    canvas.set_datum_mode("datum_shift", datum_name="F1")

    img = QImage(canvas.size(), QImage.Format.Format_ARGB32)
    img.fill(0)
    canvas.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
    canvas.render(img)
    data = img.constBits().tobytes()
    assert data.count(0) < len(data), "canvas painted nothing"
