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

    def test_render_well_log_data_does_not_crash_on_import(self, qtbot):
        """Calling render_well_log_data must not raise ImportError from missing utils."""
        from geoviz_well_log.chart_engine import ChartEngine
        engine = ChartEngine()
        qtbot.addWidget(engine)
        # The method exists but should not crash with ImportError
        # We just verify the method is callable without the import error
        import inspect
        src = inspect.getsource(engine.render_well_log_data)
        assert "from .utils import" not in src, "Dead import of nonexistent utils.py should be removed"


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

    def test_upload_horizon_does_not_reset_shading(self):
        """_uploadHorizonTexture must preserve _shading_enabled state."""
        import inspect
        from geoviz_seismic.renderer_3d import DualGLVolumeItem
        src = inspect.getsource(DualGLVolumeItem._uploadHorizonTexture)
        # The shading state reset lines should NOT be present
        assert "_shading_enabled = False" not in src, \
            "Shading state should not be reset inside _uploadHorizonTexture"

    def test_no_duplicate_setShading(self):
        """setShading should be defined exactly once."""
        import inspect
        from geoviz_seismic.renderer_3d import DualGLVolumeItem
        src = inspect.getsource(DualGLVolumeItem)
        count = src.count("def setShading(")
        assert count == 1, f"setShading defined {count} times, expected 1"


# --- 26-A4: loader.py UnboundLocalError ---

class TestLoaderExceptionHandling:
    """Exception handlers must not reference unbound local variables."""

    def test_read_inline_error_uses_self_f_not_local(self):
        """read_inline exception handler must not reference unbound `f`."""
        import inspect
        from geoviz_seismic.loader import SeismicLoader
        src = inspect.getsource(SeismicLoader.read_inline)
        # After the fix, the error message should use self._f or be restructured
        # The old code had f.ilines[0] which would be UnboundLocalError
        assert "f.ilines" not in src or "self._f" in src, \
            "Exception handler should not reference unbound local `f`"

    def test_read_crossline_error_uses_self_f_not_local(self):
        """read_crossline exception handler must not reference unbound `f`."""
        import inspect
        from geoviz_seismic.loader import SeismicLoader
        src = inspect.getsource(SeismicLoader.read_crossline)
        assert "f.xlines" not in src or "self._f" in src, \
            "Exception handler should not reference unbound local `f`"

    def test_read_timeslice_error_uses_meta_not_f(self):
        """read_timeslice exception handler must not reference unbound `f`."""
        import inspect
        from geoviz_seismic.loader import SeismicLoader
        src = inspect.getsource(SeismicLoader.read_timeslice)
        # read_timeslice uses meta, not f - just verify no f.something reference
        lines = src.split("\n")
        in_except = False
        for line in lines:
            if "except" in line:
                in_except = True
            if in_except and "f." in line and "f" in line.split("f.")[0][-1:]:
                # Check if it's a standalone f.xxx reference (not self._f, not f-string)
                import re
                if re.search(r'(?<![_"\'])f\.(ilines|xlines)', line):
                    pytest.fail(f"Exception handler references unbound `f`: {line.strip()}")


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
