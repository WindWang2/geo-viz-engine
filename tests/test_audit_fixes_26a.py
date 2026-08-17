"""Phase 26-A: Regression tests for critical bugs found in deep audit.

26-A1: chart_engine.render_well_log_data imports nonexistent utils.py
26-A2: ConnectionOverlay._well_names not initialized in __init__
26-A3: renderer_3d._uploadHorizonTexture resets shading state
26-A4: loader.py UnboundLocalError in exception handler
26-A5: WellTiePanel auto-tie button not wired
26-A6: cross_well page self.canvas AttributeError on Escape
26-A7: main.py time.sleep blocks splash animation
"""
import pytest
import numpy as np


# --- 26-A1: chart_engine dead import ---

class TestChartEngineDeadImport:
    """render_well_log_data() should not crash on import."""

    def test_render_well_log_data_does_not_crash_on_import(self):
        """Calling render_well_log_data must not raise ImportError from missing utils."""
        from geoviz_well_log.chart_engine import ChartEngine
        from geoviz_well_log.models import CurveData, WellLogData

        data = WellLogData(
            well_name="T",
            top_depth=0.0,
            bottom_depth=10.0,
            curves=[CurveData(name="GR", depth=[0.0, 10.0], values=[1.0, 2.0])],
        )

        class _Sink:
            def __init__(self):
                self.payload = None

            def render_data(self, well_data_json: str):
                self.payload = well_data_json

        sink = _Sink()
        ChartEngine.render_well_log_data(sink, data)
        assert sink.payload
        import json
        parsed = json.loads(sink.payload)
        assert parsed


# --- 26-A2: ConnectionOverlay._well_names ---

class TestConnectionOverlayInit:
    """ConnectionOverlay should have _well_names initialized in __init__."""

    def test_well_names_attribute_exists_before_set_canvases(self, qtbot):
        """Accessing _well_names before set_canvases() must not raise AttributeError."""
        from geoviz_well_log.connection_overlay import ConnectionOverlay
        overlay = ConnectionOverlay()
        qtbot.addWidget(overlay)
        # This should NOT raise AttributeError
        assert hasattr(overlay, "_well_names")
        assert overlay._well_names == []

    def test_paint_event_before_set_canvases_does_not_crash(self, qtbot):
        """paintEvent before set_canvases() must not crash."""
        from geoviz_well_log.connection_overlay import ConnectionOverlay
        from PySide6.QtGui import QImage, QPainter
        overlay = ConnectionOverlay()
        qtbot.addWidget(overlay)
        overlay.resize(200, 200)
        # Trigger paint without calling set_canvases first
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        overlay.paint_event(p, overlay.rect())
        p.end()


# --- 26-A3: renderer_3d shading state reset ---

class TestShadingStateNotReset:
    """Uploading a horizon texture must NOT reset shading state."""

    def _bare_item(self):
        from geoviz_seismic.renderer_3d import DualGLVolumeItem
        item = DualGLVolumeItem.__new__(DualGLVolumeItem)
        item._shading_enabled = False
        item._shading_light_dir = (1.0, 1.0, 1.0)
        item._shading_needs_upload = False
        item._sculpt_horizon_data = None
        item._sculpt_horizon_tex = None
        item._sculpt_needs_upload = False
        item.smooth = False
        item.update = lambda *a, **k: None
        return item

    def test_upload_horizon_does_not_reset_shading(self):
        """_uploadHorizonTexture must preserve _shading_enabled state."""
        from unittest.mock import MagicMock, patch

        from geoviz_seismic.renderer_3d import DualGLVolumeItem

        item = self._bare_item()
        DualGLVolumeItem.setShading(item, True, (0.0, 1.0, 0.0))
        assert item._shading_enabled is True
        item._sculpt_horizon_data = np.ones((2, 2), dtype=np.float32)
        item._sculpt_horizon_tex = 7
        item._sculpt_needs_upload = True
        with (
            patch("geoviz_seismic.renderer_3d.QtGui.QOpenGLContext") as ctx_cls,
            patch("geoviz_seismic.renderer_3d.GL"),
        ):
            ctx_cls.currentContext.return_value = MagicMock()
            DualGLVolumeItem._uploadHorizonTexture(item)
        assert item._shading_enabled is True
        assert item._shading_light_dir == (0.0, 1.0, 0.0)
        assert item._sculpt_needs_upload is False

    def test_no_duplicate_setShading(self):
        """setShading should be defined exactly once and toggle public state."""
        from geoviz_seismic.renderer_3d import DualGLVolumeItem

        defs = [
            cls for cls in DualGLVolumeItem.__mro__
            if "setShading" in getattr(cls, "__dict__", {})
        ]
        assert len(defs) == 1, f"setShading defined on {defs}"

        item = self._bare_item()
        DualGLVolumeItem.setShading(item, True, (0.2, 0.3, 0.4))
        assert item._shading_enabled is True
        assert item._shading_light_dir == (0.2, 0.3, 0.4)
        DualGLVolumeItem.setShading(item, False)
        assert item._shading_enabled is False


# --- 26-A4: loader.py UnboundLocalError ---

class TestLoaderExceptionHandling:
    """Exception handlers must not reference unbound local variables."""

    def _failing_loader(self):
        from types import SimpleNamespace

        from geoviz_seismic.loader import SeismicLoader
        from geoviz_seismic.models import SeismicVolumeMeta

        loader = SeismicLoader("missing.sgy")
        loader._f = SimpleNamespace(
            ilines=[10, 11, 12], xlines=[20, 21], close=lambda: None
        )
        loader._meta = SeismicVolumeMeta(
            filename="missing.sgy",
            n_inlines=3,
            n_crosslines=2,
            n_samples=8,
            sample_interval=4.0,
            iline_start=10,
            iline_step=1,
            xline_start=20,
            xline_step=1,
            dt_ms=4.0,
        )

        def _boom():
            raise KeyError("forced")

        loader._open = _boom
        return loader

    def test_read_inline_error_uses_self_f_not_local(self):
        """read_inline exception handler must not reference unbound `f`."""
        loader = self._failing_loader()
        with pytest.raises(ValueError, match=r"available: 10-12") as info:
            loader.read_inline(999)
        assert not isinstance(info.value.__cause__, UnboundLocalError)

    def test_read_crossline_error_uses_self_f_not_local(self):
        """read_crossline exception handler must not reference unbound `f`."""
        loader = self._failing_loader()
        with pytest.raises(ValueError, match=r"available: 20-21") as info:
            loader.read_crossline(999)
        assert not isinstance(info.value.__cause__, UnboundLocalError)

    def test_read_timeslice_error_uses_meta_not_f(self):
        """read_timeslice exception handler must not reference unbound `f`."""
        loader = self._failing_loader()
        with pytest.raises(ValueError, match=r"available: 0-7") as info:
            loader.read_timeslice(99)
        assert not isinstance(info.value.__cause__, UnboundLocalError)


# --- 26-A5: WellTiePanel auto-tie button wiring ---

class TestAutoTieButtonWired:
    """Auto-Tie button must be connected to a slot."""

    def test_auto_tie_button_is_connected(self, qtbot):
        """_auto_tie_btn.clicked must have at least one connection."""
        from geoviz_seismic.well_tie_panel import WellTiePanel
        panel = WellTiePanel()
        qtbot.addWidget(panel)
        # Check that the button has connections via string-based signal
        receivers = panel._auto_tie_btn.receivers("2clicked()")  # PySide6 string format
        assert receivers > 0, "Auto-Tie button has no connected slots"


# --- 26-A6: cross_well page Escape key ---

class TestCrossWellEscapeKey:
    """Escape key in pick mode must not crash with AttributeError."""

    def test_escape_exits_pick_mode_without_crash(self, qtbot):
        """Pressing Escape in pick mode must set pick_mode=False without AttributeError."""
        from src.pages.cross_well.page import CrossWellPage
        page = CrossWellPage()
        qtbot.addWidget(page)
        # Enable pick mode
        page._canvas.pick_mode = True
        page._pick_btn.setChecked(True)
        # Simulate Escape key - should NOT raise AttributeError
        from PySide6.QtCore import Qt, QEvent
        from PySide6.QtGui import QKeyEvent
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        page.keyPressEvent(event)
        assert page._canvas.pick_mode is False


# --- 26-A7: main.py time.sleep ---

class TestMainNoSleep:
    """main.py should not call time.sleep."""

    def test_no_time_sleep_in_main(self):
        """main.py must not contain time.sleep calls."""
        import inspect
        import src.main as main_module
        src = inspect.getsource(main_module)
        # Allow time.sleep in comments but not in actual code
        lines = src.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "time.sleep" not in stripped, \
                f"main.py should not call time.sleep: {stripped}"
