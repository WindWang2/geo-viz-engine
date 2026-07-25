"""Tests for ColormapManager.normalize_to_index + apply_colormap (ticket #50).

Self-consistency tests verify the two methods produce correct output by
checking their own invariants (index range, dtype, shape, clipping, degenerate
data) and cross-checking that normalize_to_index + LUT gather == apply_colormap.
"""
from __future__ import annotations

import numpy as np
import pytest

from geoviz_seismic.colormap import ColormapManager


def _cupy_available() -> bool:
    try:
        import cupy  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# normalize_to_index
# ---------------------------------------------------------------------------

class TestNormalizeToIndex:
    """ColormapManager.normalize_to_index correctness."""

    def test_numpy_basic(self):
        data = np.random.randn(100, 100).astype(np.float32)
        result = ColormapManager.normalize_to_index(data, lut_size=256)

        assert result.dtype == np.uint8
        assert result.shape == data.shape
        assert result.min() >= 0
        assert result.max() <= 255

    def test_numpy_with_value_range(self):
        data = np.random.randn(64, 64).astype(np.float32)
        vr = (-2.0, 2.0)
        result = ColormapManager.normalize_to_index(data, lut_size=256, value_range=vr)

        # Values within range map to interior indices
        mid = (vr[0] + vr[1]) / 2
        mid_idx = np.argmin(np.abs(data - mid))
        assert 50 <= result.flat[mid_idx] <= 200

    def test_numpy_custom_lut_size(self):
        data = np.linspace(0, 1, 500).reshape(50, 10).astype(np.float32)
        result = ColormapManager.normalize_to_index(data, lut_size=128)

        assert result.max() <= 127
        assert result.min() >= 0

    def test_dmin_equals_dmax(self):
        """Flat data should produce all-zero indices, not NaN."""
        data = np.full((10, 10), 3.14, dtype=np.float32)
        result = ColormapManager.normalize_to_index(data, lut_size=256)
        assert result.dtype == np.uint8
        assert result.max() == 0
        assert result.min() == 0

    def test_clipping(self):
        """Values outside value_range should clip to 0 and lut_size-1."""
        data = np.array([[-10.0, 0.0, 10.0]], dtype=np.float32)
        result = ColormapManager.normalize_to_index(data, lut_size=256, value_range=(-1.0, 1.0))
        assert result[0, 0] == 0       # below range -> 0
        assert result[0, 2] == 255     # above range -> 255

    def test_returns_uint8(self):
        data = np.random.randn(32, 32).astype(np.float32)
        result = ColormapManager.normalize_to_index(data, lut_size=256)
        assert result.dtype == np.uint8

    def test_monotonic(self):
        """Larger data values should produce larger-or-equal indices."""
        data = np.linspace(-1, 1, 100).reshape(10, 10).astype(np.float32)
        result = ColormapManager.normalize_to_index(data, lut_size=256)
        flat = result.flatten()
        # Monotonically non-decreasing
        assert np.all(np.diff(flat) >= 0)

    @pytest.mark.skipif(
        not _cupy_available(),
        reason="CuPy not available",
    )
    def test_gpu_parity_basic(self):
        """GPU path produces same result as CPU path."""
        import cupy as cp

        data_np = np.random.randn(300, 300).astype(np.float32)
        data_gpu = cp.asarray(data_np)

        cpu_result = ColormapManager.normalize_to_index(data_np, lut_size=256)
        gpu_result = ColormapManager.normalize_to_index(data_gpu, lut_size=256)

        assert isinstance(gpu_result, np.ndarray)
        np.testing.assert_array_equal(cpu_result, gpu_result)

    @pytest.mark.skipif(
        not _cupy_available(),
        reason="CuPy not available",
    )
    def test_small_cupy_returns_numpy_host(self):
        """Preview planes (≤128²) must not leak cupy into GL_R8 upload.

        Regression: small cupy inputs skipped the GPU path but still returned
        a cupy ndarray, and prepare_r8_upload(np.asarray(...)) raised TypeError.
        """
        import cupy as cp

        data_np = np.random.randn(100, 80).astype(np.float32)
        data_gpu = cp.asarray(data_np)
        assert data_gpu.size < 256 * 256

        result = ColormapManager.normalize_to_index(data_gpu, lut_size=256)
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.uint8
        assert result.shape == data_np.shape
        expected = ColormapManager.normalize_to_index(data_np, lut_size=256)
        np.testing.assert_array_equal(result, expected)


# ---------------------------------------------------------------------------
# apply_colormap
# ---------------------------------------------------------------------------

class TestApplyColormap:
    """ColormapManager.apply_colormap correctness."""

    def test_numpy_basic(self):
        data = np.random.randn(100, 100).astype(np.float32)
        result = ColormapManager.apply_colormap(data, name="seismic")

        assert result.dtype == np.uint8
        assert result.shape == (*data.shape, 4)

    def test_numpy_with_value_range(self):
        data = np.random.randn(64, 64).astype(np.float32)
        vr = (-3.0, 3.0)
        result = ColormapManager.apply_colormap(data, name="seismic", value_range=vr)

        assert result.shape == (64, 64, 4)

    def test_numpy_gray_colormap(self):
        data = np.random.randn(50, 50).astype(np.float32)
        result = ColormapManager.apply_colormap(data, name="gray")

        assert result.shape == (50, 50, 4)

    def test_returns_rgba(self):
        data = np.random.randn(32, 32).astype(np.float32)
        result = ColormapManager.apply_colormap(data, name="seismic")
        assert result.shape == (32, 32, 4)
        assert result.dtype == np.uint8

    def test_dmin_equals_dmax(self):
        """Flat data should map to the first LUT entry everywhere."""
        data = np.full((10, 10), 5.0, dtype=np.float32)
        result = ColormapManager.apply_colormap(data, name="seismic")
        lut = ColormapManager.get_colormap("seismic")
        np.testing.assert_array_equal(result[..., :3], np.broadcast_to(lut[0, :3], (10, 10, 3)))

    def test_with_explicit_lut(self):
        """Can pass a raw LUT array instead of a name."""
        data = np.random.randn(40, 40).astype(np.float32)
        lut = ColormapManager.get_colormap("jet")

        name_result = ColormapManager.apply_colormap(data, name="jet")
        lut_result = ColormapManager.apply_colormap(data, lut=lut)

        np.testing.assert_array_equal(name_result, lut_result)

    def test_cross_check_with_normalize_to_index(self):
        """apply_colormap == lut[normalize_to_index] for the same data + range."""
        data = np.random.randn(80, 60).astype(np.float32)
        vr = (float(np.nanmin(data)), float(np.nanmax(data)))
        lut = ColormapManager.get_colormap("seismic")

        rgba = ColormapManager.apply_colormap(data, name="seismic", value_range=vr)
        idx = ColormapManager.normalize_to_index(data, lut_size=len(lut), value_range=vr)

        np.testing.assert_array_equal(rgba, lut[idx])

    @pytest.mark.skipif(
        not _cupy_available(),
        reason="CuPy not available",
    )
    def test_gpu_parity_basic(self):
        """GPU path produces same result as CPU path for large arrays."""
        import cupy as cp

        data_np = np.random.randn(300, 300).astype(np.float32)
        data_gpu = cp.asarray(data_np)

        cpu_result = ColormapManager.apply_colormap(data_np, name="seismic")
        gpu_result = ColormapManager.apply_colormap(data_gpu, name="seismic")

        np.testing.assert_array_equal(cpu_result, gpu_result)

    @pytest.mark.skipif(
        not _cupy_available(),
        reason="CuPy not available",
    )
    def test_gpu_small_array_uses_cpu(self):
        """Small GPU arrays should fall back to CPU path (size guard)."""
        import cupy as cp

        data_gpu = cp.asarray(np.random.randn(10, 10).astype(np.float32))
        data_np = cp.asnumpy(data_gpu)

        cpu_result = ColormapManager.apply_colormap(data_np, name="seismic")
        gpu_result = ColormapManager.apply_colormap(data_gpu, name="seismic")

        np.testing.assert_array_equal(cpu_result, gpu_result)


# ---------------------------------------------------------------------------
# GPU dispatch + cache
# ---------------------------------------------------------------------------

class TestGPUDispatch:
    """GPU/CPU dispatch is internal to ColormapManager."""

    def test_small_numpy_array_works(self):
        """Small arrays should work fine (CPU path)."""
        data = np.random.randn(5, 5).astype(np.float32)
        result = ColormapManager.normalize_to_index(data, lut_size=256)
        assert result.shape == (5, 5)

    def test_gpu_min_elements_constant_exists(self):
        """The size guard threshold should be defined in colormap.py."""
        from geoviz_seismic import colormap

        assert hasattr(colormap, "_GPU_MIN_ELEMENTS")
        assert colormap._GPU_MIN_ELEMENTS == 256 * 256

    def test_cupy_available_flag_exists(self):
        """The _CUPY_AVAILABLE flag should be in colormap.py now."""
        from geoviz_seismic import colormap

        assert hasattr(colormap, "_CUPY_AVAILABLE")

    def test_lut_size_over_256_raises(self):
        """lut_size > 256 should raise - uint8 can't represent it."""
        data = np.random.randn(5, 5).astype(np.float32)
        with pytest.raises(ValueError, match="lut_size must be in"):
            ColormapManager.normalize_to_index(data, lut_size=512)
