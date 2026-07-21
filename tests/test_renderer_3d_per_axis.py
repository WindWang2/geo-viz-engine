"""Per-axis slice-plane update tests for Renderer3D."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

pyvista = pytest.importorskip("pyvista")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_renderer(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    r = Renderer3D()
    qtbot.addWidget(r)
    vol = np.random.default_rng(3).random((8, 9, 10)).astype(np.float32)
    r.load_volume(vol) if hasattr(r, "load_volume") else None
    if not getattr(r, "_loaded", False):
        # Fall back: set minimal state for plane creation
        r._volume_data_cpu = vol
        r._loaded = True
    return r


def test_update_slice_planes_for_only_replaces_changed_axis(qtbot, qapp):
    r = _make_renderer(qtbot)
    if not getattr(r, "_loaded", False):
        pytest.skip("renderer could not initialize in this environment")
    r._update_slice_planes()
    il_before = r._img_il
    xl_before = r._img_xl
    t_before = r._img_t

    r._t_pos = min(getattr(r, "_t_pos", 0) + 1, 9)
    r._update_slice_planes_for({"time"})

    assert r._img_il is il_before
    assert r._img_xl is xl_before
    assert r._img_t is not t_before


def test_update_slice_planes_alias_matches_full_rebuild(qtbot, qapp):
    r = _make_renderer(qtbot)
    if not getattr(r, "_loaded", False):
        pytest.skip("renderer could not initialize in this environment")
    r._update_slice_planes()
    il_before = r._img_il
    r._update_slice_planes_for(None)
    assert r._img_il is not il_before
