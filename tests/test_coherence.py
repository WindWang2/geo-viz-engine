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


def test_coherence_c3_uses_30_power_iterations(monkeypatch):
    """#845: the C3 power iteration ran only 10 times, leaving a measurable
    bias on noisy windows (max |Δ| ≈ 0.07–0.09 vs the exact eigenvalue);
    the shipped iteration count must be ~30 (linear cost)."""
    import geoviz_seismic.attributes as attrs

    calls = []
    orig = attrs._power_iteration_c3

    def spy(traces, n_iter=10):
        calls.append(n_iter)
        return orig(traces, n_iter)

    monkeypatch.setattr(attrs, "_power_iteration_c3", spy)
    rng = np.random.default_rng(0)
    data = rng.standard_normal((4, 6, 20)).astype(np.float32)
    compute_coherence_c3(data, win_il=1, win_xl=1, win_t=2)
    assert calls, "power iteration must run"
    assert all(n >= 30 for n in calls), f"iteration count must be ~30, got {calls}"


def test_coherence_c3_converges_to_exact_eigenvalue():
    """#845: with 30 iterations C3 must match the exact largest-eigenvalue
    ratio closely on noisy windows — the 10-iteration default left up to
    ~0.09 error on synthetic noise."""
    from numpy.lib.stride_tricks import sliding_window_view

    def _exact_c3(traces):
        A = traces
        lam = np.linalg.eigvalsh(A @ A.transpose(0, 2, 1))[:, -1]
        total = np.sum(A ** 2, axis=(1, 2))
        return np.where(total > 0, lam / total, 1.0)

    def _volume_traces(data, wil, wxl, wt):
        n_il, n_xl, n_t = data.shape
        p = np.pad(data, (((wil - 1) // 2,) * 2, ((wxl - 1) // 2,) * 2,
                          ((wt - 1) // 2,) * 2), mode="reflect")
        out = []
        for il in range(n_il):
            chunk = p[il:il + wil, 0:n_xl + wxl - 1, :]
            swv = sliding_window_view(chunk, (wxl, wt), axis=(1, 2))
            out.append(np.ascontiguousarray(swv.transpose(1, 2, 0, 3, 4))
                       .reshape(-1, wil * wxl, wt))
        return np.concatenate(out, axis=0)

    t = np.linspace(0, 2 * np.pi, 50, dtype=np.float32)
    flat = np.tile(np.sin(t), (8, 12, 1))
    rng = np.random.default_rng(11)
    data = (flat + 0.4 * rng.standard_normal(flat.shape).astype(np.float32))

    coh = compute_coherence_c3(data, win_il=1, win_xl=1, win_t=2)
    traces = _volume_traces(data, 3, 3, 5)
    ref = _exact_c3(traces).reshape(8, 12, 50)
    d = np.abs(coh - ref)
    assert d.max() < 0.01, f"30-iteration C3 bias too large: max|Δ|={d.max():.4f}"
    assert d.mean() < 1e-4, f"mean C3 bias too large: {d.mean():.6f}"
