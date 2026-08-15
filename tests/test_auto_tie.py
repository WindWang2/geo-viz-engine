"""Tests for auto-tie cross-correlation and synthetic overlay API.

Auto-tie: numpy.correlate-based bulk time shift estimation.
Overlay: ProfileVD synthetic wiggle overlay rendering API.
"""
import numpy as np
import pytest

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ---------------------------------------------------------------------------
# Auto-tie cross-correlation
# ---------------------------------------------------------------------------

class TestAutoTie:
    """Tests for auto_tie bulk time-shift estimation."""

    def test_auto_tie_zero_shift(self):
        """Perfectly aligned synthetic returns shift ≈ 0."""
        from geoviz_well_tie.auto_tie import auto_tie

        rng = np.random.default_rng(42)
        trace = rng.standard_normal(200, dtype=np.float32)
        # Synthetic is identical — zero shift
        shift_samples = auto_tie(trace, trace)
        assert shift_samples == pytest.approx(0, abs=2)

    def test_auto_tie_known_shift(self):
        """Known shift is correctly detected."""
        from geoviz_well_tie.auto_tie import auto_tie

        n = 200
        rng = np.random.default_rng(42)
        trace = rng.standard_normal(n, dtype=np.float32)
        shift = 5
        # Delay the synthetic by 5 samples (synthetic is late / down)
        synth = np.zeros(n, dtype=np.float32)
        synth[shift:] = trace[:-shift]

        detected = auto_tie(trace, synth)
        # #72 sign convention: positive shift means the synthetic should move
        # DOWN to line up with the field trace. A late synthetic therefore
        # needs a negative shift (move it up by the same amount).
        assert detected == pytest.approx(-shift, abs=1)

    def test_auto_tie_correlation_coefficient(self):
        """Returns correlation coefficient for quality assessment."""
        from geoviz_well_tie.auto_tie import auto_tie_with_quality

        rng = np.random.default_rng(42)
        trace = rng.standard_normal(200, dtype=np.float32)
        shift, cc = auto_tie_with_quality(trace, trace)
        # Perfect match → correlation near 1.0
        assert cc == pytest.approx(1.0, abs=0.01)

    def test_auto_tie_noisy_correlation(self):
        """Low correlation with noise should still produce a result."""
        from geoviz_well_tie.auto_tie import auto_tie_with_quality

        rng = np.random.default_rng(42)
        trace = rng.standard_normal(200, dtype=np.float32)
        noise = rng.standard_normal(200, dtype=np.float32)

        shift, cc = auto_tie_with_quality(trace, noise)
        assert isinstance(shift, (int, float, np.integer, np.floating))
        assert isinstance(cc, float)
        assert 0.0 <= abs(cc) <= 1.0

    def test_auto_tie_different_lengths(self):
        """Traces of different lengths are handled by truncating to shorter."""
        from geoviz_well_tie.auto_tie import auto_tie

        rng = np.random.default_rng(42)
        trace_a = rng.standard_normal(200, dtype=np.float32)
        trace_b = rng.standard_normal(150, dtype=np.float32)
        # Should not raise
        shift = auto_tie(trace_a, trace_b)
        assert isinstance(shift, (int, float, np.integer, np.floating))


# ---------------------------------------------------------------------------
# Synthetic overlay API on ProfileVD
# ---------------------------------------------------------------------------

class TestSyntheticOverlayAPI:
    """Tests for ProfileVD.set_synthetic_overlay() and related methods."""

    @pytest.fixture
    def profile(self, qtbot):
        """Create a ProfileVD with rendered data."""
        from geoviz_seismic.profile_vd import ProfileVD
        from geoviz_seismic.models import SliceInfo

        vd = ProfileVD()
        vd.resize(600, 400)
        data = np.random.default_rng(42).standard_normal(
            (100, 50), dtype=np.float32
        )
        si = SliceInfo(
            slice_type="inline",
            position=1050,
            axis_h_label="Crossline",
            axis_v_label="TWT (ms)",
            axis_h_values=[float(v) for v in range(2000, 2050)],
            axis_v_values=[float(v) for v in range(0, 400, 4)],
        )
        vd.render(data, "seismic", si)
        qtbot.addWidget(vd)
        return vd

    def test_set_synthetic_overlay(self, profile):
        """set_synthetic_overlay stores overlay data without error."""
        twt = np.linspace(0, 200, 51)
        values = np.sin(twt / 20.0).astype(np.float32)
        profile.set_synthetic_overlay(
            h_position=2025.0,
            twt=twt,
            values=values,
            label="Well-A",
            color="#ff0000",
        )
        assert profile._synthetic_overlay is not None
        assert profile._synthetic_overlay["label"] == "Well-A"

    def test_clear_synthetic_overlay(self, profile):
        """clear_synthetic_overlay removes stored overlay."""
        twt = np.linspace(0, 200, 51)
        values = np.sin(twt / 20.0).astype(np.float32)
        profile.set_synthetic_overlay(
            h_position=2025.0, twt=twt, values=values, label="Well-A"
        )
        profile.clear_synthetic_overlay()
        assert profile._synthetic_overlay is None

    def test_overlay_within_viewport(self, profile):
        """Overlay at valid h_position renders without error."""
        twt = np.linspace(0, 300, 76)
        values = np.random.default_rng(42).standard_normal(76).astype(np.float32)
        profile.set_synthetic_overlay(
            h_position=2025.0, twt=twt, values=values, label="Well-B"
        )
        # Trigger paint
        profile.grab()
        # No assertion needed — just verify no crash

    def test_overlay_outside_viewport_no_crash(self, profile):
        """Overlay outside viewport range does not crash."""
        twt = np.linspace(0, 200, 51)
        values = np.sin(twt / 20.0).astype(np.float32)
        # h_position way outside the data range
        profile.set_synthetic_overlay(
            h_position=9999.0, twt=twt, values=values, label="Far-Well"
        )
        profile.grab()  # should not crash

    def test_overlay_zoom_still_renders(self, profile):
        """Overlay still renders after zoom change."""
        twt = np.linspace(0, 200, 51)
        values = np.sin(twt / 20.0).astype(np.float32)
        profile.set_synthetic_overlay(
            h_position=2025.0, twt=twt, values=values, label="Well-A"
        )
        # Simulate zoom by modifying viewport
        profile._view_h = (0.2, 0.6)
        profile._view_v = (0.1, 0.5)
        profile._renormalize()
        profile.grab()  # should not crash


# ---------------------------------------------------------------------------
# ProfileWidget mode switching
# ---------------------------------------------------------------------------

class TestProfileWidgetSwitching:
    """Tests for ProfileWidget VD/Wiggle mode switching."""

    @pytest.fixture
    def widget(self, qtbot):
        from geoviz_seismic.profile_widget import ProfileWidget
        from geoviz_seismic.models import SliceInfo

        pw = ProfileWidget()
        pw.resize(600, 400)
        data = np.random.default_rng(42).standard_normal(
            (100, 50), dtype=np.float32
        )
        si = SliceInfo(
            slice_type="inline",
            position=1050,
            axis_h_label="Crossline",
            axis_v_label="TWT (ms)",
            axis_h_values=[float(v) for v in range(50)],
            axis_v_values=[float(v) for v in range(0, 400, 4)],
        )
        pw.update_profile(data, si, "seismic")
        qtbot.addWidget(pw)
        return pw

    def test_default_mode_is_vd(self, widget):
        """Default display mode is variable-density."""
        assert widget._mode == "vd"

    def test_switch_to_wiggle(self, widget):
        """Switching to wiggle mode changes internal state."""
        widget.set_display_mode("wiggle")
        assert widget._mode == "wiggle"

    def test_switch_back_to_vd(self, widget):
        """Switching back to VD restores state."""
        widget.set_display_mode("wiggle")
        widget.set_display_mode("vd")
        assert widget._mode == "vd"

    def test_same_mode_noop(self, widget):
        """Setting same mode is a no-op."""
        widget.set_display_mode("vd")
        assert widget._mode == "vd"
