"""Composite export geometry: link polygons must match screen rendering
(WL-10 / #407) and tops/picks must be exported.

The export previously drew canvases at translate(x_off, 0) (no well-name
label) but computed link Y through ConnectionOverlay.depth_to_y, which maps
through the canvas position inside the widget and therefore includes the
28 px name label — every exported link band was shifted down by exactly
28 px. Tops/picks were painted only by PickingOverlay on screen and never
reached the export.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter, QPolygonF
from PySide6.QtWidgets import QApplication

from geoviz_well_log.cross_well_widget import CrossWellWidget
from geoviz_well_log.models import CorrelationLink, CurveData
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.curve_track import CurveTrack


class RecordingPainter(QPainter):
    """Records vector primitives in composite (post-transform) coordinates."""

    def __init__(self, device):
        super().__init__(device)
        self.polygons: list[list[QPointF]] = []
        self.lines: list[tuple[QPointF, QPointF]] = []
        self.ellipses: list[QPointF] = []

    def drawPolygon(self, *args):
        if len(args) == 1 and isinstance(args[0], QPolygonF):
            self.polygons.append([self.worldTransform().map(p) for p in args[0]])
        return super().drawPolygon(*args)

    def drawLine(self, *args):
        if (len(args) == 2 and isinstance(args[0], QPointF)
                and isinstance(args[1], QPointF)):
            self.lines.append((self.worldTransform().map(args[0]),
                               self.worldTransform().map(args[1])))
        return super().drawLine(*args)

    def drawEllipse(self, *args):
        if len(args) == 3 and isinstance(args[0], QPointF):
            self.ellipses.append(self.worldTransform().map(args[0]))
        return super().drawEllipse(*args)


def _curve_track():
    curve = CurveData(
        name="GR", unit="API",
        depth=[float(d) for d in range(10)],
        values=[float(v) for v in range(10)],
        display_range=(0.0, 10.0),
    )
    return CurveTrack([curve], label="GR")


def _local_y(canvas, depth: float) -> float:
    """Composite-space Y for a depth on a canvas (label offset excluded)."""
    header_h = max((t.header_height for t in canvas.tracks), default=56)
    content_h = canvas.height() - header_h
    track = canvas.tracks[0]
    ratio = (depth - track.depth_top) / track.depth_span
    return header_h + ratio * content_h


def test_link_polygon_aligns_with_canvas_content(qtbot):
    """Exported link band endpoints sit at the canvas-local Y of their depths
    (0 px label offset, tolerance 1 px)."""
    widget = CrossWellWidget()
    qtbot.addWidget(widget)
    canvases = []
    for name in ("W1", "W2"):
        canvas = WellLogCanvas()
        canvas.add_track(_curve_track())
        canvas.set_depth_range(0.0, 100.0)
        widget.add_canvas(canvas, name)
        canvases.append(canvas)
    widget._overlay.set_links([
        CorrelationLink(
            source_well="W1", target_well="W2",
            source_interval_id="20_30_F1", target_interval_id="25_35_F1",
            color="#f59e0b",
        ),
    ])
    widget.resize(1000, 600)
    widget.show()
    QApplication.processEvents()

    img = QImage(1000, 600, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    rec = RecordingPainter(img)
    widget._paint_composite(rec, 1000, 600)
    rec.end()

    assert len(rec.polygons) == 1
    poly = rec.polygons[0]
    w1, w2 = canvases
    spacing = widget._well_spacing
    # Composite X: W1 right edge = w1.width(); W2 left edge = w1.width()+spacing.
    assert abs(poly[0].x() - w1.width()) <= 1.0
    assert abs(poly[1].x() - (w1.width() + spacing)) <= 1.0
    # Composite Y equals the canvas-local Y of each depth (no 28 px label shift).
    assert abs(poly[0].y() - _local_y(w1, 20.0)) <= 1.0
    assert abs(poly[2].y() - _local_y(w2, 35.0)) <= 1.0


def test_export_includes_tops_and_picks(qtbot):
    """Tops (dashed lines) and picks (dots) visible on screen reach the export."""
    from geoviz_cross_well.canvas import CrossWellCanvas
    from geoviz_cross_well.tops_model import FormationTop

    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    canvases = {}
    for name in ("W1", "W2"):
        sub = WellLogCanvas()
        sub.add_track(_curve_track())
        sub.set_depth_range(0.0, 100.0)
        canvas._widget.add_canvas(sub, name)
        canvases[name] = sub

    canvas._tops_model.add_top(FormationTop("W1", "T1", 20.0))
    pick_id = canvas._picks_model.add_pick("H1", "W1", 30.0)
    canvas._picks_model.connect_picks(pick_id, "W2", 32.0)

    canvas.resize(1200, 600)
    canvas.show()
    QApplication.processEvents()

    widget = canvas._widget
    img = QImage(1200, 600, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    rec = RecordingPainter(img)
    widget._paint_composite(rec, 1200, 600)
    rec.end()

    # Top "T1" at 20 m on W1: dashed line spanning the full canvas width at
    # local Y 20 (grid lines only span individual tracks, so restrict the
    # match to lines spanning the whole W1 canvas).
    expected_top_y = _local_y(canvases["W1"], 20.0)
    w1 = canvases["W1"]
    span_lines = [
        (a, b) for a, b in rec.lines
        if abs(a.x() - 0.0) <= 1.0 and abs(b.x() - w1.width()) <= 1.0
    ]
    assert any(
        abs(a.y() - expected_top_y) <= 1.0 and abs(b.y() - expected_top_y) <= 1.0
        for a, b in span_lines
    ), "formation top line missing from export"

    # Pick dots on both wells.
    expected_y_w1 = _local_y(canvases["W1"], 30.0)
    expected_y_w2 = _local_y(canvases["W2"], 32.0)
    dot_ys = [p.y() for p in rec.ellipses]
    assert any(abs(y - expected_y_w1) <= 1.0 for y in dot_ys), "W1 pick dot missing"
    assert any(abs(y - expected_y_w2) <= 1.0 for y in dot_ys), "W2 pick dot missing"


def test_export_without_interpretation_still_works(qtbot):
    """No tops/picks and no links: plain curve section exports normally."""
    from geoviz_cross_well.canvas import CrossWellCanvas

    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    for name in ("W1", "W2"):
        sub = WellLogCanvas()
        sub.add_track(_curve_track())
        canvas._widget.add_canvas(sub, name)
    canvas.resize(1000, 600)
    canvas.show()
    QApplication.processEvents()

    img = QImage(1000, 600, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    rec = RecordingPainter(img)
    canvas._widget._paint_composite(rec, 1000, 600)
    rec.end()
    # No interpretation graphics (no links, no tops/picks). Plain canvas
    # grid lines may still be recorded as drawLine calls.
    assert rec.polygons == []
    assert rec.ellipses == []
