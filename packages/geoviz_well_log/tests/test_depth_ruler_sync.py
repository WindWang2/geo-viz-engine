"""Shared depth ruler must track the synchronized viewport and align with the
canvas content (WL-12 / #409).

The ruler previously got its range only at add_canvas time (any zoom/pan left
it stale, since canvas_depth_changed had zero consumers) and mapped depth over
the full widget height, ignoring the 56 px track header + 28 px well-name
label that every other Y transform subtracts.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from geoviz_well_log.cross_well_widget import CrossWellWidget
from geoviz_well_log.models import CurveData
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.curve_track import CurveTrack


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_widget():
    widget = CrossWellWidget()
    curve = CurveData(
        name="GR", unit="API",
        depth=[float(d) for d in range(10)],
        values=[float(v) for v in range(10)],
        display_range=(0.0, 10.0),
    )
    canvas = WellLogCanvas()
    canvas.add_track(CurveTrack([curve], label="GR"))
    widget.add_canvas(canvas, "W1")
    return widget, canvas


def _header_h(canvas) -> int:
    return max((t.header_height for t in canvas.tracks), default=56)


def test_ruler_initialized_from_canvas(qapp):
    widget, canvas = _make_widget()
    ruler = widget._depth_ruler
    assert ruler._depth_top == canvas.tracks[0].depth_top
    assert ruler._depth_bottom == canvas.tracks[0].depth_bottom
    assert ruler._label_inset == CrossWellWidget.NAME_LABEL_HEIGHT
    assert ruler._header_inset == _header_h(canvas)


def test_ruler_updates_after_zoom_pan(qapp):
    widget, canvas = _make_widget()
    ruler = widget._depth_ruler

    # Zoom/pan goes through the coalesced path: depth_range_changed ->
    # _schedule_depth_changed -> _on_coalesced_depth_changed.
    canvas.set_depth_range(1200.0, 1800.0)
    widget._on_coalesced_depth_changed()

    assert ruler._depth_top == 1200.0
    assert ruler._depth_bottom == 1800.0

    # And the real timer path fires the same handler.
    canvas.set_depth_range(0.0, 2000.0)
    widget._coalesce_timer.timeout.emit()
    assert ruler._depth_top == 0.0
    assert ruler._depth_bottom == 2000.0


def test_ruler_aligns_with_canvas_content(qapp):
    """Same depth has the same widget Y on ruler and canvas content (<=1 px)."""
    widget, canvas = _make_widget()
    widget.resize(900, 600)
    widget.show()
    qapp.processEvents()

    ruler = widget._depth_ruler
    assert ruler.height() == widget.height()

    for depth in (500.0, 800.0, 250.0, 123.456):
        header_h = _header_h(canvas)
        content_h = canvas.height() - header_h
        track = canvas.tracks[0]
        ratio = (depth - track.depth_top) / track.depth_span
        local_y = header_h + ratio * content_h
        canvas_widget_y = canvas.mapTo(widget, QPointF(0, local_y)).y()
        assert abs(ruler._depth_to_y(depth) - canvas_widget_y) <= 1.0, (
            f"depth {depth}: ruler y={ruler._depth_to_y(depth)} "
            f"canvas y={canvas_widget_y}"
        )


def test_single_well_view_ruler_keeps_content_alignment(qapp):
    """WellLogView ruler excludes only the header (canvas sits at y=0)."""
    from geoviz_well_log.well_log_view import WellLogView

    view = WellLogView()
    curve = CurveData(
        name="GR", unit="API",
        depth=[float(d) for d in range(10)],
        values=[float(v) for v in range(10)],
        display_range=(0.0, 10.0),
    )
    view.set_tracks([CurveTrack([curve], label="GR")])
    view.resize(600, 500)
    view.show()
    qapp.processEvents()

    ruler = view._depth_ruler
    assert ruler._label_inset == 0.0
    assert ruler._header_inset == _header_h(view._canvas)

    depth = 700.0
    header_h = _header_h(view._canvas)
    content_h = view._canvas.height() - header_h
    ratio = (depth - view._canvas.tracks[0].depth_top) / view._canvas.tracks[0].depth_span
    local_y = header_h + ratio * content_h
    canvas_y = view._canvas.mapTo(view.viewport(), QPointF(0, local_y)).y()
    assert abs(ruler._depth_to_y(depth) - canvas_y) <= 1.0
