"""Tests for the well-tie / attribute / 3D-curve APIs promoted into geo-viz-engine.

阶段 1 engine sink-down: these used to live in
``paleo_workbench/viz/geomodel/well_seismic.py``.
"""

from __future__ import annotations

import numpy as np
import pytest

from geoviz_seismic import analyze_lithology_crossplot, blend_rgba
from geoviz_well_seismic_3d import offset_curve_along_trajectory
from geoviz_well_tie import (
    compute_reflectivity,
    correlate_synthetic_to_trace,
    shift_depths,
    synthetic_from_logs,
)


def _two_layer_logs(n: int = 100, interface: int = 50):
    """Blocky sonic/density pair with a single impedance contrast."""
    sonic = np.full(n, 300.0, dtype=np.float32)
    density = np.full(n, 2.3, dtype=np.float32)
    sonic[interface:] = 200.0
    density[interface:] = 2.7
    return sonic, density


class TestSyntheticFromLogs:
    def test_length_is_one_less_than_the_logs(self):
        sonic, density = _two_layer_logs(100)
        synthetic = synthetic_from_logs(sonic, density, wavelet_freq=30.0, dt_s=0.002)
        assert synthetic.shape == (99,)
        assert synthetic.dtype == np.float32

    def test_energy_concentrates_at_the_interface(self):
        sonic, density = _two_layer_logs(100, interface=50)
        synthetic = synthetic_from_logs(sonic, density, wavelet_freq=30.0, dt_s=0.002)
        # The Ricker is centred on the reflector; the peak must land near index 49.
        assert abs(int(np.argmax(np.abs(synthetic))) - 49) <= 2

    def test_blocky_logs_are_quiet_away_from_the_interface(self):
        sonic, density = _two_layer_logs(200, interface=100)
        synthetic = synthetic_from_logs(sonic, density)
        peak = np.max(np.abs(synthetic))
        assert np.max(np.abs(synthetic[:60])) < 0.01 * peak

    def test_matches_manual_reflectivity_convolution(self):
        """synthetic_from_logs must be exactly compute_reflectivity + Ricker convolution."""
        from geoviz_well_tie import generate_synthetic, ricker_wavelet

        sonic, density = _two_layer_logs(80, interface=40)
        expected = generate_synthetic(
            compute_reflectivity(np.clip(sonic, 10.0, 1000.0), density),
            ricker_wavelet(65, dt=0.002, peak_freq=30.0),
        )
        assert np.allclose(synthetic_from_logs(sonic, density), expected)

    @pytest.mark.parametrize("n", [0, 1])
    def test_too_few_samples_returns_empty(self, n):
        result = synthetic_from_logs(np.full(n, 300.0), np.full(n, 2.3))
        assert result.shape == (0,)
        assert result.dtype == np.float32

    def test_sonic_clip_guards_against_zero_slowness(self):
        sonic = np.array([300.0, 0.0, 300.0, 300.0], dtype=np.float32)
        density = np.full(4, 2.3, dtype=np.float32)
        assert np.isfinite(synthetic_from_logs(sonic, density)).all()

    def test_sonic_clip_can_be_disabled(self):
        sonic, density = _two_layer_logs(40, interface=20)
        unclipped = synthetic_from_logs(sonic, density, sonic_clip=None)
        # Values are well inside [10, 1000], so disabling the clamp changes nothing.
        assert np.allclose(unclipped, synthetic_from_logs(sonic, density))

    def test_higher_frequency_narrows_the_wavelet_response(self):
        sonic, density = _two_layer_logs(200, interface=100)
        low = synthetic_from_logs(sonic, density, wavelet_freq=15.0)
        high = synthetic_from_logs(sonic, density, wavelet_freq=60.0)

        def _support(trace):
            return int(np.count_nonzero(np.abs(trace) > 0.05 * np.max(np.abs(trace))))

        assert _support(high) < _support(low)

    def test_half_length_controls_the_wavelet_size(self):
        sonic, density = _two_layer_logs(400, interface=200)
        short = synthetic_from_logs(sonic, density, half_length_s=0.016)
        long = synthetic_from_logs(sonic, density, half_length_s=0.128)
        assert short.shape == long.shape == (399,)

        def _support(trace):
            return int(np.count_nonzero(np.abs(trace) > 0.01 * np.max(np.abs(trace))))

        assert _support(short) < _support(long)


class TestCorrelateSyntheticToTrace:
    def test_recovers_a_known_shift(self):
        sonic, density = _two_layer_logs()
        synthetic = synthetic_from_logs(sonic, density, wavelet_freq=30.0)
        shift, cc = correlate_synthetic_to_trace(synthetic, np.roll(synthetic, 5))
        assert abs(shift - 5) <= 2
        assert cc > 0.8

    def test_zero_shift_for_an_identical_trace(self):
        sonic, density = _two_layer_logs()
        synthetic = synthetic_from_logs(sonic, density)
        shift, cc = correlate_synthetic_to_trace(synthetic, synthetic)
        assert shift == 0
        assert cc == pytest.approx(1.0, abs=1e-6)

    def test_dc_offset_does_not_shift_the_answer(self):
        """Mean removal is the reason this exists alongside auto_tie_with_quality."""
        sonic, density = _two_layer_logs()
        synthetic = synthetic_from_logs(sonic, density)
        shifted = np.roll(synthetic, 4)
        clean, _ = correlate_synthetic_to_trace(synthetic, shifted)
        biased, _ = correlate_synthetic_to_trace(synthetic, shifted + 500.0)
        assert clean == biased

    @pytest.mark.parametrize(
        ("synthetic", "trace"),
        [
            (np.array([]), np.array([1.0, 2.0])),
            (np.array([1.0, 2.0]), np.array([])),
            (np.array([]), np.array([])),
        ],
    )
    def test_empty_inputs(self, synthetic, trace):
        assert correlate_synthetic_to_trace(synthetic, trace) == (0, 0.0)

    def test_constant_inputs(self):
        assert correlate_synthetic_to_trace(np.ones(20), np.arange(20.0)) == (0, 0.0)
        assert correlate_synthetic_to_trace(np.arange(20.0), np.ones(20)) == (0, 0.0)

    def test_correlation_is_capped_at_one(self):
        _, cc = correlate_synthetic_to_trace(np.sin(np.arange(64) / 3.0), np.sin(np.arange(64) / 3.0))
        assert cc <= 1.0


class TestShiftDepths:
    def test_applies_a_bulk_offset(self):
        depths = np.linspace(0.0, 1000.0, 11)
        shifted = shift_depths(depths, 10.0)
        assert shifted.shape == depths.shape
        assert shifted[0] == 10.0
        assert shifted[-1] == 1010.0

    def test_does_not_mutate_the_input(self):
        depths = np.array([0.0, 100.0])
        shift_depths(depths, 50.0)
        assert np.allclose(depths, [0.0, 100.0])

    def test_negative_shift(self):
        assert np.allclose(shift_depths(np.array([100.0, 200.0]), -25.0), [75.0, 175.0])


class TestOffsetCurveAlongTrajectory:
    def test_vertical_well_offsets_along_x(self):
        path = np.array([[0, 0, 0], [0, 0, -10], [0, 0, -20]], dtype=np.float32)
        values = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        out = offset_curve_along_trajectory(path, values, scale=2.0)
        assert out.shape == (3, 3)
        assert np.allclose(out[:, 0], [2.0, 4.0, 6.0])
        assert np.allclose(out[:, 1], 0.0)
        # Z must be untouched — the offset is purely horizontal.
        assert np.allclose(out[:, 2], path[:, 2])

    def test_offset_is_horizontal_and_perpendicular_in_plan_view(self):
        # Well deviating along +X: the horizontal normal is +Y.
        path = np.array([[0, 0, 0], [10, 0, -10], [20, 0, -20]], dtype=np.float32)
        out = offset_curve_along_trajectory(path, np.ones(3, dtype=np.float32), scale=5.0)
        assert np.allclose(out[:, 1], 5.0)
        assert np.allclose(out[:, 0], path[:, 0])
        assert np.allclose(out[:, 2], path[:, 2])

    def test_offset_magnitude_scales_with_value_and_scale(self):
        path = np.array([[0, 0, 0], [0, 0, -10]], dtype=np.float32)
        out = offset_curve_along_trajectory(path, np.array([4.0, 4.0], dtype=np.float32), scale=0.25)
        assert np.allclose(np.linalg.norm(out - path, axis=1), 1.0)

    def test_offset_is_independent_of_station_spacing(self):
        """Normalizing the tangent keeps the vertical-well threshold scale-free."""
        dense = np.array([[0, 0, 0], [0.001, 0, -0.01]], dtype=np.float32)
        sparse = np.array([[0, 0, 0], [100.0, 0, -1000.0]], dtype=np.float32)
        values = np.ones(2, dtype=np.float32)
        dense_dir = offset_curve_along_trajectory(dense, values, scale=1.0) - dense
        sparse_dir = offset_curve_along_trajectory(sparse, values, scale=1.0) - sparse
        assert np.allclose(dense_dir, sparse_dir, atol=1e-4)

    def test_empty_path(self):
        out = offset_curve_along_trajectory(np.empty((0, 3)), np.empty(0))
        assert out.shape == (0, 3)

    def test_single_point_falls_back_to_x(self):
        out = offset_curve_along_trajectory(
            np.array([[5, 5, -1]], dtype=np.float32), np.array([2.0], dtype=np.float32), scale=1.0
        )
        assert np.allclose(out, [[7.0, 5.0, -1.0]])

    def test_rejects_short_curve(self):
        path = np.zeros((5, 3), dtype=np.float32)
        with pytest.raises(ValueError, match="3 samples but well_path has 5"):
            offset_curve_along_trajectory(path, np.zeros(3, dtype=np.float32))

    def test_returns_float32(self):
        out = offset_curve_along_trajectory(np.zeros((4, 3)), np.zeros(4))
        assert out.dtype == np.float32


class TestBlendRgba:
    def test_shape_and_dtype(self):
        shape = (20, 20)
        out = blend_rgba(
            np.linspace(0, 1, 400).reshape(shape),
            np.full(shape, 0.5),
            np.linspace(1, 0, 400).reshape(shape),
        )
        assert out.shape == (*shape, 4)
        assert out.dtype == np.float32

    def test_channels_span_zero_to_one(self):
        r = np.array([[10.0, 20.0], [30.0, 40.0]])
        out = blend_rgba(r, r, r)
        assert out[..., 0].min() == pytest.approx(0.0)
        assert out[..., 0].max() == pytest.approx(1.0)

    def test_alpha_is_constant(self):
        out = blend_rgba(np.arange(4.0), np.arange(4.0), np.arange(4.0), alpha=0.42)
        assert np.allclose(out[..., 3], 0.42)

    def test_constant_channel_becomes_zero(self):
        out = blend_rgba(np.full(5, 7.0), np.arange(5.0), np.arange(5.0))
        assert np.allclose(out[..., 0], 0.0)

    def test_channels_are_normalized_independently(self):
        out = blend_rgba(np.array([0.0, 1.0]), np.array([0.0, 1000.0]), np.array([0.0, 1.0]))
        assert np.allclose(out[..., 0], out[..., 1])

    def test_works_on_1d_input(self):
        assert blend_rgba(np.arange(6.0), np.arange(6.0), np.arange(6.0)).shape == (6, 4)


class TestAnalyzeLithologyCrossplot:
    def test_points_and_clusters(self):
        gr = np.array([10.0, 12.0, 90.0, 95.0])
        ai = np.array([8.0, 8.5, 3.0, 3.2])
        result = analyze_lithology_crossplot(gr, ai, ["sand", "sand", "shale", "shale"])

        assert len(result["points"]) == 4
        assert result["points"][0] == {"gr": 10.0, "ai": 8.0, "lithology": "sand"}
        assert set(result["clusters"]) == {"sand", "shale"}
        assert result["clusters"]["sand"]["count"] == 2
        assert result["clusters"]["sand"]["mean_gr"] == pytest.approx(11.0)
        assert result["clusters"]["shale"]["mean_ai"] == pytest.approx(3.1)

    def test_cluster_std(self):
        result = analyze_lithology_crossplot(
            np.array([10.0, 20.0]), np.array([5.0, 5.0]), ["sand", "sand"]
        )
        assert result["clusters"]["sand"]["std_gr"] == pytest.approx(5.0)
        assert result["clusters"]["sand"]["std_ai"] == pytest.approx(0.0)

    def test_missing_labels_become_unknown(self):
        result = analyze_lithology_crossplot(np.arange(4.0), np.arange(4.0), ["sand"])
        assert result["clusters"]["Unknown"]["count"] == 3
        assert result["points"][3]["lithology"] == "Unknown"

    def test_empty_input(self):
        result = analyze_lithology_crossplot(np.array([]), np.array([]), [])
        assert result == {"points": [], "clusters": {}}
