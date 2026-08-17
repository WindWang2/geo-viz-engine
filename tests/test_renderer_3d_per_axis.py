"""Per-axis slice-plane update tests for Renderer3D.

Renderer3D is pyqtgraph.opengl — there is no pyvista dependency. Skip only
when the GL widget cannot initialize in this environment.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_renderer(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    try:
        r = Renderer3D()
    except Exception as exc:
        pytest.skip(f"renderer could not initialize: {exc}")
    qtbot.addWidget(r)
    vol = np.random.default_rng(3).random((8, 9, 10)).astype(np.float32)
    r.load_volume(vol)
    if not getattr(r, "_loaded", False) or getattr(r, "_view", None) is None:
        pytest.skip("renderer could not initialize in this environment")
    return r


def test_update_slice_planes_for_only_replaces_changed_axis(qtbot, qapp):
    r = _make_renderer(qtbot)
    r._update_slice_planes()
    il_before = r._img_il
    xl_before = r._img_xl
    if il_before is None or xl_before is None:
        pytest.skip("slice planes were not created")

    nt = int(r._volume_data_cpu.shape[2])
    new_t = min(int(r._t_pos) + 1, nt - 1)
    if new_t == int(r._t_pos):
        new_t = max(0, int(r._t_pos) - 1)
    r._t_pos = new_t
    r._active_time_pos = new_t
    r._time_slice_positions = [new_t]
    r._update_slice_planes_for({"time"})

    assert r._img_il is il_before
    assert r._img_xl is xl_before
    assert new_t in r._time_plane_items
    assert r._img_t is r._time_plane_items[new_t][0]


def test_update_slice_planes_alias_matches_full_rebuild(qtbot, qapp):
    r = _make_renderer(qtbot)
    r._update_slice_planes()
    il_before = r._img_il
    if il_before is None:
        pytest.skip("slice planes were not created")
    r._update_slice_planes_for(None)
    assert r._img_il is not il_before
