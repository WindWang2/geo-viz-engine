"""Red tests for Phase 9: Coherence (C3 eigenstructure) attribute."""

import numpy as np
import pytest

from geoviz_seismic.attributes import compute_coherence_c3


class TestCoherenceC3Shape:
    """Output shape should match input shape for 3D volumes."""

    def test_3d_shape_preserved(self):
        """Coherence output has same shape as input (n_il, n_xl, n_samples)."""
        data = np.random.randn(10, 20, 30).astype(np.float32)
        result = compute_coherence_c3(data)
        assert result.shape == data.shape

    def test_2d_inline_slice_shape(self):
        """A 2D (n_xl, n_samples) slice should also work — treated as single inline."""
        data = np.random.randn(20, 30).astype(np.float32)
        result = compute_coherence_c3(data)
        assert result.shape == data.shape

    def test_output_dtype_float32(self):
        """Output should be float32."""
        data = np.random.randn(10, 20, 30).astype(np.float32)
        result = compute_coherence_c3(data)
        assert result.dtype == np.float32


class TestCoherenceC3ValueRange:
    """Coherence values must be in [0, 1]."""

    def test_values_in_unit_range(self):
        """All coherence values should be between 0 and 1."""
        data = np.random.randn(20, 30, 40).astype(np.float32)
        result = compute_coherence_c3(data)
        assert np.all(result >= 0.0)
        assert np.all(result <= 1.0)

    def test_flat_reflector_high_coherence(self):
        """A perfectly flat (constant) reflector should yield coherence ~1.0."""
        # All traces identical → covariance matrix rank 1 → coherence = 1
        trace = np.sin(np.linspace(0, 2 * np.pi, 30)).astype(np.float32)
        data = np.tile(trace, (10, 15, 1))  # (10 il, 15 xl, 30 samples)
        result = compute_coherence_c3(data, win_il=3, win_xl=3, win_t=5)
        # Interior samples should be ~1.0 (edges may differ)
        interior = result[3:-3, 3:-3, 3:-3]
        np.testing.assert_allclose(interior, 1.0, atol=0.05)

    def test_random_noise_lower_coherence(self):
        """Random noise should have lower coherence than a flat reflector."""
        rng = np.random.default_rng(42)
        flat_data = np.ones((15, 15, 30), dtype=np.float32)
        flat_data *= np.sin(np.linspace(0, 2 * np.pi, 30)).astype(np.float32)
        noisy_data = rng.standard_normal((15, 15, 30)).astype(np.float32)

        coh_flat = compute_coherence_c3(flat_data, win_il=3, win_xl=3, win_t=5)
        coh_noisy = compute_coherence_c3(noisy_data, win_il=3, win_xl=3, win_t=5)

        # Interior mean coherence
        mean_flat = coh_flat[3:-3, 3:-3, 3:-3].mean()
        mean_noisy = coh_noisy[3:-3, 3:-3, 3:-3].mean()
        assert mean_flat > mean_noisy


class TestCoherenceC3WindowParams:
    """Window size parameters should be configurable."""

    def test_custom_window_sizes(self):
        """Custom il/xl/time window sizes should work."""
        data = np.random.randn(15, 20, 30).astype(np.float32)
        result = compute_coherence_c3(data, win_il=5, win_xl=5, win_t=7)
        assert result.shape == data.shape

    def test_default_window_sizes(self):
        """Default window sizes should work without explicit args."""
        data = np.random.randn(15, 20, 30).astype(np.float32)
        result = compute_coherence_c3(data)
        assert result.shape == data.shape

    def test_small_volume_no_crash(self):
        """Very small volume (smaller than window) should not crash."""
        data = np.random.randn(3, 3, 5).astype(np.float32)
        result = compute_coherence_c3(data, win_il=3, win_xl=3, win_t=3)
        assert result.shape == data.shape


class TestCoherenceC3EdgeHandling:
    """Edge samples should be handled gracefully."""

    def test_no_nan_in_output(self):
        """No NaN values in output for random input."""
        data = np.random.randn(15, 20, 30).astype(np.float32)
        result = compute_coherence_c3(data)
        assert not np.any(np.isnan(result))

    def test_no_inf_in_output(self):
        """No Inf values in output."""
        data = np.random.randn(15, 20, 30).astype(np.float32)
        result = compute_coherence_c3(data)
        assert not np.any(np.isinf(result))


class TestCoherenceC3GpuConsistency:
    """GPU path must match CPU path numerically when CuPy is available."""

    def test_gpu_matches_cpu(self):
        """CPU and GPU coherence values should be identical (float32 tolerance)."""
        try:
            import cupy as cp

            cp.cuda.Device().id
        except Exception:
            pytest.skip("CuPy not available")

        rng = np.random.default_rng(42)
        data = rng.standard_normal((20, 25, 35)).astype(np.float32)
        coh_cpu = compute_coherence_c3(data, win_il=3, win_xl=3, win_t=5, use_gpu=False)
        coh_gpu = compute_coherence_c3(data, win_il=3, win_xl=3, win_t=5, use_gpu=True)
        np.testing.assert_allclose(coh_cpu, coh_gpu, atol=1e-5)
