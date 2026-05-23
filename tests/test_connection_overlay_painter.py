import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QImage

from geoviz_well_log.connection_overlay import ConnectionOverlay
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from src.data.models import CorrelationLink


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _make_canvas(well_name: str, top: float, bottom: float) -> WellLogCanvas:
    canvas = WellLogCanvas()
    canvas.resize(200, 600)
    track = DepthTrack(top_depth=top, bottom_depth=bottom, width=60, label="深度")
    canvas.set_tracks([track])
    return canvas


def test_connection_overlay_creation(app):
    overlay = ConnectionOverlay()
    assert overlay._canvases == []
    assert overlay._links == []


def test_connection_overlay_set_canvases(app):
    overlay = ConnectionOverlay()
    c1 = _make_canvas("well1", 0, 100)
    c2 = _make_canvas("well2", 0, 100)
    overlay.set_canvases([c1, c2])
    assert len(overlay._canvases) == 2


def test_connection_overlay_depth_to_y(app):
    overlay = ConnectionOverlay()
    c1 = _make_canvas("well1", 0, 100)
    overlay.set_canvases([c1])
    y = overlay.depth_to_y(c1, 50.0)
    assert isinstance(y, float)
    assert y > 0


def test_connection_overlay_paint_no_crash(app):
    overlay = ConnectionOverlay()
    c1 = _make_canvas("well1", 0, 100)
    c2 = _make_canvas("well2", 0, 100)
    overlay.set_canvases([c1, c2])
    link = CorrelationLink(
        source_well="well1", target_well="well2",
        source_interval_id="10_50_FormationA",
        target_interval_id="15_55_FormationA",
        color="#f59e0b",
    )
    overlay.set_links([link])
    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    overlay.paint_event(painter, QRectF(img.rect()))
    painter.end()


def test_connection_overlay_empty_links_no_crash(app):
    overlay = ConnectionOverlay()
    c1 = _make_canvas("well1", 0, 100)
    overlay.set_canvases([c1])
    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    overlay.paint_event(painter, QRectF(img.rect()))
    painter.end()
