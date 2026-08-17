"""#541: FenceProfile2D click mapping must account for a centered pixmap."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPixmap

from geoviz_well_seismic_3d.profile_2d import FenceProfile2D


class _Click:
    def __init__(self, x: float, y: float) -> None:
        self._pos = QPointF(x, y)

    def position(self):
        return self._pos


def _mounted_profile(qtbot, label_w=1000, label_h=400, pix_w=756, pix_h=300):
    profile = FenceProfile2D()
    qtbot.addWidget(profile)
    profile.show()
    profile._label.setFixedSize(label_w, label_h)
    pix = QPixmap(pix_w, pix_h)
    pix.fill(Qt.GlobalColor.black)
    profile._pix = pix
    profile._plot_width = 640
    profile._smax = 100.0
    profile._z0 = 0.0
    profile._z1 = 1000.0
    profile._label.setPixmap(pix)
    profile._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return profile


def test_click_in_left_margin_is_not_mapped_as_interior(qtbot):
    profile = _mounted_profile(qtbot)
    emitted = []
    profile.probe_changed.connect(lambda s, z: emitted.append((s, z)))

    # Label 1000 wide, pixmap 756 centered → left margin starts at 122 px.
    # Old code mapped x=100 as px = 100/1000*(756-1) ≈ 75.5 (interior).
    profile._on_click(_Click(100.0, 200.0))
    assert emitted == []


def test_click_at_pixmap_left_edge_maps_to_s_zero(qtbot):
    profile = _mounted_profile(qtbot)
    emitted = []
    profile.probe_changed.connect(lambda s, z: emitted.append((s, z)))

    offset_x = (1000 - 756) / 2.0
    profile._on_click(_Click(offset_x, 200.0))
    assert emitted
    assert emitted[0][0] == pytest.approx(0.0, abs=0.2)


def test_click_at_plot_midpoint_maps_to_half_s(qtbot):
    profile = _mounted_profile(qtbot)
    emitted = []
    profile.probe_changed.connect(lambda s, z: emitted.append((s, z)))

    offset_x = (1000 - 756) / 2.0
    offset_y = (400 - 300) / 2.0
    profile._on_click(_Click(offset_x + 320.0, offset_y + 150.0))
    assert emitted
    assert emitted[0][0] == pytest.approx(320.0 / 639.0 * 100.0, abs=0.3)
    assert emitted[0][1] == pytest.approx(150.0 / 299.0 * 1000.0, abs=2.0)
