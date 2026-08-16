"""Red tests for Phase 11: Curvature attributes (dip, azimuth, curvature)."""

import numpy as np
import pytest

from geoviz_seismic.attributes import compute_dip, compute_azimuth, compute_curvature


class TestDipShape:
    """Output shape and dtype for compute_dip."""

    def test_3d_shape(self):
        data = np.random.randn(10, 20, 30).astype(np.float32)
        dip_il, dip_xl = compute_dip(data)
        assert dip_il.shape == data.shape
        assert dip_xl.shape == data.shape

    def test_2d_shape(self):
        data = np.random.randn(20, 30).astype(np.float32)
        dip_il, dip_xl = compute_dip(data)
        assert dip_il.shape == data.shape
        assert dip_xl.shape == data.shape

    def test_output_dtype(self):
        data = np.random.randn(10, 20, 30).astype(np.float32)
        dip_il, dip_xl = compute_dip(data)
        assert dip_il.dtype == np.float32
        assert dip_xl.dtype == np.float32


class TestDipValueRange:
    """Dip values should be in [-pi/2, pi/2]."""

    def test_values_in_range(self):
        data = np.random.randn(20, 30, 40).astype(np.float32)
        dip_il, dip_xl = compute_dip(data)
        assert np.all(np.abs(dip_il) <= np.pi / 2 + 1e-6)
        assert np.all(np.abs(dip_xl) <= np.pi / 2 + 1e-6)

    def test_flat_reflector_zero_dip(self):
        """A perfectly flat reflector should have dip ~0."""
        trace = np.sin(np.linspace(0, 2 * np.pi, 30)).astype(np.float32)
        data = np.tile(trace, (10, 15, 1))
        dip_il, dip_xl = compute_dip(data)
        interior_il = dip_il[2:-2, 2:-2, 2:-2]
        interior_xl = dip_xl[2:-2, 2:-2, 2:-2]
        np.testing.assert_allclose(interior_il, 0.0, atol=0.1)
        np.testing.assert_allclose(interior_xl, 0.0, atol=0.1)


class TestAzimuthShape:
    """Output shape and range for compute_azimuth."""

    def test_shape_matches_input(self):
        dip_il = np.random.randn(10, 20, 30).astype(np.float32)
        dip_xl = np.random.randn(10, 20, 30).astype(np.float32)
        az = compute_azimuth(dip_il, dip_xl)
        assert az.shape == dip_il.shape

    def test_range_0_to_2pi(self):
        dip_il = np.random.randn(10, 20, 30).astype(np.float32)
        dip_xl = np.random.randn(10, 20, 30).astype(np.float32)
        az = compute_azimuth(dip_il, dip_xl)
        assert np.all(az >= 0.0)
        assert np.all(az <= 2 * np.pi + 1e-6)


class TestCurvatureShape:
    """Output shape for all curvature kinds."""

    @pytest.mark.parametrize("kind", ["gaussian", "mean", "max", "min", "dip", "strike"])
    def test_3d_shape(self, kind):
        data = np.random.randn(15, 20, 30).astype(np.float32)
        result = compute_curvature(data, kind=kind)
        assert result.shape == data.shape
        assert result.dtype == np.float32

    def test_2d_shape(self):
        data = np.random.randn(20, 30).astype(np.float32)
        result = compute_curvature(data, kind="mean")
        assert result.shape == data.shape


class TestCurvatureSynthetic:
    """Curvature on synthetic structures."""

    def test_dome_vs_syncline_opposite_sign(self):
        """Volumes whose slope fields differ only by an overall sign must
        produce mean-curvature volumes that are exact negatives of each
        other.  This validates the second-derivative pipeline's linearity
        in the sign of the underlying slope, independent of wavelet shape.

        Construction: amplitude = (x*t)·alpha — slope_xl = x/t·alpha after
        division.  Flipping alpha flips slope_xl → flips its second
        derivatives → flips mean curvature."""
        x = np.linspace(0.5, 1.5, 25)   # strictly positive so slope is finite
        y = np.linspace(0.5, 1.5, 25)
        t = np.linspace(1.0, 2.0, 40)   # strictly positive to avoid /0
        X, Y, T = np.meshgrid(x, y, t, indexing="ij")
        # Quadratic spatial term in amplitude — slope is linear in x,y after
        # division by grad_t, second derivative is constant ≠ 0.
        base = T + 0.1 * X**3 + 0.1 * Y**3
        dome_vol = base.astype(np.float32)
        sync_vol = (T - 0.1 * X**3 - 0.1 * Y**3).astype(np.float32)
        dome_cur = compute_curvature(dome_vol, kind="mean")
        sync_cur = compute_curvature(sync_vol, kind="mean")
        interior_d = dome_cur[3:-3, 3:-3, 3:-3]
        interior_s = sync_cur[3:-3, 3:-3, 3:-3]
        assert np.abs(interior_d).mean() > 1e-4
        # Should be sign-flipped (negatives of each other)
        np.testing.assert_allclose(interior_d, -interior_s, atol=1e-4)
        # And the dome volume mean should be non-zero with consistent sign
        assert abs(interior_d.mean()) > 1e-4

    def test_plane_zero_curvature(self):
        """A plane should have near-zero curvature."""
        data = (np.arange(30) * 0.1).astype(np.float32)
        data = np.tile(data, (10, 15, 1))
        result = compute_curvature(data, kind="gaussian")
        interior = result[3:-3, 3:-3, 3:-3]
        np.testing.assert_allclose(interior, 0.0, atol=0.05)


class TestCurvature2DSmoothingAxisOrder:
    """2-D slices are (n_xl, n_t) — the smoothing window must be applied in
    that axis order.  Regression: ``uniform_filter`` was called with
    ``size=(size_t, size_xl)``, swapping the crossline/time windows."""

    def test_asymmetric_window_matches_reference(self):
        from scipy.ndimage import uniform_filter

        rng = np.random.default_rng(0)
        data = rng.standard_normal((40, 60)).astype(np.float32)
        win_xl, win_t = 1, 4  # asymmetric — swapped order gives a different map
        out = compute_curvature(data, kind="mean", win_xl=win_xl, win_t=win_t)

        # Reference: replicate the 2-D pipeline with the correct axis order.
        # slope_il is identically zero on 2-D input, so mean = d2_xl / 2.
        grad_xl = np.gradient(data, axis=0)
        grad_t = np.gradient(data, axis=1)
        gt_safe = np.where(np.abs(grad_t) < 1e-10, 1e-10, grad_t)
        slope_xl = (grad_xl / gt_safe).astype(np.float32)
        slope_xl = uniform_filter(
            slope_xl, size=(2 * win_xl + 1, 2 * win_t + 1), mode="reflect"
        )
        d2_xl = np.gradient(np.gradient(slope_xl, axis=0), axis=0)
        ref = (d2_xl / 2.0).astype(np.float32)

        np.testing.assert_allclose(out, ref, rtol=1e-4, atol=1e-4)

    def test_axis_order_is_observable(self):
        """Guard against a vacuous reference: the swapped-window variant
        (the original bug) must produce a visibly different map."""
        from scipy.ndimage import uniform_filter

        rng = np.random.default_rng(0)
        data = rng.standard_normal((40, 60)).astype(np.float32)
        win_xl, win_t = 1, 4
        out = compute_curvature(data, kind="mean", win_xl=win_xl, win_t=win_t)

        grad_xl = np.gradient(data, axis=0)
        grad_t = np.gradient(data, axis=1)
        gt_safe = np.where(np.abs(grad_t) < 1e-10, 1e-10, grad_t)
        slope_xl = (grad_xl / gt_safe).astype(np.float32)
        buggy = uniform_filter(
            slope_xl, size=(2 * win_t + 1, 2 * win_xl + 1), mode="reflect"
        )
        ref_buggy = (np.gradient(np.gradient(buggy, axis=0), axis=0) / 2.0).astype(np.float32)
        assert not np.allclose(out, ref_buggy, rtol=1e-3, atol=1e-3)

    def test_window_follows_crossline_axis(self):
        """A ridge running along the time axis: smoothing across crosslines
        (win_xl large) must blur it, smoothing along time (win_t large)
        must not."""
        t = np.linspace(0, 4 * np.pi, 80, dtype=np.float32)
        xl = np.linspace(0, 2 * np.pi, 60, dtype=np.float32)
        # Amplitude varies only across crosslines (axis 0); linear ramp in
        # time keeps grad_t constant so slope_xl is a clean 1-D profile.
        data = (np.sin(xl)[:, None] + 0.5 * t[None, :]).astype(np.float32)

        cur_xl = compute_curvature(data, kind="mean", win_xl=5, win_t=1)
        cur_t = compute_curvature(data, kind="mean", win_xl=1, win_t=5)
        interior = np.s_[10:-10, 10:-10]
        # Heavy crossline smoothing suppresses the ridge curvature much more
        # than heavy time smoothing (the signal is constant along time).
        assert np.abs(cur_xl[interior]).mean() < np.abs(cur_t[interior]).mean()


class TestCurvatureEdgeHandling:
    """Edge behavior."""

    def test_no_nan(self):
        data = np.random.randn(15, 20, 30).astype(np.float32)
        for kind in ["gaussian", "mean", "max", "min"]:
            result = compute_curvature(data, kind=kind)
            assert not np.any(np.isnan(result))

    def test_no_inf(self):
        data = np.random.randn(15, 20, 30).astype(np.float32)
        for kind in ["gaussian", "mean", "max", "min"]:
            result = compute_curvature(data, kind=kind)
            assert not np.any(np.isinf(result))


class TestCurvatureGpuConsistency:
    """GPU path must match CPU path."""

    def test_gpu_matches_cpu(self):
        try:
            import cupy as cp

            cp.cuda.Device().id
        except Exception:
            pytest.skip("CuPy not available")

        rng = np.random.default_rng(42)
        data = rng.standard_normal((15, 20, 25)).astype(np.float32)
        for kind in ["gaussian", "mean", "max"]:
            coh_cpu = compute_curvature(data, kind=kind, use_gpu=False)
            coh_gpu = compute_curvature(data, kind=kind, use_gpu=True)
            # GPU/CPU float32 reductions differ by ~1e-3 on noisy random input
            np.testing.assert_allclose(coh_cpu, coh_gpu, atol=5e-3, rtol=1e-3)
