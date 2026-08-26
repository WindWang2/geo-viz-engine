"""Regression tests for GL resource lifecycle + stratal reload state (G-PR3).

Covers:
- ``DualGLVolumeItem.clean()`` releases the main 3D texture, cmap/horizon/
  normal textures, shader program and VBO (previously only the small LUT
  textures were deleted, and only when a context happened to be current).
- ``GLImageLutItem.clean()`` releases the R8 index texture, LUT texture,
  per-instance shader program and VBO, and is invoked on every removeItem
  teardown path.
- ``WiggleTraceRenderer.destroy()`` also deletes the colormap LUT texture.
- ``load_volume`` with a different ``(nI, nX)`` clears stale stratal state
  instead of crashing in ``extract_stratal_slice``.

GL deletion is verified with monkeypatched ``glDeleteTextures`` /
``glDeleteProgram`` and a fake current context, so no real GL context is
required (offscreen CI friendly).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from geoviz_seismic import renderer_3d
from geoviz_seismic.renderer_3d import DualGLVolumeItem, GLImageLutItem, Renderer3D
from geoviz_seismic.stratal import build_proportional_surfaces


@pytest.fixture
def fake_gl(monkeypatch):
    """Patch renderer_3d's GL entry points + current context; record deletes."""
    deleted_textures: list[int] = []
    deleted_programs: list[int] = []
    monkeypatch.setattr(
        renderer_3d.GL, "glDeleteTextures",
        lambda ids: deleted_textures.extend(list(ids)),
    )
    monkeypatch.setattr(
        renderer_3d.GL, "glDeleteProgram",
        lambda program: deleted_programs.append(program),
    )
    fake_ctx = object()
    monkeypatch.setattr(
        renderer_3d, "QtGui",
        SimpleNamespace(
            QOpenGLContext=SimpleNamespace(currentContext=lambda: fake_ctx),
        ),
    )
    return SimpleNamespace(
        textures=deleted_textures, programs=deleted_programs, ctx=fake_ctx,
    )


def _make_dual_item() -> DualGLVolumeItem:
    """Bare instance with fake GL ids (no QObject/QApplication needed)."""
    item = DualGLVolumeItem.__new__(DualGLVolumeItem)
    item.texture = 101            # main 3D volume texture
    item._primary_cmap_tex = 102
    item._overlay_cmap_tex = 103
    item._sculpt_horizon_tex = 104
    item._normal_tex = 105
    item._customShaderProgram = 201
    item.m_vbo_position = Mock()
    item.m_vbo_position.isCreated.return_value = True
    item._needUpload = False
    return item


def _make_lut_item() -> GLImageLutItem:
    item = GLImageLutItem.__new__(GLImageLutItem)
    item.texture = 11             # R8 index texture
    item._lut_tex = 12
    item._lut_shader_program = 55
    item._cmap_name = "seismic"
    item._lut_needs_upload = False
    item._needUpdate = False
    item.m_vbo_position = Mock()
    item.m_vbo_position.isCreated.return_value = True
    return item


# ---------------------------------------------------------------------------
# DualGLVolumeItem.clean()
# ---------------------------------------------------------------------------

def test_dual_volume_clean_releases_all_gl_resources(fake_gl):
    item = _make_dual_item()
    item.clean()
    assert sorted(fake_gl.textures) == [101, 102, 103, 104, 105]
    assert fake_gl.programs == [201]
    item.m_vbo_position.destroy.assert_called_once()
    assert item.texture is None
    assert item._primary_cmap_tex is None
    assert item._overlay_cmap_tex is None
    assert item._sculpt_horizon_tex is None
    assert item._normal_tex is None
    assert item._customShaderProgram is None
    # Repaintable after clean: next paint re-uploads from scratch.
    assert item._needUpload is True


def test_dual_volume_clean_is_idempotent(fake_gl):
    item = _make_dual_item()
    # Real QOpenGLBuffer reports isCreated() == False after destroy().
    item.m_vbo_position.isCreated.side_effect = [True, False]
    item.clean()
    item.clean()
    assert sorted(fake_gl.textures) == [101, 102, 103, 104, 105]
    assert fake_gl.programs == [201]
    item.m_vbo_position.destroy.assert_called_once()


def test_dual_volume_clean_without_context_queues_deferred_deletes(monkeypatch):
    deleted: list[int] = []
    monkeypatch.setattr(
        renderer_3d.GL, "glDeleteTextures", lambda ids: deleted.extend(list(ids))
    )
    monkeypatch.setattr(
        renderer_3d, "QtGui",
        SimpleNamespace(QOpenGLContext=SimpleNamespace(currentContext=lambda: None)),
    )
    renderer_3d._PENDING_GL_TEXTURE_DELETES.clear()
    renderer_3d._PENDING_GL_PROGRAM_DELETES.clear()

    item = _make_dual_item()
    item.clean()
    assert deleted == []
    # Handles dropped from the item and queued for deferred flush
    assert item.texture is None
    assert item._primary_cmap_tex is None
    assert item._overlay_cmap_tex is None
    assert item._sculpt_horizon_tex is None
    assert item._normal_tex is None
    assert item._customShaderProgram is None
    assert sorted(renderer_3d._PENDING_GL_TEXTURE_DELETES) == [101, 102, 103, 104, 105]
    assert renderer_3d._PENDING_GL_PROGRAM_DELETES == [201]

    renderer_3d._PENDING_GL_TEXTURE_DELETES.clear()
    renderer_3d._PENDING_GL_PROGRAM_DELETES.clear()


def test_dual_volume_clean_tolerates_partial_state(fake_gl):
    """Items torn down before any upload (all ids None) must not crash."""
    item = _make_dual_item()
    item.texture = None
    item._primary_cmap_tex = None
    item._overlay_cmap_tex = None
    item._sculpt_horizon_tex = None
    item._normal_tex = None
    item._customShaderProgram = None
    item.m_vbo_position.isCreated.return_value = False
    item.clean()
    assert fake_gl.textures == []
    assert fake_gl.programs == []
    item.m_vbo_position.destroy.assert_not_called()


# ---------------------------------------------------------------------------
# GLImageLutItem.clean()
# ---------------------------------------------------------------------------

def test_lut_item_clean_releases_all_gl_resources(fake_gl):
    item = _make_lut_item()
    item.clean()
    assert sorted(fake_gl.textures) == [11, 12]
    assert fake_gl.programs == [55]
    item.m_vbo_position.destroy.assert_called_once()
    assert item.texture is None
    assert item._lut_tex is None
    assert item._lut_shader_program is None
    assert item._needUpdate is True
    assert item._lut_needs_upload is True


def test_lut_item_clean_is_idempotent(fake_gl):
    item = _make_lut_item()
    item.clean()
    item.clean()
    assert sorted(fake_gl.textures) == [11, 12]
    assert fake_gl.programs == [55]


def test_lut_item_clean_without_context_queues_deferred_deletes(monkeypatch):
    """#116: the no-context branch must queue handles, not silently drop them.

    The b9ac5d93 merge added a second ``GLImageLutItem.clean`` after the
    deferred-delete version; the later class-body definition shadowed the
    earlier one, and its ``ctx is None: return`` leaked the R8/LUT textures
    (and program) on every teardown where ``makeCurrent`` failed.
    """
    monkeypatch.setattr(
        renderer_3d, "QtGui",
        SimpleNamespace(QOpenGLContext=SimpleNamespace(currentContext=lambda: None)),
    )
    renderer_3d._PENDING_GL_TEXTURE_DELETES.clear()
    renderer_3d._PENDING_GL_PROGRAM_DELETES.clear()

    item = _make_lut_item()
    item.clean()

    # Handles dropped from the item and queued for the next-paint flush.
    assert item.texture is None
    assert item._lut_tex is None
    assert item._lut_shader_program is None
    assert sorted(renderer_3d._PENDING_GL_TEXTURE_DELETES) == [11, 12]
    assert renderer_3d._PENDING_GL_PROGRAM_DELETES == [55]
    # Repaintable after clean: next paint re-uploads from scratch.
    assert item._needUpdate is True
    assert item._lut_needs_upload is True

    # Idempotent: the second call must not re-queue the same ids.
    item.clean()
    assert sorted(renderer_3d._PENDING_GL_TEXTURE_DELETES) == [11, 12]
    assert renderer_3d._PENDING_GL_PROGRAM_DELETES == [55]

    renderer_3d._PENDING_GL_TEXTURE_DELETES.clear()
    renderer_3d._PENDING_GL_PROGRAM_DELETES.clear()


def test_flush_pending_gl_deletes_handles_int_program_ids(monkeypatch):
    """Queued int (raw GLuint) shader programs must actually be deleted.

    ``queue_gl_program_delete`` is used for pyqtgraph ``gl_shaders`` int
    handles; the flush loop previously only handled Qt shader-program
    objects, so deferred programs leaked (#116).
    """
    deleted_textures: list = []
    deleted_programs: list[int] = []
    monkeypatch.setattr(
        renderer_3d.GL, "glDeleteTextures", lambda *a: deleted_textures.extend(a[-1])
    )
    monkeypatch.setattr(
        renderer_3d.GL, "glDeleteProgram", lambda program: deleted_programs.append(program)
    )

    renderer_3d._PENDING_GL_TEXTURE_DELETES.extend([31, 32])
    renderer_3d._PENDING_GL_PROGRAM_DELETES.append(77)
    try:
        renderer_3d.flush_pending_gl_deletes()
    finally:
        renderer_3d._PENDING_GL_TEXTURE_DELETES.clear()
        renderer_3d._PENDING_GL_PROGRAM_DELETES.clear()

    assert sorted(deleted_textures) == [31, 32]
    assert deleted_programs == [77]
    assert renderer_3d._PENDING_GL_TEXTURE_DELETES == []
    assert renderer_3d._PENDING_GL_PROGRAM_DELETES == []


# ---------------------------------------------------------------------------
# Teardown paths invoke clean() on discarded items
# ---------------------------------------------------------------------------

def test_load_volume_cleans_discarded_gl_items(qtbot, monkeypatch):
    widget = Renderer3D()
    qtbot.addWidget(widget)
    widget.load_volume(np.random.randn(8, 8, 16).astype(np.float32))

    discarded = [
        widget._volume_visual,
        widget._img_il,
        widget._img_xl,
        widget._img_t,
    ]
    for item in discarded:
        assert item is not None
        monkeypatch.setattr(item, "clean", Mock())

    widget.load_volume(np.random.randn(6, 6, 8).astype(np.float32))

    for item in discarded:
        item.clean.assert_called()


def test_full_slice_rebuild_cleans_replaced_planes(qtbot, monkeypatch):
    widget = Renderer3D()
    qtbot.addWidget(widget)
    widget.load_volume(np.random.randn(8, 8, 16).astype(np.float32))

    old_il = widget._img_il
    monkeypatch.setattr(old_il, "clean", Mock())

    widget._update_slice_planes()  # full rebuild path
    old_il.clean.assert_called()
    assert widget._img_il is not old_il


# ---------------------------------------------------------------------------
# Stratal state on volume reload
# ---------------------------------------------------------------------------

def test_load_volume_with_different_shape_clears_stratal(qtbot):
    """Setting stratal slices then loading a different (nI, nX) volume must
    not raise (extract_stratal_slice shape-mismatch ValueError) and must drop
    the stale stratal state."""
    widget = Renderer3D()
    qtbot.addWidget(widget)
    vol1 = np.random.randn(8, 8, 24).astype(np.float32)
    widget.load_volume(vol1)

    top = np.full(vol1.shape[:2], 4.0)
    bot = np.full(vol1.shape[:2], 20.0)
    surfs = build_proportional_surfaces(top, bot, [0.25, 0.5])
    widget.set_stratal_slices(surfs, labels=["q1", "mid"])
    assert len(widget._stratal_surfaces) == 2
    assert widget._stratal_plane_items  # synced because the volume is loaded

    vol2 = np.random.randn(6, 10, 24).astype(np.float32)  # different (nI, nX)
    widget.load_volume(vol2)  # previously raised ValueError

    assert widget._loaded
    assert widget._stratal_surfaces == []
    assert widget._stratal_plane_items == {}
    assert widget.get_stratal_slices() == ()


def test_clear_resets_stratal_state(qtbot):
    widget = Renderer3D()
    qtbot.addWidget(widget)
    vol = np.random.randn(8, 8, 24).astype(np.float32)
    widget.load_volume(vol)
    top = np.full(vol.shape[:2], 4.0)
    bot = np.full(vol.shape[:2], 20.0)
    widget.set_stratal_slices(build_proportional_surfaces(top, bot, [0.5]))
    assert widget._stratal_surfaces

    widget.clear()

    assert widget._stratal_surfaces == []
    assert widget._stratal_plane_items == {}
    assert widget._stratal_labels == []
    assert widget._stratal_active is None


def test_stratal_slices_set_before_load_render_after_load(qtbot):
    """Surfaces registered while no volume is loaded must survive the load
    when their (nI, nX) shape matches the new volume."""
    widget = Renderer3D()
    qtbot.addWidget(widget)
    vol = np.random.randn(8, 8, 24).astype(np.float32)
    top = np.full(vol.shape[:2], 4.0)
    bot = np.full(vol.shape[:2], 20.0)
    surfs = build_proportional_surfaces(top, bot, [0.5])
    widget.set_stratal_slices(surfs)  # not loaded yet — state only

    widget.load_volume(vol)

    assert len(widget._stratal_surfaces) == 1
    assert len(widget._stratal_plane_items) == 1


def test_load_volume_same_shape_keeps_stratal(qtbot):
    """Reloading a same-shaped volume keeps the stratal slices (they remain
    geometrically valid in sample-index space)."""
    widget = Renderer3D()
    qtbot.addWidget(widget)
    vol1 = np.random.randn(8, 8, 24).astype(np.float32)
    widget.load_volume(vol1)
    top = np.full(vol1.shape[:2], 4.0)
    bot = np.full(vol1.shape[:2], 20.0)
    widget.set_stratal_slices(build_proportional_surfaces(top, bot, [0.25, 0.5]))

    widget.load_volume(np.random.randn(8, 8, 24).astype(np.float32))

    assert len(widget._stratal_surfaces) == 2
    assert len(widget._stratal_plane_items) == 2


# ---------------------------------------------------------------------------
# WiggleTraceRenderer LUT texture lifecycle
# ---------------------------------------------------------------------------

def test_wiggle_destroy_releases_lut_texture(monkeypatch):
    from geoviz_seismic.renderer import wiggle_instanced as wi

    deleted: list[int] = []
    monkeypatch.setattr(wi.GL, "glDeleteTextures", lambda ids: deleted.extend(list(ids)))

    renderer = wi.WiggleTraceRenderer()
    renderer.set_data(np.zeros((4, 10), np.float32), mock_gl=True)
    renderer.set_colormap(np.zeros((256, 4), np.uint8), mock_gl=True)
    tex_id = renderer.texture.texture_id
    lut_id = renderer.lut_texture_id
    assert tex_id is not None and lut_id is not None

    renderer.destroy(mock_gl=False)

    assert tex_id in deleted
    assert lut_id in deleted
    assert renderer.texture.texture_id is None
    assert renderer.lut_texture_id is None


def test_wiggle_destroy_mock_mode_clears_ids_without_gl_calls(monkeypatch):
    from geoviz_seismic.renderer import wiggle_instanced as wi

    deleted: list[int] = []
    monkeypatch.setattr(wi.GL, "glDeleteTextures", lambda ids: deleted.extend(list(ids)))

    renderer = wi.WiggleTraceRenderer()
    renderer.set_colormap(np.zeros((256, 4), np.uint8), mock_gl=True)
    renderer.destroy(mock_gl=True)
    renderer.destroy(mock_gl=True)  # idempotent

    assert renderer.lut_texture_id is None
    assert deleted == []
