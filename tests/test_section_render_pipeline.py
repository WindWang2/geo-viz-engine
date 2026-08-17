"""#582 / #583 / #584 regressions: section correlation layer, datum
flattening, duplicate-mnemonic rendering."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from geoviz_well_log.models import (
    CurveData,
    IntervalItem,
    WellIntervals,
    WellLogData,
)


def _well(name: str, formations: list[tuple[str, float]] | None = None) -> WellLogData:
    intervals = None
    if formations is not None:
        intervals = WellIntervals(
            formation=[IntervalItem(top=t, bottom=t + 50.0, name=n) for n, t in formations]
        )
    return WellLogData(
        well_name=name,
        top_depth=1000.0,
        bottom_depth=1100.0,
        curves=[CurveData(name="GR", depth=[1000.0, 1100.0], values=[10.0, 20.0])],
        intervals=intervals,
    )


# --- #582: interval tracks expose a public payload -------------------------


def test_interval_track_classes_expose_public_intervals(qtbot):
    """#582: the section canvas discovers stratigraphy tracks via a public
    ``intervals`` attribute; the private-only ``_intervals`` made its
    horizon-link / facies-fill layer unreachable dead code."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from geoviz_well_log.renderer.interval_track import IntervalTrack
    from geoviz_well_log.renderer.lithology_track import LithologyTrack
    from geoviz_well_log.renderer.systems_tract import SystemsTractTrack

    ivs = [IntervalItem(top=1000.0, bottom=1020.0, name="F1")]
    for cls in (IntervalTrack, SystemsTractTrack, LithologyTrack):
        track = cls(intervals=ivs, label=cls.__name__)
        assert hasattr(track, "intervals"), f"{cls.__name__} must expose intervals"
        assert list(track.intervals) == ivs


def test_section_canvas_finds_stratigraphy_tracks(qtbot):
    """#582: paint_all's discovery must actually select an interval track."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from geoviz_well_log.renderer.interval_track import IntervalTrack
    from geoviz_well_log.section.section_canvas import WellSectionCanvas

    canvas = WellSectionCanvas()
    qtbot.addWidget(canvas)
    w1, w2 = _well("W1", [("F1", 1010.0)]), _well("W2", [("F1", 1030.0)])
    canvas.set_wells([w1, w2])

    ivs = [IntervalItem(top=1010.0, bottom=1030.0, name="F1")]
    track = IntervalTrack(intervals=ivs, label="Strat")
    canvas._well_tracks[0] = [track]
    canvas._well_tracks[1] = [IntervalTrack(intervals=list(ivs), label="Strat")]

    # Offscreen paint must not raise and must leave visible pixels for the
    # correlation background layer.
    from PySide6.QtGui import QImage, QPainter

    canvas.resize(600, 400)
    img = QImage(canvas.size(), QImage.Format.Format_ARGB32)
    img.fill(0)
    canvas.render(img)
    data = img.constBits().tobytes()
    assert data.count(0) < len(data), "canvas painted nothing"


# --- #583: datum flattening from real payloads -----------------------------


def test_datum_depths_keyed_by_well_and_datum_name(qtbot):
    """#583: datum_depths must be {well_id: top of the SELECTED formation}."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from geoviz_well_log.section.section_canvas import WellSectionCanvas

    canvas = WellSectionCanvas()
    qtbot.addWidget(canvas)
    w1 = _well("W1", [("F1", 1010.0), ("F2", 1050.0)])
    w2 = _well("W2", [("F1", 1030.0)])  # W2 lacks F2
    canvas.set_wells([w1, w2])

    assert canvas.available_datums() == ["F1", "F2"]

    canvas.set_datum_mode("datum_shift", datum_name="F1")
    assert canvas._transformer.datum_depths == {"W1": 1010.0, "W2": 1030.0}

    canvas.set_datum_mode("datum_shift", datum_name="F2")
    # W2 missing F2 → absent → absolute fallback, never a wrong flatten.
    assert canvas._transformer.datum_depths == {"W1": 1050.0}


def test_datum_shift_moves_well_depths_relative(qtbot):
    """#583 end-to-end: the transformer must actually flatten wells onto
    the datum line when the datum exists in both."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from geoviz_well_log.section.section_canvas import WellSectionCanvas

    canvas = WellSectionCanvas()
    qtbot.addWidget(canvas)
    canvas.set_wells([_well("W1", [("F", 1010.0)]), _well("W2", [("F", 1040.0)])])
    canvas.set_datum_mode("datum_shift", datum_name="F")

    t = canvas._transformer
    y_w1 = t.get_depth_y("W1", 1010.0)
    y_w2 = t.get_depth_y("W2", 1040.0)
    # Both wells' datum horizons sit ON the datum line, despite different
    # absolute depths (old behaviour: identical y to absolute mode).
    assert y_w1 == pytest.approx(t.y_datum)
    assert y_w2 == pytest.approx(t.y_datum)


def test_wells_without_formation_payload_keep_absolute(qtbot):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from geoviz_well_log.section.section_canvas import WellSectionCanvas

    canvas = WellSectionCanvas()
    qtbot.addWidget(canvas)
    canvas.set_wells([_well("W1"), _well("W2")])  # no intervals payload

    canvas.set_datum_mode("datum_shift", datum_name="F")
    assert canvas._transformer.datum_depths == {}
    assert canvas.available_datums() == []
    # Absolute fallback mapping stays valid.
    y = canvas._transformer.get_depth_y("W1", 1000.0)
    assert y == pytest.approx(canvas._transformer.header_height)


# --- #584: duplicate mnemonics survive parse + render ----------------------


def test_las_parser_disambiguates_duplicate_mnemonics():
    """#584: two GR columns must both survive parsing with visible names."""
    from geoviz_well_log.las_parser import parse_las_text

    las = """~VERSION INFORMATION
VERS. 2.0
WRAP. NO
~WELL INFORMATION
STRT.M 1000.0
STOP.M 1002.0
STEP.M 1.0
NULL. -999.25
WELL. DUP
~CURVE INFORMATION
DEPT.M
GR.GAPI
GR.GAPI
~ASCII
1000 10 30
1001 20 40
1002 30 50
"""
    result = parse_las_text(las)
    assert set(result.curves) == {"GR", "GR_2"}, result.curves
    assert result.curves["GR"].tolist() == [10.0, 20.0, 30.0]
    assert result.curves["GR_2"].tolist() == [30.0, 40.0, 50.0]
    assert result.units["GR_2"] == "GAPI"


def test_qpainter_builder_renders_all_duplicate_curves(qtbot):
    """#584: build_qpainter_tracks must draw every duplicate column —
    grouped AND ungrouped — never silently drop the earlier run."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from geoviz_well_log.qpainter_builder import build_qpainter_tracks

    data = WellLogData(
        well_name="DUP",
        top_depth=1000.0,
        bottom_depth=1100.0,
        curves=[
            CurveData(name="GR", depth=[1000.0, 1100.0], values=[10.0, 20.0]),
            CurveData(name="GR", depth=[1000.0, 1100.0], values=[80.0, 90.0]),
            CurveData(name="RT", depth=[1000.0, 1100.0], values=[1.0, 2.0]),
        ],
    )
    merge_groups = [(("GR",), "GR")]
    tracks = build_qpainter_tracks(data, merge_groups=merge_groups)

    curve_tracks = [t for t in tracks if type(t).__name__ == "CurveTrack"]
    # Grouped GR track carries BOTH GR columns...
    gr_tracks = [t for t in curve_tracks if t._label == "GR"]
    assert len(gr_tracks) == 1
    assert len(gr_tracks[0]._curves) == 2, "both duplicate GR columns must render"

    # ...and no other track silently swallows or duplicates RT.
    rt_tracks = [t for t in curve_tracks if t._label == "RT"]
    assert len(rt_tracks) == 1
    total_curve_refs = sum(len(t._curves) for t in curve_tracks)
    assert total_curve_refs == 3, "exactly the three input columns"


def test_qpainter_builder_ungrouped_duplicates_each_get_a_track(qtbot):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from geoviz_well_log.qpainter_builder import build_qpainter_tracks

    data = WellLogData(
        well_name="DUP2",
        top_depth=1000.0,
        bottom_depth=1100.0,
        curves=[
            CurveData(name="AC", depth=[1000.0, 1100.0], values=[1.0, 2.0]),
            CurveData(name="AC", depth=[1000.0, 1100.0], values=[8.0, 9.0]),
        ],
    )
    tracks = build_qpainter_tracks(data, merge_groups=[])
    curve_tracks = [t for t in tracks if type(t).__name__ == "CurveTrack"]
    assert len(curve_tracks) == 2, "each ungrouped duplicate gets its own track"
