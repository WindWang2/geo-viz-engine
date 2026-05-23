import pytest
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF, Qt

from geoviz_well_log.renderer.depth_ruler import DepthRuler


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_depth_ruler_creation(app):
    ruler = DepthRuler()
    assert ruler is not None
    assert ruler.width() == 50


def test_depth_ruler_nice_intervals(app):
    ruler = DepthRuler()
    # Full range 0-3000m in 600px viewport => 5m/px
    # Target spacing 60px => 300m interval => rounds to 500
    intervals = ruler._compute_nice_intervals(0, 3000, 600)
    assert intervals == 500

    # Zoomed range 1000-1100m in 600px viewport => 0.167m/px
    # Target spacing 60px => 10m interval
    intervals = ruler._compute_nice_intervals(1000, 1100, 600)
    assert intervals == 10


def test_depth_ruler_paint_no_crash(app):
    ruler = DepthRuler()
    ruler.set_depth_range(0, 1000)
    ruler.set_cursor_depth(500.0)
    ruler.resize(50, 600)
    pm = QPixmap(50, 600)
    painter = QPainter(pm)
    ruler.paintEvent(None)  # paint directly
    painter.end()


def test_depth_ruler_cursor_indicator(app):
    ruler = DepthRuler()
    ruler.resize(50, 600)
    ruler.set_depth_range(0, 1000)
    ruler.set_cursor_depth(500.0)
    # depth 500 in range 0-1000 => 50% from top
    y = ruler._depth_to_y(500.0)
    assert y == pytest.approx(300.0, abs=1.0)  # 600px viewport * 0.5
