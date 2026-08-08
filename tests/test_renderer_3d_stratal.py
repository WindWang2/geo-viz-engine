"""Renderer3D stratal / proportional slice integration tests.

These exercise the GL-plane rendering path (marked slow by conftest because the
filename matches ``test_renderer_3d*``). The pure algorithm is covered in
``test_stratal_slice.py``.
"""

from __future__ import annotations

import numpy as np
import pytest

from geoviz_seismic.renderer_3d import Renderer3D
from geoviz_seismic.stratal import (
    build_proportional_surfaces,
    stratal_slice_volume,
)


def _flat_volume(ni=8, nx=8, nt=24, reflector=12):
    """Volume with a single flat reflector (amp 1.0) at sample *reflector*."""
    vol = np.zeros((ni, nx, nt), np.float32)
    vol[:, :, reflector] = 1.0
    return vol


# ---------------------------------------------------------------------------
# State-only tests (headless, no GL context — the Renderer3D.__new__ pattern)
# ---------------------------------------------------------------------------

def test_set_stratal_slices_records_state_when_not_loaded():
    r = Renderer3D.__new__(Renderer3D)
    r._loaded = False
    r._stratal_surfaces = []
    r._stratal_visibility = []
    r._stratal_labels = []
    r._stratal_active = None
    r._stratal_opacity = 0.8
    r._stratal_enabled = True
    r._stratal_plane_items = {}

    top = np.full((4, 4), 2.0)
    bot = np.full((4, 4), 10.0)
    surfs = build_proportional_surfaces(top, bot, [0.25, 0.5, 0.75])
    Renderer3D.set_stratal_slices(
        r, surfs, labels=["q1", "q2", "q3"], active=1, opacity=0.6,
    )
    assert len(r._stratal_surfaces) == 3
    assert r._stratal_labels == ["q1", "q2", "q3"]
    assert r._stratal_active == 1
    assert r._stratal_opacity == 0.6
    snap = Renderer3D.get_stratal_slices(r)
    assert len(snap) == 3
    # the half surface mean depth = 6.0
    assert snap[1][0] == "q2"
    assert pytest.approx(snap[1][2], abs=1e-4) == 6.0


def test_set_stratal_slices_empty_clears():
    r = Renderer3D.__new__(Renderer3D)
    r._loaded = False
    r._stratal_surfaces = [np.zeros((2, 2))]
    r._stratal_visibility = [True]
    r._stratal_labels = ["x"]
    r._stratal_active = 0
    r._stratal_opacity = 0.8
    r._stratal_enabled = True
    r._stratal_plane_items = {}
    Renderer3D.set_stratal_slices(r, [])
    assert r._stratal_surfaces == []
    assert r._stratal_active is None


def test_clear_stratal_slices_resets():
    r = Renderer3D.__new__(Renderer3D)
    r._loaded = False
    r._stratal_surfaces = [np.zeros((2, 2))]
    r._stratal_visibility = [True]
    r._stratal_labels = ["x"]
    r._stratal_active = 0
    r._stratal_plane_items = {}
    Renderer3D.clear_stratal_slices(r)
    assert r._stratal_surfaces == []
    assert r._stratal_labels == []
    assert r._stratal_active is None


def test_set_stratal_visible_toggles_flag():
    r = Renderer3D.__new__(Renderer3D)
    r._loaded = False
    r._stratal_surfaces = [np.zeros((2, 2))]
    r._stratal_visibility = [True]
    r._stratal_labels = ["x"]
    r._stratal_active = 0
    r._stratal_opacity = 0.8
    r._stratal_enabled = True
    r._stratal_plane_items = {}
    Renderer3D.set_stratal_visible(r, False)
    assert r._stratal_enabled is False
    Renderer3D.set_stratal_visible(r, True)
    assert r._stratal_enabled is True


# ---------------------------------------------------------------------------
# GL integration (real Renderer3D + qtbot)
# ---------------------------------------------------------------------------

def test_stratal_planes_render_after_load(qtbot):
    widget = Renderer3D()
    qtbot.addWidget(widget)
    vol = _flat_volume()
    widget.load_volume(vol)
    assert widget._loaded

    top = np.full(vol.shape[:2], 4.0)
    bot = np.full(vol.shape[:2], 20.0)
    surfs = build_proportional_surfaces(top, bot, [0.25, 0.5, 0.75])
    widget.set_stratal_slices(surfs)

    # three stratal planes should now be registered as GL items.
    assert len(widget._stratal_plane_items) == 3
    # each plane is a (image, line) pair added to the view.
    for image, line in widget._stratal_plane_items.values():
        assert image in widget._view.items
        assert line in widget._view.items


def test_stratal_clear_removes_planes(qtbot):
    widget = Renderer3D()
    qtbot.addWidget(widget)
    vol = _flat_volume()
    widget.load_volume(vol)

    top = np.full(vol.shape[:2], 4.0)
    bot = np.full(vol.shape[:2], 20.0)
    widget.set_stratal_slices(build_proportional_surfaces(top, bot, [0.5]))
    assert widget._stratal_plane_items
    widget.clear_stratal_slices()
    assert widget._stratal_plane_items == {}


def test_stratal_reflector_hits_half_surface(qtbot):
    """End-to-end: a flat reflector at sample 12 must light up the k=0.5
    stratal surface between top=4 and bot=20 (half = 12)."""
    widget = Renderer3D()
    qtbot.addWidget(widget)
    vol = _flat_volume(reflector=12)
    widget.load_volume(vol)

    top = np.full(vol.shape[:2], 4.0)
    bot = np.full(vol.shape[:2], 20.0)
    widget.set_stratal_slices(build_proportional_surfaces(top, bot, [0.5]))

    snap = widget.get_stratal_slices()
    assert len(snap) == 1
    assert pytest.approx(snap[0][2], abs=1e-4) == 12.0  # mean depth = 12


def test_stratal_slice_volume_feeds_renderer(qtbot):
    """The end-to-end helper produces surfaces + amp maps usable by the page."""
    widget = Renderer3D()
    qtbot.addWidget(widget)
    vol = _flat_volume(reflector=12)
    widget.load_volume(vol)

    top = np.full(vol.shape[:2], 4.0)
    bot = np.full(vol.shape[:2], 20.0)
    maps, surfs = stratal_slice_volume(
        vol, top, bot, fractions=[0.25, 0.5, 0.75], return_surfaces=True
    )
    widget.set_stratal_slices(list(surfs))
    assert len(widget._stratal_plane_items) == 3
    # the half-way map should be all ones (reflector hit).
    assert np.allclose(maps[1], 1.0)
