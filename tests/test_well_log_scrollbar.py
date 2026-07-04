from PySide6.QtWidgets import QApplication

from geoviz_well_log import DepthTrack
from src.pages.well_log.qpainter_widget import QPainterWidget


def test_vertical_scrollbar_maps_to_current_depth_window():
    QApplication.instance() or QApplication([])
    widget = QPainterWidget()
    track = DepthTrack(2500.0, 2600.0)
    widget.set_tracks([track])
    widget.set_depth_range(2520.0, 2540.0)

    sb = widget.verticalScrollBar()
    sb.setValue(sb.maximum())

    assert track.depth_top == 2580.0
    assert track.depth_bottom == 2600.0


def test_vertical_scrollbar_does_not_physically_scroll_canvas():
    QApplication.instance() or QApplication([])
    widget = QPainterWidget()
    track = DepthTrack(2500.0, 2600.0)
    widget.set_tracks([track])
    widget.set_depth_range(2520.0, 2540.0)

    widget.verticalScrollBar().setValue(widget.verticalScrollBar().maximum())

    assert widget.canvas.pos().y() == 0
