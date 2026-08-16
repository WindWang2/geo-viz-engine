# tests/test_texture_axis_contract.py
"""Regression tests for the 3D texture axis-order contract.

pyqtgraph's ``GLVolumeItem._uploadData`` uploads the volume with
``data.transpose((2, 1, 0, 3))`` while declaring the *original* shape as
(width, height, depth). Because the C-order buffer varies fastest along the
last spatial axis, this makes GL texel ``(i, j, k)`` address ``data[i, j, k]``
— shader ``v_texcoord.x`` maps to data axis 0 (inline), y to axis 1
(crossline), z to axis 2 (sample).

The hillshading normal texture and the sculpting horizon texture must follow
the same convention. These tests assert the pure upload-preparation helpers
produce buffers whose simulated GL texel fetches match the source arrays,
using deliberately non-square shapes so a missing transpose cannot hide.
"""

import numpy as np
import pytest

from geoviz_seismic.renderer_3d import (
    prepare_horizon_texture_upload,
    prepare_normal_texture_upload,
)


def _fetch_texel_3d(buffer, width, height, depth, i, j, k, comps):
    """Simulate a GL 3D texel fetch from a C-order upload buffer.

    GL defines texel (i, j, k) at buffer offset ((k*height + j)*width + i).
    """
    flat = buffer.reshape(-1, comps)
    return flat[(k * height + j) * width + i]


def test_normal_texture_upload_matches_volume_contract():
    # Non-cubic shape so any axis mix-up changes the result.
    ni, nx, nt = 3, 5, 7
    rng = np.random.default_rng(0)
    normal_data = rng.integers(0, 256, size=(ni, nx, nt, 3), dtype=np.uint8)

    buffer, w, h, d = prepare_normal_texture_upload(normal_data)

    # Declared dims are the original spatial shape, as in
    # GLVolumeItem._uploadData.
    assert (w, h, d) == (ni, nx, nt)
    assert buffer.dtype == np.uint8
    assert buffer.flags["C_CONTIGUOUS"]

    # Simulated fetch: texel (i, j, k) must equal normal_data[i, j, k],
    # i.e. the shader samples the normal map in the same coordinate frame as
    # the main volume texture.
    for i, j, k in [(0, 0, 0), (2, 4, 6), (1, 3, 5), (2, 0, 6)]:
        texel = _fetch_texel_3d(buffer, w, h, d, i, j, k, 3)
        np.testing.assert_array_equal(texel, normal_data[i, j, k])


def test_normal_texture_matches_main_volume_transpose():
    """Normal buffer must use the exact transpose GLVolumeItem applies."""
    ni, nx, nt = 4, 2, 6
    rng = np.random.default_rng(1)
    volume = rng.integers(0, 256, size=(ni, nx, nt, 4), dtype=np.uint8)
    normals = rng.integers(0, 256, size=(ni, nx, nt, 3), dtype=np.uint8)

    volume_buffer = np.ascontiguousarray(volume.transpose((2, 1, 0, 3)))
    normal_buffer, w, h, d = prepare_normal_texture_upload(normals)

    assert (w, h, d) == volume.shape[:3]
    # Same (i, j, k) texel in both textures must address the same voxel.
    i, j, k = 3, 1, 5
    vol_texel = _fetch_texel_3d(volume_buffer, ni, nx, nt, i, j, k, 4)
    nrm_texel = _fetch_texel_3d(normal_buffer, w, h, d, i, j, k, 3)
    np.testing.assert_array_equal(vol_texel, volume[i, j, k])
    np.testing.assert_array_equal(nrm_texel, normals[i, j, k])


def test_horizon_texture_upload_transpose_contract():
    # (nI, nX) grid, deliberately non-square: a missing transpose would
    # mirror the sculpting mask across the grid diagonal.
    n_i, n_x = 4, 6
    grid = np.arange(n_i * n_x, dtype=np.float64).reshape(n_i, n_x)

    buffer, w, h = prepare_horizon_texture_upload(grid)

    # width must be the inline axis (data axis 0), height the crossline axis.
    assert (w, h) == (n_i, n_x)
    assert buffer.dtype == np.float32
    assert buffer.flags["C_CONTIGUOUS"]

    # Simulated GL 2D fetch: texel (i, j) sits at buffer offset j*width + i
    # and must equal grid[i, j], so shader v_texcoord.x addresses the inline
    # axis like the volume texture.
    flat = buffer.reshape(-1)
    for i, j in [(0, 0), (3, 5), (1, 4), (2, 0)]:
        assert flat[j * w + i] == pytest.approx(grid[i, j])


def test_upload_helpers_reject_bad_shapes():
    with pytest.raises(ValueError):
        prepare_normal_texture_upload(np.zeros((3, 5, 7), dtype=np.uint8))
    with pytest.raises(ValueError):
        prepare_normal_texture_upload(np.zeros((3, 5, 7, 4), dtype=np.uint8))
    with pytest.raises(ValueError):
        prepare_horizon_texture_upload(np.zeros((4, 6, 2), dtype=np.float32))
