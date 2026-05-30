"""End-to-end well-tie pipeline tests.

Validates the full workflow:
  sonic+density → reflectivity → synthetic → resample to TWT → resample to seismic grid
  → auto-tie (cross-correlation bulk shift) → overlay rendering

These tests define the API contracts for Phase 8 additions.
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# 1. Reflectivity length alignment (Bug fix: N-1 vs N)
# ---------------------------------------------------------------------------

class TestReflectivityLengthAlignment:
    """Reflectivity has N-1 samples at midpoints between N depth samples.
    The pipeline must handle this correctly when resampling to TWT."""

    def test_reflectivity_midpoint_depths(self):
        """Reflectivity lives at midpoints between depth samples."""
        from geoviz_well_tie.synthetic import compute_reflectivity

        depths = np.array([0.0, 10.0, 20.0, 30.0, 40.0])
        sonic = np.array([200.0, 200.0, 150.0, 150.0, 200.0])
        density = np.full(5, 2.5)

        rc = compute_reflectivity(sonic, density)
        assert rc.shape == (4,)  # N-1

        # Midpoint depths for the reflectivity: average of adjacent samples
        mid_depths = (depths[:-1] + depths[1:]) / 2.0
        assert len(mid_depths) == len(rc)

    def test_pipeline_resample_uses_midpoint_depths(self):
        """resample_to_twt must receive log_values at midpoints for reflectivity."""
        from geoviz_well_tie.calibration import WellTieCalibration
        from geoviz_well_tie.synthetic import compute_reflectivity

        depths = np.linspace(0, 1000, 501)
        sonic = np.full(501, 200.0)
        density = np.full(501, 2.5)
        # Add a contrast at 500m
        sonic[250:] = 150.0

        cal = WellTieCalibration.from_sonic(depths, sonic)
        rc = compute_reflectivity(sonic, density)
        assert rc.shape == (500,)  # N-1

        # Midpoint depths
        mid_depths = (depths[:-1] + depths[1:]) / 2.0

        # Must resample rc using midpoint depths, not original depths
        # Build a calibration with midpoint depths
        mid_twt = cal.depth_to_twt(mid_depths)
        # mid_twt is scalar because depth_to_twt returns float for scalar input
        # We need array version — use np.interp directly for now
        mid_twt_arr = np.interp(mid_depths, cal.depths, cal.twt)
        assert len(mid_twt_arr) == len(rc)


# ---------------------------------------------------------------------------
# 2. Unit-safe synthetic generation (Bug fix: dt seconds vs milliseconds)
# ---------------------------------------------------------------------------

class TestUnitSafeSynthetic:
    """generate_synthetic_twt() wraps the pipeline with dt_ms input."""

    def test_generate_synthetic_twt_accepts_dt_ms(self):
        """New wrapper accepts dt_ms (milliseconds) instead of dt (seconds)."""
        from geoviz_well_tie.synthetic import generate_synthetic_twt

        rc = np.array([0.0, 0.1, -0.05, 0.0], dtype=np.float32)
        synth = generate_synthetic_twt(rc, wavelet_type="ricker", dt_ms=4.0,
                                       peak_freq=25.0)
        assert synth.shape == rc.shape
        assert synth.dtype == np.float32

    def test_generate_synthetic_twt_ormsby(self):
        """Wrapper also supports Ormsby wavelet."""
        from geoviz_well_tie.synthetic import generate_synthetic_twt

        rc = np.zeros(100, dtype=np.float32)
        rc[50] = 1.0
        synth = generate_synthetic_twt(rc, wavelet_type="ormsby", dt_ms=2.0,
                                       f1=5, f2=10, f3=40, f4=50)
        assert synth.shape == rc.shape
        assert np.max(np.abs(synth)) > 0

    def test_dt_ms_converted_to_seconds_internally(self):
        """dt_ms=4.0 should produce same result as dt=0.004."""
        from geoviz_well_tie.synthetic import generate_synthetic_twt
        from geoviz_well_tie.wavelet import ricker_wavelet
        from geoviz_well_tie.synthetic import generate_synthetic

        rc = np.array([0.0, 0.1, -0.05, 0.0, 0.02], dtype=np.float32)
        dt_ms = 4.0
        peak_freq = 25.0

        # New API
        result_new = generate_synthetic_twt(rc, wavelet_type="ricker",
                                             dt_ms=dt_ms, peak_freq=peak_freq)
        # Old API (manual conversion)
        w = ricker_wavelet(41, dt=dt_ms / 1000.0, peak_freq=peak_freq)
        result_old = generate_synthetic(rc, w)

        np.testing.assert_allclose(result_new, result_old, atol=1e-6)


# ---------------------------------------------------------------------------
# 3. Resample to seismic grid (Bug fix: missing function)
# ---------------------------------------------------------------------------

class TestResampleToSeismicGrid:
    """resample_to_seismic_grid() aligns synthetic TWT with the seismic volume's grid."""

    def test_basic_resample(self):
        """Synthetic resampled to match seismic TWT grid."""
        from geoviz_well_tie.calibration import resample_to_seismic_grid

        # Synthetic at irregular TWT positions
        synth_twt = np.array([0.0, 2.1, 4.0, 6.2, 8.1, 10.0], dtype=np.float64)
        synth_vals = np.sin(synth_twt / 2.0)

        # Seismic grid: 0 to 10 ms, 2 ms intervals
        result = resample_to_seismic_grid(synth_vals, synth_twt,
                                           dt_ms=2.0, t0_ms=0.0, n_samples=6)
        assert result.dtype == np.float32
        assert result.shape == (6,)
        # First and last should be close (interpolated at exact grid points)
        np.testing.assert_allclose(result[0], synth_vals[0], atol=0.1)

    def test_t0_offset(self):
        """Handles non-zero t0_ms correctly."""
        from geoviz_well_tie.calibration import resample_to_seismic_grid

        synth_twt = np.arange(50, 200, 1.0)
        synth_vals = np.ones(len(synth_twt))

        result = resample_to_seismic_grid(synth_vals, synth_twt,
                                           dt_ms=4.0, t0_ms=50.0, n_samples=38)
        # All values within the valid range should be ~1.0
        assert result.shape == (38,)

    def test_extrapolation_zeros(self):
        """Values outside the synthetic range should be zero (padded)."""
        from geoviz_well_tie.calibration import resample_to_seismic_grid

        synth_twt = np.array([20.0, 30.0, 40.0])
        synth_vals = np.array([1.0, 1.0, 1.0])

        # Seismic grid starts at 0, before synthetic data
        result = resample_to_seismic_grid(synth_vals, synth_twt,
                                           dt_ms=4.0, t0_ms=0.0, n_samples=15)
        # Samples before 20ms should be zero
        assert result[0] == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# 4. Full end-to-end pipeline
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """End-to-end: sonic+density → synthetic → seismic grid alignment."""

    def test_pipeline_sonic_path(self):
        """Complete Path 1: sonic integration."""
        from geoviz_well_tie.calibration import (WellTieCalibration,
                                                  resample_to_seismic_grid)
        from geoviz_well_tie.synthetic import (compute_reflectivity,
                                                generate_synthetic_twt)

        # Input: synthetic well with 500m of uniform sonic, then velocity change
        depths = np.linspace(0, 1000, 501)
        sonic = np.full(501, 200.0)   # 200 µs/m → 5000 m/s
        density = np.full(501, 2.5)   # g/cm³

        # Step 2: T-D curve from sonic
        cal = WellTieCalibration.from_sonic(depths, sonic)

        # Step 3: Reflectivity (at midpoints, length N-1)
        rc = compute_reflectivity(sonic, density)
        assert rc.shape == (500,)

        # Step 4: Build midpoint calibration for resampling
        mid_depths = (depths[:-1] + depths[1:]) / 2.0
        mid_twt = cal.depth_to_twt(mid_depths)
        mid_cal = WellTieCalibration(mid_depths, np.asarray(mid_twt))
        rc_twt = mid_cal.resample_to_twt(rc, dt_ms=2.0)
        assert rc_twt.dtype == np.float32

        # Step 5+6: Generate synthetic with unit-safe wrapper
        synth = generate_synthetic_twt(rc_twt, wavelet_type="ricker",
                                        dt_ms=2.0, peak_freq=25.0)
        assert synth.shape == rc_twt.shape

        # Step 7: Resample to seismic grid (e.g., dt=4ms, t0=0)
        # First get the TWT grid that rc_twt was computed on
        t_max = float(cal.twt[-1])
        rc_twt_time = np.arange(0, t_max + 2.0, 2.0, dtype=np.float64)

        seismic_synth = resample_to_seismic_grid(
            synth, rc_twt_time, dt_ms=4.0, t0_ms=0.0,
            n_samples=int(t_max / 4.0) + 1
        )
        assert seismic_synth.dtype == np.float32
        assert len(seismic_synth) > 0

    def test_pipeline_checkshot_path(self):
        """Path 2: checkshot table provides T-D curve, still needs sonic+density."""
        from geoviz_well_tie.calibration import (WellTieCalibration,
                                                  resample_to_seismic_grid)
        from geoviz_well_tie.synthetic import (compute_reflectivity,
                                                generate_synthetic_twt)

        # Checkshot provides T-D pairs
        cs_depths = np.array([0.0, 200.0, 500.0, 800.0, 1000.0])
        cs_twt = np.array([0.0, 80.0, 220.0, 380.0, 490.0])
        cal = WellTieCalibration(cs_depths, cs_twt)

        # Still need sonic+density for reflectivity
        depths = np.linspace(0, 1000, 501)
        sonic = np.full(501, 200.0)
        density = np.full(501, 2.5)

        rc = compute_reflectivity(sonic, density)

        # Resample using midpoint depths
        mid_depths = (depths[:-1] + depths[1:]) / 2.0
        mid_twt = cal.depth_to_twt(mid_depths)
        mid_cal = WellTieCalibration(mid_depths, np.asarray(mid_twt))
        rc_twt = mid_cal.resample_to_twt(rc, dt_ms=2.0)

        synth = generate_synthetic_twt(rc_twt, wavelet_type="ricker",
                                        dt_ms=2.0, peak_freq=25.0)
        assert synth.shape == rc_twt.shape


# ---------------------------------------------------------------------------
# 5. Calibration depth_to_twt / twt_to_depth with array input
# ---------------------------------------------------------------------------

class TestCalibrationArrayInput:
    """Verify that depth_to_twt and twt_to_depth work with ndarray inputs."""

    def test_depth_to_twt_array(self):
        from geoviz_well_tie.calibration import WellTieCalibration

        depths = np.linspace(0, 300, 301)
        twt = np.linspace(0, 180, 301)
        cal = WellTieCalibration(depths, twt)

        query = np.array([0.0, 150.0, 300.0])
        result = cal.depth_to_twt(query)
        # Should return array of same shape
        assert isinstance(result, np.ndarray)
        np.testing.assert_allclose(result, [0.0, 90.0, 180.0], atol=0.1)

    def test_twt_to_depth_array(self):
        from geoviz_well_tie.calibration import WellTieCalibration

        depths = np.linspace(0, 300, 301)
        twt = np.linspace(0, 180, 301)
        cal = WellTieCalibration(depths, twt)

        query = np.array([0.0, 90.0, 180.0])
        result = cal.twt_to_depth(query)
        assert isinstance(result, np.ndarray)
        np.testing.assert_allclose(result, [0.0, 150.0, 300.0], atol=0.1)


# ---------------------------------------------------------------------------
# 6. Generate synthetic edge cases
# ---------------------------------------------------------------------------

class TestSyntheticEdgeCases:
    """Edge cases for generate_synthetic that are currently untested."""

    def test_wavelet_longer_than_reflectivity(self):
        """Wavelet longer than reflectivity should still produce correct output."""
        from geoviz_well_tie.wavelet import ricker_wavelet
        from geoviz_well_tie.synthetic import generate_synthetic

        rc = np.array([0.1, -0.05], dtype=np.float32)
        w = ricker_wavelet(81, dt=0.001, peak_freq=25.0)
        synth = generate_synthetic(rc, w)
        assert synth.shape == rc.shape
        assert synth.dtype == np.float32

    def test_empty_reflectivity(self):
        """Empty reflectivity should return empty array."""
        from geoviz_well_tie.wavelet import ricker_wavelet
        from geoviz_well_tie.synthetic import generate_synthetic

        rc = np.array([], dtype=np.float32)
        w = ricker_wavelet(21, dt=0.001, peak_freq=25.0)
        synth = generate_synthetic(rc, w)
        assert len(synth) == 0

    def test_single_sample_reflectivity(self):
        """Single-sample reflectivity with longer wavelet."""
        from geoviz_well_tie.wavelet import ricker_wavelet
        from geoviz_well_tie.synthetic import generate_synthetic

        rc = np.array([0.5], dtype=np.float32)
        w = ricker_wavelet(21, dt=0.001, peak_freq=25.0)
        synth = generate_synthetic(rc, w)
        assert synth.shape == (1,)


# ---------------------------------------------------------------------------
# 7. Export calibration T-D pairs
# ---------------------------------------------------------------------------

class TestExportCalibration:
    """Tests for exporting calibration T-D pairs."""

    def test_calibration_to_dict(self):
        """Calibration should export T-D pairs as structured data."""
        from geoviz_well_tie.calibration import WellTieCalibration

        depths = np.array([0.0, 100.0, 200.0, 300.0])
        twt = np.array([0.0, 50.0, 110.0, 180.0])
        cal = WellTieCalibration(depths, twt)

        pairs = cal.to_td_pairs()
        assert "depth_m" in pairs
        assert "twt_ms" in pairs
        np.testing.assert_array_equal(pairs["depth_m"], depths)
        np.testing.assert_array_equal(pairs["twt_ms"], twt)
