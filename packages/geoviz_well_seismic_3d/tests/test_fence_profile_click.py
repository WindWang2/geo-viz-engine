"""FenceProfile2D click mapping uses the painted plot rectangle."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QColor

from geoviz_well_seismic_3d.profile_2d import FenceProfile2D


class _Click:
    def __init__(self, x: float, y: float) -> None:
        self._pos = QPointF(x, y)

    def position(self):
        return self._pos


def _mounted_profile(qtbot, width=1000, height=400):
    profile = FenceProfile2D()
    qtbot.addWidget(profile)
    profile.resize(width, height)
    profile.show()
    profile._ext = object()
    profile._image = QImage(16, 16, QImage.Format.Format_RGBA8888)
    profile._image.fill(QColor(0, 0, 0))
    profile._smax = 100.0
    profile._z0 = 0.0
    profile._z1 = 1000.0
    return profile


def test_click_in_left_margin_is_not_mapped_as_interior(qtbot):
    profile = _mounted_profile(qtbot)
    emitted = []
    profile.probe_changed.connect(lambda s, z: emitted.append((s, z)))
    plot = profile._plot_rect()
    profile._on_click(_Click(float(plot.left() - 4), float(plot.center().y())))
    assert emitted == []


def test_click_at_pixmap_left_edge_maps_to_s_zero(qtbot):
    profile = _mounted_profile(qtbot)
    emitted = []
    profile.probe_changed.connect(lambda s, z: emitted.append((s, z)))
    plot = profile._plot_rect()
    profile._on_click(_Click(float(plot.left()), float(plot.center().y())))
    assert emitted
    assert emitted[0][0] == pytest.approx(0.0, abs=0.2)


def test_click_at_plot_midpoint_maps_to_half_s(qtbot):
    profile = _mounted_profile(qtbot)
    emitted = []
    profile.probe_changed.connect(lambda s, z: emitted.append((s, z)))
    plot = profile._plot_rect()
    mid_x = plot.left() + plot.width() / 2.0
    mid_y = plot.top() + plot.height() / 2.0
    profile._on_click(_Click(mid_x, mid_y))
    assert emitted
    assert emitted[0][0] == pytest.approx(50.0, abs=1.5)
    assert emitted[0][1] == pytest.approx(500.0, abs=15.0)
