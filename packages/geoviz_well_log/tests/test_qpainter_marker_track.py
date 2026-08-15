"""Formation-top markers must reach the QPainter (Legacy) backend (WL-14 / #410).

The workbench wraps well data in ``WellLogDataWithMarkers``; the native engine
adapter consumes ``data.markers`` but ``build_qpainter_tracks`` had no marker
consumer, so saved correlation tops silently disappeared on the Legacy backend.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from geoviz_well_log.models import CurveData
from geoviz_well_log.qpainter_builder import build_qpainter_tracks
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.marker_track import MarkerTrack


class _Marker:
    """Duck-typed marker (same shape as workbench FormationTopMarker)."""

    def __init__(self, depth, label, *, use_reference_depth=False, name=None):
        self.depth = None if use_reference_depth else depth
        self.reference_depth = depth if use_reference_depth else None
        self.label = label if name is None else None
        self.name = name


class _WellData:
    """Duck-typed WellLogDataWithMarkers (proxies + markers list)."""

    def __init__(self, markers, **overrides):
        self.well_name = "W1"
        self.top_depth = 0.0
        self.bottom_depth = 1000.0
        self.curves = [
            CurveData(
                name="GR", unit="API",
                depth=[float(d) for d in range(0, 1001, 100)],
                values=[float(v % 100) for v in range(0, 1001, 100)],
                display_range=(0.0, 100.0),
            )
        ]
        self.lithology = []
        self.facies = []
        self.intervals = None
        self.markers = markers
        for k, v in overrides.items():
            setattr(self, k, v)


def test_builder_emits_marker_track_for_markers(qtbot):
    data = _WellData(markers=[_Marker(500.0, "T1"), _Marker(700.5, "T2")])
    tracks = build_qpainter_tracks(data)
    marker_tracks = [t for t in tracks if isinstance(t, MarkerTrack)]
    assert len(marker_tracks) == 1
    assert marker_tracks[0].markers == [(500.0, "T1"), (700.5, "T2")]
    assert marker_tracks[0].width == 0  # no layout contribution


def test_builder_accepts_reference_depth_and_name_attributes(qtbot):
    data = _WellData(markers=[
        _Marker(500.0, None, use_reference_depth=True, name="T-REF"),
    ])
    tracks = build_qpainter_tracks(data)
    marker_tracks = [t for t in tracks if isinstance(t, MarkerTrack)]
    assert len(marker_tracks) == 1
    assert marker_tracks[0].markers == [(500.0, "T-REF")]


def test_builder_skips_invalid_markers_and_empty_lists(qtbot):
    bad = _Marker(500.0, "T1")
    del bad.depth
    del bad.reference_depth
    data = _WellData(markers=[bad, _Marker(float("nan"), "BAD")])
    tracks = build_qpainter_tracks(data)
    marker_tracks = [t for t in tracks if isinstance(t, MarkerTrack)]
    assert len(marker_tracks) == 1
    assert marker_tracks[0].markers == []

    plain = _WellData(markers=[])
    assert not [t for t in build_qpainter_tracks(plain) if isinstance(t, MarkerTrack)]


def test_marker_lines_rendered_offscreen(qtbot):
    """Marker line appears at the correct depth Y when rendered offscreen."""
    data = _WellData(markers=[_Marker(500.0, "T1")])
    canvas = WellLogCanvas()
    canvas.set_tracks(build_qpainter_tracks(data))
    qtbot.addWidget(canvas)
    canvas.resize(400, 600)

    img = QImage(400, 600, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    canvas.paint_all(painter)
    painter.end()

    expected_y = int(500.0 / 1000.0 * 600)  # full-canvas ratio
    marker_color = QColor("#0ea5e9")
    hits = []
    for x in range(0, 400, 2):
        c = img.pixelColor(x, expected_y)
        if (abs(c.red() - marker_color.red()) <= 40
                and abs(c.green() - marker_color.green()) <= 40
                and abs(c.blue() - marker_color.blue()) <= 40):
            hits.append(x)
    assert hits, f"no marker-colored pixel at y={expected_y}"


def test_canvas_without_markers_renders_unchanged(qtbot):
    data = _WellData(markers=[])
    canvas = WellLogCanvas()
    canvas.set_tracks(build_qpainter_tracks(data))
    qtbot.addWidget(canvas)
    canvas.resize(400, 600)
    img = QImage(400, 600, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    canvas.paint_all(painter)
    painter.end()
    assert canvas.total_width > 0
