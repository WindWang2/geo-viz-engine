import pytest
from PySide6.QtWidgets import QApplication

from geoviz_well_log.cross_well_widget import CrossWellWidget
from geoviz_well_log.renderer.canvas import WellLogCanvas


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_cross_well_widget_creation(app):
    widget = CrossWellWidget()
    assert widget.canvas_count == 0
    assert widget._canvases == []


def test_cross_well_widget_add_well(app):
    widget = CrossWellWidget()
    canvas = WellLogCanvas()
    widget.add_canvas(canvas, "well1")
    assert widget.canvas_count == 1
    assert widget._canvases[0] is canvas


def test_cross_well_widget_remove_well(app):
    widget = CrossWellWidget()
    c1 = WellLogCanvas()
    c2 = WellLogCanvas()
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.remove_canvas(c1)
    assert widget.canvas_count == 1


def test_cross_well_widget_clear_all(app):
    widget = CrossWellWidget()
    widget.add_canvas(WellLogCanvas(), "well1")
    widget.add_canvas(WellLogCanvas(), "well2")
    widget.clear_all()
    assert widget.canvas_count == 0
