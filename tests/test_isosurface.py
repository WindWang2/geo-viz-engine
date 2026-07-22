from __future__ import annotations

import numpy as np
import pytest

from geoviz_seismic import isosurface as iso_mod
from geoviz_seismic.renderer_3d import Renderer3D


@pytest.fixture(autouse=True)
def _reset_extractor():
    iso_mod.set_isosurface_extractor(None)
    yield
    iso_mod.set_isosurface_extractor(None)


def _renderer(qtbot):
    r = Renderer3D()
    qtbot.addWidget(r)
    vol = np.random.default_rng(0).standard_normal((8, 8, 8)).astype(np.float32)
    r.load_volume(vol)
    return r


def test_extractor_hook_set_get():
    fn = lambda vol, iso: (np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int32))
    iso_mod.set_isosurface_extractor(fn)
    assert iso_mod.get_isosurface_extractor() is fn
    iso_mod.set_isosurface_extractor(None)
    assert iso_mod.get_isosurface_extractor() is None


def test_set_and_clear_isosurface(qtbot):
    r = _renderer(qtbot)
    verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    faces = np.array([[0, 1, 2]], dtype=np.int32)
    r.set_isosurface(verts, faces)
    assert r._isosurface_item is not None
    assert r._isosurface_item in r._view.items
    r.clear_isosurface()
    assert r._isosurface_item is None
    assert all(type(it).__name__ != "GLMeshItem" or it not in r._view.items for it in [])


def test_set_isosurface_replaces_previous(qtbot):
    r = _renderer(qtbot)
    verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    faces = np.array([[0, 1, 2]], dtype=np.int32)
    r.set_isosurface(verts, faces)
    first = r._isosurface_item
    r.set_isosurface(verts, faces)
    assert r._isosurface_item is not None
    assert r._isosurface_item is not first
    assert first not in r._view.items


def test_set_isosurface_empty_mesh_is_noop(qtbot):
    r = _renderer(qtbot)
    r.set_isosurface(np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int32))
    assert r._isosurface_item is None


def test_isosurface_cleared_on_new_volume(qtbot):
    r = _renderer(qtbot)
    verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    faces = np.array([[0, 1, 2]], dtype=np.int32)
    r.set_isosurface(verts, faces)
    r.load_volume(np.zeros((4, 4, 4), dtype=np.float32))
    assert r._isosurface_item is None


def test_isosurface_scaled_by_spacing(qtbot):
    r = Renderer3D()
    qtbot.addWidget(r)
    vol = np.random.default_rng(0).standard_normal((8, 8, 8)).astype(np.float32)
    r.load_volume(vol, origin=(0, 0, 0), spacing=(2.0, 1.0, 3.0))
    verts = np.array([[1, 1, 1]], dtype=np.float32)
    faces = np.array([[0, 0, 0]], dtype=np.int32)
    r.set_isosurface(verts, faces)
    md = r._isosurface_item.opts['meshdata']
    np.testing.assert_allclose(md.vertexes()[0], [2.0, 1.0, 3.0], atol=1e-6)


def test_volume_data_accessor(qtbot):
    r = _renderer(qtbot)
    assert isinstance(r.volume_data(), np.ndarray)
    empty = Renderer3D()
    qtbot.addWidget(empty)
    assert empty.volume_data() is None
