"""Pick hit-testing tolerance is in screen pixels, converted via the current
depth scale, and the nearest pick wins (WL-11 / #408).

A fixed ±5.0 depth-unit tolerance made every click on the canvas hit a pick
when zoomed into a <10 m span, and made picks effectively un-clickable when
zoomed out to ~2 km (5 m ≈ 2 px). The tolerance must stay constant in pixels.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QPoint

from geoviz_cross_well.canvas import CrossWellCanvas
from geoviz_well_log.models import CurveData
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.curve_track import CurveTrack


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _build(span_top: float, span_bottom: float, qtbot):
    """CrossWellCanvas with one well; viewport zoomed to [span_top, span_bottom]."""
    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(900, 700)
    canvas.show()

    sub = WellLogCanvas()
    n = 50
    depths = np.linspace(span_top, span_bottom, n)
    values = np.linspace(0.0, 100.0, n)
    sub.set_tracks([
        CurveTrack(
            curves=[CurveData(name="GR", depth=depths.tolist(), values=values.tolist(),
                              display_range=(0.0, 200.0))],
            label="GR",
            width=150,
        ),
    ])
    canvas._widget.add_canvas(sub, "W1")
    sub.set_depth_range(span_top, span_bottom)
    assert sub.height() > 100, "offscreen layout must size the well canvas"
    return canvas, sub


def _widget_y_for_depth(canvas, sub, depth: float) -> float:
    """Y of ``depth`` in CrossWellWidget coordinates (label offset included)."""
    return canvas._widget._overlay.depth_to_y(sub, depth)


def _click_pos(canvas, sub, y_offset_px: float) -> QPoint:
    """A widget-space click point inside the canvas at pick_y + y_offset_px."""
    canvas_rect = sub.rect().translated(sub.mapTo(canvas._widget, sub.rect().topLeft()))
    pick_y = _widget_y_for_depth(canvas, sub, 1000.0)
    x = canvas_rect.left() + canvas_rect.width() / 2
    return QPoint(int(x), int(pick_y + y_offset_px))


def _zoom_and_pick(canvas, sub, span_top, span_bottom, pick_depth=1000.0):
    sub.set_depth_range(span_top, span_bottom)
    return canvas._picks_model.add_pick("H1", "W1", pick_depth)


def test_zoomed_in_far_click_does_not_hit(qtbot, qapp):
    """4 m span: a click >12 px away must NOT hit (old code hit the whole canvas)."""
    canvas, sub = _build(998.0, 1002.0, qtbot)
    pick_id = _zoom_and_pick(canvas, sub, 998.0, 1002.0)

    qapp.processEvents()
    assert _pick_at(canvas, _click_pos(canvas, sub, 20.0)) is None, \
        "click 20 px below the pick must miss even though depth delta < 5 m"
    assert _pick_at(canvas, _click_pos(canvas, sub, -20.0)) is None

    hit = _pick_at(canvas, _click_pos(canvas, sub, 6.0))
    assert hit is not None and hit.pick_id == pick_id
    hit = _pick_at(canvas, _click_pos(canvas, sub, -6.0))
    assert hit is not None and hit.pick_id == pick_id


def test_zoomed_out_click_within_10px_hits(qtbot, qapp):
    """2 km span: clicks within ±10 px reliably hit (old 5 m ≈ 2 px missed)."""
    canvas, sub = _build(0.0, 2000.0, qtbot)
    pick_id = _zoom_and_pick(canvas, sub, 0.0, 2000.0)

    qapp.processEvents()
    hit = _pick_at(canvas, _click_pos(canvas, sub, 8.0))
    assert hit is not None and hit.pick_id == pick_id
    hit = _pick_at(canvas, _click_pos(canvas, sub, -9.0))
    assert hit is not None and hit.pick_id == pick_id

    assert _pick_at(canvas, _click_pos(canvas, sub, 40.0)) is None


def test_nearest_pick_wins(qtbot, qapp):
    """Two picks within tolerance: the screen-nearest one wins (not model order)."""
    canvas, sub = _build(998.0, 1002.0, qtbot)
    qapp.processEvents()
    # 0.1 m apart ≈ 15 px at a 4 m span — a click at the midpoint is within a
    # 10 px tolerance of both picks.
    far_id = canvas._picks_model.add_pick("H1", "W1", 999.95)
    near_id = canvas._picks_model.add_pick("H1", "W1", 1000.05)
    far_y = _widget_y_for_depth(canvas, sub, 999.95)
    near_y = _widget_y_for_depth(canvas, sub, 1000.05)
    mid_y = (near_y + far_y) / 2.0
    canvas_rect = sub.rect().translated(sub.mapTo(canvas._widget, sub.rect().topLeft()))
    cx = canvas_rect.left() + canvas_rect.width() / 2

    # 1 px toward the lower (near) pick: nearest = near_id, even though far_id
    # was inserted first (the old code returned the first model-order hit).
    hit = _pick_at(canvas, QPoint(int(cx), int(mid_y + 1)))
    assert hit is not None and hit.pick_id == near_id

    # 1 px toward the upper (far) pick: nearest = far_id.
    hit = _pick_at(canvas, QPoint(int(cx), int(mid_y - 1)))
    assert hit is not None and hit.pick_id == far_id


def test_click_outside_canvas_never_hits(qtbot, qapp):
    canvas, sub = _build(998.0, 1002.0, qtbot)
    canvas._picks_model.add_pick("H1", "W1", 1000.0)
    qapp.processEvents()
    assert _pick_at(canvas, QPoint(-50, -50)) is None


def _pick_at(canvas, pos):
    return canvas._pick_at(pos)
