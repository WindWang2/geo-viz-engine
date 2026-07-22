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


from geoviz_seismic.seismic_view import SeismicView


def _view(qtbot):
    v = SeismicView(auto_load=False)
    qtbot.addWidget(v)
    vol = np.random.default_rng(1).standard_normal((8, 8, 8)).astype(np.float32)
    v._renderer_3d.load_volume(vol)
    return v


def test_isosurface_controls_disabled_without_extractor(qtbot):
    v = _view(qtbot)
    v._refresh_isosurface_controls()
    assert not v._iso_checkbox.isEnabled()
    assert not v._iso_spin.isEnabled()


def test_isosurface_controls_enabled_with_extractor(qtbot):
    iso_mod.set_isosurface_extractor(
        lambda vol, iso: (np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int32))
    )
    v = _view(qtbot)
    v._refresh_isosurface_controls()
    assert v._iso_checkbox.isEnabled()
    assert v._iso_spin.isEnabled()


def test_isosurface_toggle_extracts_and_clears(qtbot):
    calls = []

    def fake(vol, iso):
        calls.append(iso)
        verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
        return verts, np.array([[0, 1, 2]], dtype=np.int32)

    iso_mod.set_isosurface_extractor(fake)
    v = _view(qtbot)
    v._refresh_isosurface_controls()
    v._iso_checkbox.setChecked(True)
    qtbot.wait(350)  # debounce 200ms
    assert len(calls) == 1
    assert v._renderer_3d._isosurface_item is not None
    v._iso_checkbox.setChecked(False)
    assert v._renderer_3d._isosurface_item is None


def test_isosurface_threshold_debounce(qtbot):
    calls = []

    def fake(vol, iso):
        calls.append(iso)
        verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
        return verts, np.array([[0, 1, 2]], dtype=np.int32)

    iso_mod.set_isosurface_extractor(fake)
    v = _view(qtbot)
    v._refresh_isosurface_controls()
    v._iso_checkbox.setChecked(True)
    qtbot.wait(350)
    assert len(calls) == 1
    v._iso_spin.setValue(v._iso_spin.value() + 0.01)
    v._iso_spin.setValue(v._iso_spin.value() + 0.01)
    qtbot.wait(350)
    assert len(calls) == 2  # 两次快速改动合并为一次提取


def test_isosurface_extractor_error_unchecks(qtbot):
    def boom(vol, iso):
        raise RuntimeError("extraction failed")

    iso_mod.set_isosurface_extractor(boom)
    v = _view(qtbot)
    v._refresh_isosurface_controls()
    v._iso_checkbox.setChecked(True)
    qtbot.wait(350)
    assert not v._iso_checkbox.isChecked()
    assert v._renderer_3d._isosurface_item is None


def test_isosurface_rebuilt_after_volume_swap(qtbot):
    calls = []

    def fake(vol, iso):
        calls.append((vol.shape, iso))
        verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
        return verts, np.array([[0, 1, 2]], dtype=np.int32)

    iso_mod.set_isosurface_extractor(fake)
    v = _view(qtbot)
    v._refresh_isosurface_controls()
    v._iso_checkbox.setChecked(True)
    qtbot.wait(350)
    assert len(calls) == 1
    assert v._renderer_3d._isosurface_item is not None
    # 新数据体加载：_clear_visuals 清掉 mesh，但 checkbox 仍勾选 → 刷新后应自动重建
    v._renderer_3d.load_volume(
        np.random.default_rng(2).standard_normal((6, 6, 6)).astype(np.float32)
    )
    assert v._renderer_3d._isosurface_item is None
    v._refresh_isosurface_controls()
    qtbot.wait(350)
    assert len(calls) == 2
    assert v._renderer_3d._isosurface_item is not None
