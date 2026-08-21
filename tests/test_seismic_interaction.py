"""Tests for seismic display interaction: zoom/pan, slice browsing, cursor linkage."""

import numpy as np
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QVector3D

from geoviz_seismic.profile_vd import ProfileVD
from geoviz_seismic.models import SliceInfo


def _make_vd_with_data(qtbot) -> ProfileVD:
    widget = ProfileVD()
    qtbot.addWidget(widget)
    widget.resize(400, 300)

    data = np.random.randn(50, 80).astype(np.float32)
    info = SliceInfo(
        slice_type="inline",
        position=10,
        axis_h_label="XL",
        axis_v_label="T",
        axis_h_values=list(np.arange(80) * 25.0),
        axis_v_values=list(np.arange(50) * 4.0),
    )
    widget.render(data, slice_info=info)
    return widget


# --- Step 1: Zoom and Pan ---

def test_profile_vd_wheel_zoom(qtbot):
    widget = _make_vd_with_data(qtbot)
    assert widget._zoom_scale == pytest.approx(1.0, abs=0.01)

    # Simulate wheel zoom in
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtCore import QPointF
    img_rect = widget._image_rect()
    pos = QPointF(img_rect.center().x(), img_rect.center().y())
    event = QWheelEvent(
        pos, pos, QPoint(0, 120), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate, False,
    )
    widget.wheelEvent(event)
    assert widget._zoom_scale > 1.0
    assert widget._view_h != (0.0, 1.0) or widget._view_v != (0.0, 1.0)


def test_profile_vd_double_click_reset(qtbot):
    widget = _make_vd_with_data(qtbot)
    # Zoom in first
    widget._view_h = (0.2, 0.5)
    widget._view_v = (0.3, 0.6)
    widget._zoom_scale = 4.0
    widget._build_image_from_normalized()

    # Double-click to reset
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF
    pos = QPointF(100, 100)
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonDblClick, pos, pos,
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseDoubleClickEvent(event)

    assert widget._zoom_scale == pytest.approx(1.0, abs=0.01)
    assert widget._view_h == (0.0, 1.0)
    assert widget._view_v == (0.0, 1.0)


def test_pixel_to_seismic_zoomed(qtbot):
    widget = _make_vd_with_data(qtbot)

    # Zoom to right half of data
    widget._view_h = (0.5, 1.0)
    widget._view_v = (0.0, 1.0)
    widget._zoom_scale = 2.0
    widget._build_image_from_normalized()

    # Click at left edge of viewport should map to ~50% of full data
    img_rect = widget._image_rect()
    from PySide6.QtCore import QPointF
    pos = QPointF(img_rect.left() + 1, img_rect.top() + img_rect.height() / 2)
    result = widget._pixel_to_seismic(pos)
    assert result is not None
    h_val, v_val, col_idx, row_idx = result
    # col_idx should be around 40 (50% of 80 columns)
    assert 35 <= col_idx <= 45


def test_seismic_to_pixel_zoomed(qtbot):
    widget = _make_vd_with_data(qtbot)

    # Zoom to right half
    widget._view_h = (0.5, 1.0)
    widget._view_v = (0.0, 1.0)
    widget._zoom_scale = 2.0
    widget._build_image_from_normalized()

    # A point in the left half (col_idx=10) should map outside viewport
    info = widget.slice_info()
    pt_left = widget._seismic_to_pixel(info.axis_h_values[10], info.axis_v_values[25])
    assert pt_left is not None
    px, py = pt_left
    img_rect = widget._image_rect()
    assert px < img_rect.left()  # outside visible area

    # A point in the right half (col_idx=60) should be inside viewport
    pt_right = widget._seismic_to_pixel(info.axis_h_values[60], info.axis_v_values[25])
    assert pt_right is not None
    px, py = pt_right
    assert img_rect.left() <= px <= img_rect.right()


def test_profile_vd_middle_pan(qtbot):
    widget = _make_vd_with_data(qtbot)
    assert not widget._panning

    # Simulate middle-button press
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF
    pos = QPointF(200, 150)
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress, pos, pos,
        Qt.MouseButton.MiddleButton, Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(event)
    assert widget._panning
    assert widget._pan_last is not None

    # Release
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease, pos, pos,
        Qt.MouseButton.MiddleButton, Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseReleaseEvent(event)
    assert not widget._panning


# --- Step 2: Slice Browsing ---

def test_slice_step_signal(qtbot):
    widget = _make_vd_with_data(qtbot)

    received = []
    widget.slice_step_requested.connect(lambda d: received.append(d))

    # Simulate Shift+wheel
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtCore import QPointF
    pos = QPointF(200, 150)
    event = QWheelEvent(
        pos, pos, QPoint(0, 120), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.ShiftModifier,
        Qt.ScrollPhase.ScrollUpdate, False,
    )
    widget.wheelEvent(event)

    assert len(received) == 1
    assert received[0] == 1


def test_renderer_3d_set_position_external(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D
    widget = Renderer3D()
    qtbot.addWidget(widget)

    data = np.random.randn(20, 20, 20).astype(np.float32)
    widget.load_volume(data)

    received = []
    widget.slice_changed.connect(lambda st, pos: received.append((st, pos)))

    widget.set_position_external("inline", 5)
    assert widget._il_pos == 5
    assert any(st == "inline" and pos == 5 for st, pos in received)


def test_set_position_external_time_defers_plane_rebuild(qtbot):
    """Time slider must not GL-rebuild on every mouse-move (IL/XL already debounce)."""
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.random.randn(8, 9, 12).astype(np.float32)
    widget.load_volume(data, spacing=(1.0, 1.0, 2.0))

    old_t = int(widget._t_pos)
    old_z = widget._img_t.transform().map(QVector3D(0, 0, 0)).z()
    new_t = 0 if old_t != 0 else 3
    widget.set_position_external("time", new_t)
    assert widget._t_pos == new_t
    assert widget._active_time_pos == new_t
    # Geometry stays put until the host debounce calls _update_slice_planes_for.
    still_z = widget._img_t.transform().map(QVector3D(0, 0, 0)).z()
    assert still_z == pytest.approx(old_z)
    widget._update_slice_planes_for({"time"})
    moved_z = widget._img_t.transform().map(QVector3D(0, 0, 0)).z()
    assert moved_z != pytest.approx(old_z)


def test_renderer_3d_cursor_sphere(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D
    widget = Renderer3D()
    qtbot.addWidget(widget)

    data = np.random.randn(10, 10, 10).astype(np.float32)
    widget.load_volume(data)

    assert widget._cursor_sphere is None
    widget.set_cursor_position(5.0, 3.0, 100.0)
    assert widget._cursor_sphere is not None

    # Update position
    widget.set_cursor_position(7.0, 4.0, 200.0)
    assert widget._cursor_sphere is not None


# --- Step 3: Cursor Linkage ---

def test_cursor_moved_3d_signal(qtbot):
    widget = _make_vd_with_data(qtbot)

    received = []
    widget.cursor_moved_3d.connect(lambda h, v, st: received.append((h, v, st)))

    # Simulate mouse move to trigger cursor signal
    img_rect = widget._image_rect()
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF
    pos = QPointF(img_rect.center().x(), img_rect.center().y())
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove, pos, pos,
        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseMoveEvent(event)
    # Wait for throttle timer
    qtbot.wait(20)

    assert len(received) >= 1
    h, v, st = received[0]
    assert st == "inline"


def test_profile_vd_reset_on_render(qtbot):
    widget = _make_vd_with_data(qtbot)

    # Zoom in
    widget._view_h = (0.3, 0.7)
    widget._view_v = (0.2, 0.8)
    widget._zoom_scale = 3.0

    # Render new data — should reset viewport
    new_data = np.random.randn(30, 60).astype(np.float32)
    info = SliceInfo(
        slice_type="crossline", position=5,
        axis_h_label="IL", axis_v_label="T",
        axis_h_values=list(np.arange(60) * 10.0),
        axis_v_values=list(np.arange(30) * 4.0),
    )
    widget.render(new_data, slice_info=info)

    assert widget._zoom_scale == pytest.approx(1.0, abs=0.01)
    assert widget._view_h == (0.0, 1.0)
    assert widget._view_v == (0.0, 1.0)


def test_zoom_clamp_limits(qtbot):
    widget = _make_vd_with_data(qtbot)

    # Try extreme zoom in
    widget._view_h = (0.499, 0.501)
    widget._view_v = (0.499, 0.501)
    widget._zoom_scale = 500.0

    from PySide6.QtGui import QWheelEvent
    from PySide6.QtCore import QPointF
    pos = QPointF(widget._image_rect().center().x(), widget._image_rect().center().y())

    # Zoom in more — should clamp
    event = QWheelEvent(
        pos, pos, QPoint(0, 120), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate, False,
    )
    widget.wheelEvent(event)

    # Span should not be smaller than 1/32
    h_span = widget._view_h[1] - widget._view_h[0]
    v_span = widget._view_v[1] - widget._view_v[0]
    assert h_span >= 1.0 / 32.0 - 0.01
    assert v_span >= 1.0 / 32.0 - 0.01
