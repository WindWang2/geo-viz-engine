import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter

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


def test_depth_ruler_paint_no_crash(app, monkeypatch):
    ruler = DepthRuler()
    ruler.set_depth_range(0, 1000)
    ruler.set_cursor_depth(500.0)
    ruler.resize(50, 600)

    drawn: list[str] = []
    orig = QPainter.drawText

    def _capture(self, *args, **kwargs):
        for arg in args:
            if isinstance(arg, str):
                drawn.append(arg)
        return orig(self, *args, **kwargs)

    monkeypatch.setattr(QPainter, "drawText", _capture)

    img = QImage(50, 600, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    ruler.render(img)

    joined = " ".join(drawn)
    assert any(label in joined for label in ("0", "500", "1000"))
    assert any("500" in text for text in drawn)
    from PySide6.QtGui import QColor
    bg = QColor("#f8fafc")
    assert any(
        img.pixelColor(x, y) != bg and img.pixelColor(x, y).alpha() > 0
        for y in range(0, img.height(), 8)
        for x in range(0, img.width(), 4)
    )


def test_depth_ruler_cursor_indicator(app):
    ruler = DepthRuler()
    ruler.resize(50, 600)
    ruler.set_depth_range(0, 1000)
    ruler.set_cursor_depth(500.0)
    # depth 500 in range 0-1000 => 50% from top
    y = ruler._depth_to_y(500.0)
    assert y == pytest.approx(300.0, abs=1.0)  # 600px viewport * 0.5
