"""TDD tests for Phase 23 bugfixes:
- 23-B1: Crosshair overlay visible on header area
- 23-B2: Vertical scrollbar controls depth range (like Ctrl+drag panning)
- 23-B3: Last track fully visible (no clipping)
- Bonus: Curve legend shows min/max values
"""
import pytest
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.overlay import CrosshairOverlay
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.models import CurveData
import numpy as np

from src.pages.well_log.qpainter_widget import QPainterWidget


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _make_curve_track(name="GR", n=200):
    """Create a test CurveTrack with synthetic data."""
    depths = np.linspace(1000, 2000, n)
    values = np.sin(np.linspace(0, 6, n)) * 50 + 100
    curve = CurveData(name=name, unit="API", color="#22c55e",
                      depth=depths.tolist(), values=values.tolist())
    return CurveTrack([curve], label=name, width=150)


class TestCrosshairOnHeader:
    """23-B1: Crosshair overlay should be visible when cursor is over track header."""

    def test_canvas_has_crosshair_reference(self, app):
        """QPainterWidget should wire crosshair to canvas."""
        w = QPainterWidget()
        w.resize(600, 800)
        assert w._crosshair is not None
        assert w.canvas.crosshair is w._crosshair

    def test_crosshair_visible_at_header_y(self, app):
        """set_cursor_y at header region should make crosshair visible."""
        w = QPainterWidget()
        w.resize(600, 800)
        track = _make_curve_track()
        w.set_tracks([track])

        overlay = w._crosshair
        header_h = track.header_height
        overlay.set_cursor_y(header_h / 2)
        assert overlay.visible

    def test_depth_at_y_accounts_for_header(self, app):
        """depth_at_y should return depth_top when cursor is at header."""
        w = QPainterWidget()
        w.resize(600, 800)
        track = _make_curve_track()
        w.set_tracks([track])

        overlay = w._crosshair
        header_h = track.header_height
        # At top of header, depth should be depth_top
        depth = overlay.depth_at_y(header_h)
        assert abs(depth - track.depth_top) < 1.0

    def test_crosshair_paints_on_canvas(self, app):
        """Crosshair should paint directly on canvas (no separate overlay widget)."""
        from geoviz_well_log.renderer.canvas import WellLogCanvas
        from geoviz_well_log.renderer.overlay import CrosshairOverlay
        canvas = WellLogCanvas()
        overlay = CrosshairOverlay(canvas)
        canvas.crosshair = overlay
        overlay.set_cursor_y(100)
        # Verify crosshair is set and canvas references it
        assert canvas.crosshair is overlay
        assert canvas.crosshair.visible


class TestVerticalScrollbar:
    """23-B2: Vertical scrollbar controls depth range (like Ctrl+drag panning)."""

    def test_scrollbar_policy_is_always_on(self, app):
        """Vertical scrollbar policy should be ScrollBarAlwaysOn."""
        w = QPainterWidget()
        policy = w.verticalScrollBarPolicy()
        assert policy == Qt.ScrollBarPolicy.ScrollBarAlwaysOn

    def test_scrollbar_visible_when_shown(self, app):
        """Vertical scrollbar should be visible when widget is shown with tracks."""
        w = QPainterWidget()
        w.resize(600, 800)
        track = _make_curve_track()
        w.set_tracks([track])
        w.show()
        sb = w.verticalScrollBar()
        assert sb.isVisible()

    def test_scrollbar_controls_depth_range(self, app):
        """Moving scrollbar should change the visible depth range."""
        w = QPainterWidget()
        w.resize(600, 800)
        track = _make_curve_track()
        track.set_depth_range(1000.0, 2000.0)
        w.set_tracks([track])
        w.show()

        # Zoom so the thumb no longer fills the track, then drive the bar.
        w.set_depth_range(1200.0, 1400.0)
        assert track.depth_top == pytest.approx(1200.0)
        assert track.depth_bottom == pytest.approx(1400.0)

        sb = w.verticalScrollBar()
        sb.setValue(sb.maximum())
        assert track.depth_top == pytest.approx(1800.0)
        assert track.depth_bottom == pytest.approx(2000.0)

        sb.setValue(0)
        assert track.depth_top == pytest.approx(1000.0)
        assert track.depth_bottom == pytest.approx(1200.0)

    def test_scrollbar_range_configured(self, app):
        """Scrollbar max/pageStep must track visible vs full depth span."""
        w = QPainterWidget()
        w.resize(600, 800)
        track = _make_curve_track()
        track.set_depth_range(1000.0, 2000.0)
        w.set_tracks([track])

        sb = w.verticalScrollBar()
        full_span = track.depth_bottom - track.depth_top
        assert full_span == pytest.approx(1000.0)
        # Full view: thumb fills the track (max=0) but pageStep stays positive.
        assert sb.maximum() == 0
        assert sb.pageStep() > 0

        w.set_depth_range(1200.0, 1400.0)
        visible_span = track.depth_bottom - track.depth_top
        assert visible_span == pytest.approx(200.0)
        assert sb.maximum() == 100000
        assert sb.pageStep() == int((visible_span / full_span) * 100000)
        assert 0 < sb.pageStep() < sb.maximum()

    def test_scrollbar_thumb_shrinks_on_zoom(self, app):
        """Zooming in should shrink the scrollbar thumb proportionally."""
        w = QPainterWidget()
        w.resize(600, 800)
        track = _make_curve_track()
        w.set_tracks([track])

        full_page_step = w.verticalScrollBar().pageStep()

        # Zoom in to half the depth range
        mid = (track.depth_top + track.depth_bottom) / 2
        half_span = track.depth_span / 4
        w.set_depth_range(mid - half_span, mid + half_span)

        zoomed_page_step = w.verticalScrollBar().pageStep()
        assert zoomed_page_step < full_page_step


class TestLastTrackVisible:
    """23-B3: Last track should be fully visible, not clipped."""

    def test_canvas_fills_viewport(self, app):
        """Canvas should fill the viewport (no physical scrolling)."""
        w = QPainterWidget()
        w.resize(600, 800)
        track = _make_curve_track()
        w.set_tracks([track])

        # Canvas width should not exceed viewport
        viewport_w = w.viewport().width()
        canvas_w = w.canvas.width()
        assert canvas_w <= viewport_w

    def test_all_tracks_fit_within_viewport(self, app):
        """Total track width should fit within the viewport."""
        w = QPainterWidget()
        w.resize(600, 800)
        tracks = [_make_curve_track(f"T{i}") for i in range(5)]
        for t in tracks:
            t.set_width(120)
        w.set_tracks(tracks)

        total_track_w = sum(t.width for t in tracks)
        viewport_w = w.viewport().width()
        assert total_track_w <= viewport_w + 10


class TestCurveLegendMinMax:
    """Curve legend should show min/max values."""

    def test_paint_header_includes_range(self, app, monkeypatch):
        """CurveTrack header should render min/max range text."""
        track = _make_curve_track("GR", 100)
        curve = track.curves[0]
        range_str = track._range_str_for(curve)
        assert "~" in range_str

        drawn: list[str] = []
        orig = QPainter.drawText

        def _capture(self, *args, **kwargs):
            for arg in args:
                if isinstance(arg, str):
                    drawn.append(arg)
            return orig(self, *args, **kwargs)

        monkeypatch.setattr(QPainter, "drawText", _capture)

        img = QImage(160, 80, QImage.Format.Format_ARGB32)
        img.fill(0xFFFFFFFF)
        painter = QPainter(img)
        track.paint_header(painter, QRectF(0, 0, 160, 80))
        painter.end()

        joined = " ".join(drawn)
        assert "GR" in joined
        assert "~" in joined
        assert any(range_str in text or "~" in text for text in drawn)
        from PySide6.QtGui import QColor
        white = QColor("#ffffff")
        assert any(
            img.pixelColor(x, y) != white
            for y in range(0, img.height(), 4)
            for x in range(0, img.width(), 4)
        )
