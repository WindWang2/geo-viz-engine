"""Tests for WellTiePanel widget and SeismicView integration.

Defines the API contract for:
- WellTiePanel: persistent panel with wavelet controls, auto-tie, export
- SeismicView integration: toolbar toggle, overlay injection
"""
import numpy as np
import pytest

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ---------------------------------------------------------------------------
# WellTiePanel widget
# ---------------------------------------------------------------------------

class TestWellTiePanelInit:

    @pytest.fixture
    def panel(self, qtbot):
        from geoviz_seismic.well_tie_panel import WellTiePanel
        p = WellTiePanel()
        p.resize(300, 600)
        qtbot.addWidget(p)
        return p

    def test_panel_creates(self, panel):
        """WellTiePanel instantiates without error."""
        assert panel is not None

    def test_wavelet_combo_exists(self, panel):
        """Panel has a wavelet type selector."""
        assert hasattr(panel, "_wavelet_combo")

    def test_peak_freq_slider_exists(self, panel):
        """Panel has a peak frequency slider for Ricker."""
        assert hasattr(panel, "_peak_freq_slider")

    def test_auto_tie_button_exists(self, panel):
        """Panel has an auto-tie button."""
        assert hasattr(panel, "_auto_tie_btn")

    def test_export_button_exists(self, panel):
        """Panel has an export calibration button."""
        assert hasattr(panel, "_export_btn")

    def test_correlation_readout_exists(self, panel):
        """Panel has a correlation coefficient readout label."""
        assert hasattr(panel, "_cc_label")


class TestWellTiePanelWaveletControls:

    @pytest.fixture
    def panel(self, qtbot):
        from geoviz_seismic.well_tie_panel import WellTiePanel
        p = WellTiePanel()
        p.resize(300, 600)
        qtbot.addWidget(p)
        return p

    def test_default_wavelet_is_ricker(self, panel):
        """Default wavelet type is Ricker."""
        assert panel._wavelet_combo.currentText() == "Ricker"

    def test_ormsby_shows_extra_sliders(self, panel):
        """Switching to Ormsby shows f1-f4 parameter sliders."""
        panel._wavelet_combo.setCurrentText("Ormsby")
        # Ormsby sliders should be visible
        assert hasattr(panel, "_f1_slider")

    def test_peak_freq_range(self, panel):
        """Peak frequency slider has valid range."""
        slider = panel._peak_freq_slider
        assert slider.minimum() >= 5
        assert slider.maximum() <= 100


class TestWellTiePanelSetCalibration:

    @pytest.fixture
    def panel(self, qtbot):
        from geoviz_seismic.well_tie_panel import WellTiePanel
        p = WellTiePanel()
        p.resize(300, 600)
        qtbot.addWidget(p)
        return p

    def test_set_calibration(self, panel):
        """set_calibration stores the WellTieCalibration."""
        from geoviz_well_tie.calibration import WellTieCalibration

        depths = np.linspace(0, 1000, 501)
        twt = np.linspace(0, 500, 501)
        cal = WellTieCalibration(depths, twt)
        panel.set_calibration(cal)
        assert panel._calibration is cal

    def test_set_well_logs(self, panel):
        """set_well_logs stores sonic and density arrays."""
        depths = np.linspace(0, 1000, 501)
        sonic = np.full(501, 200.0)
        density = np.full(501, 2.5)
        panel.set_well_logs(depths, sonic, density)
        assert panel._sonic is not None
        assert len(panel._sonic) == 501


class TestWellTiePanelGenerateSynthetic:

    @pytest.fixture
    def panel_with_data(self, qtbot):
        from geoviz_seismic.well_tie_panel import WellTiePanel
        from geoviz_well_tie.calibration import WellTieCalibration

        p = WellTiePanel()
        p.resize(300, 600)
        qtbot.addWidget(p)

        depths = np.linspace(0, 1000, 501)
        sonic = np.full(501, 200.0)
        sonic[250:] = 150.0
        density = np.full(501, 2.5)
        cal = WellTieCalibration.from_sonic(depths, sonic)
        p.set_calibration(cal)
        p.set_well_logs(depths, sonic, density)
        return p

    def test_generate_synthetic(self, panel_with_data):
        """generate_synthetic produces a non-empty synthetic trace."""
        panel_with_data.generate_synthetic(dt_ms=4.0)
        assert panel_with_data._synthetic is not None
        assert len(panel_with_data._synthetic) > 0

    def test_synthetic_updated_on_freq_change(self, panel_with_data):
        """Changing peak frequency regenerates synthetic."""
        panel_with_data.generate_synthetic(dt_ms=4.0)
        synth1 = panel_with_data._synthetic.copy()

        panel_with_data._peak_freq_slider.setValue(40)
        panel_with_data.generate_synthetic(dt_ms=4.0)
        synth2 = panel_with_data._synthetic

        # Different frequency should produce different synthetic
        assert not np.allclose(synth1, synth2, atol=0.01)


class TestWellTiePanelAutoTie:

    @pytest.fixture
    def panel_with_data(self, qtbot):
        from geoviz_seismic.well_tie_panel import WellTiePanel
        from geoviz_well_tie.calibration import WellTieCalibration

        p = WellTiePanel()
        p.resize(300, 600)
        qtbot.addWidget(p)

        depths = np.linspace(0, 1000, 501)
        sonic = np.full(501, 200.0)
        density = np.full(501, 2.5)
        cal = WellTieCalibration.from_sonic(depths, sonic)
        p.set_calibration(cal)
        p.set_well_logs(depths, sonic, density)
        return p

    def test_auto_tie_with_seismic_trace(self, panel_with_data):
        """Auto-tie computes shift and updates CC readout."""
        panel_with_data.generate_synthetic(dt_ms=4.0)
        # Provide a fake seismic trace
        seismic = np.random.default_rng(42).standard_normal(
            len(panel_with_data._synthetic), dtype=np.float32
        )
        panel_with_data.auto_tie(seismic)
        assert panel_with_data._shift_samples is not None
        assert panel_with_data._correlation_coeff is not None


# ---------------------------------------------------------------------------
# SeismicView integration
# ---------------------------------------------------------------------------

class TestSeismicViewWellTieIntegration:

    @pytest.fixture
    def view(self, qtbot):
        from geoviz_seismic.seismic_view import SeismicView

        sv = SeismicView()
        sv.resize(1200, 800)
        # Load demo data so profiles have content
        rng = np.random.default_rng(42)
        demo_data = rng.standard_normal((30, 40, 50), dtype=np.float32)
        sv.load_demo(demo_data)
        qtbot.addWidget(sv)
        return sv

    def test_well_tie_button_in_toolbar(self, view):
        """SeismicView toolbar has a well-tie toggle button."""
        assert hasattr(view, "_well_tie_btn")

    def test_well_tie_panel_toggle(self, view):
        """Clicking well-tie button toggles WellTiePanel visibility."""
        # Initially no panel
        assert view._well_tie_panel is None or not view._well_tie_panel.isVisible()
        # Toggle on
        view._well_tie_btn.setChecked(True)
        assert view._well_tie_panel is not None

    def test_well_tie_panel_is_persistent(self, view):
        """WellTiePanel persists (not recreated) on toggle."""
        view._well_tie_btn.setChecked(True)
        panel1 = view._well_tie_panel
        view._well_tie_btn.setChecked(False)
        view._well_tie_btn.setChecked(True)
        panel2 = view._well_tie_panel
        assert panel1 is panel2  # same object, not recreated

    def test_current_seismic_trace_from_demo_volume(self, view):
        """current_seismic_trace returns 1-D samples at current IL/XL."""
        trace = view.current_seismic_trace()
        assert trace is not None
        assert trace.ndim == 1
        assert len(trace) == 50  # demo volume shape (30, 40, 50)

    def test_auto_tie_signal_runs_against_current_trace(self, view):
        """auto_tie_requested is connected: panel.auto_tie gets live seismic."""
        view._well_tie_btn.setChecked(True)
        panel = view._well_tie_panel
        assert panel is not None
        assert panel._calibration is not None  # demo logs seeded
        panel.generate_synthetic(dt_ms=4.0)
        assert panel._synthetic is not None

        panel.auto_tie_requested.emit()
        assert panel._shift_samples is not None
        assert panel._correlation_coeff is not None
        assert "CC:" in panel._cc_label.text()
        assert "Shift:" in panel._shift_label.text()

    def test_synthetic_changed_sets_profile_overlay(self, view):
        """Generating synthetic injects wiggle overlay on IL/XL panels."""
        view._well_tie_btn.setChecked(True)
        panel = view._well_tie_panel
        panel.generate_synthetic(dt_ms=4.0)
        assert view._profile_il._vd._synthetic_overlay is not None
        assert view._profile_xl._vd._synthetic_overlay is not None
        ov = view._profile_il._vd._synthetic_overlay
        assert len(ov["values"]) == len(panel._synthetic)
