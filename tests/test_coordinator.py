from geoviz_well_log.renderer.coordinator import LayoutCoordinator
from geoviz_well_log.renderer.track_base import BaseTrack
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF


class StubTrack(BaseTrack):
    def __init__(self, label="stub", width=100):
        super().__init__(label=label, width=width)
        self.synced_range = None

    def paint_content(self, painter, rect):
        pass

    def set_depth_range(self, top, bottom):
        self.synced_range = (top, bottom)
        super().set_depth_range(top, bottom)


def test_coordinator_broadcasts_range(qtbot):
    t1 = StubTrack()
    t2 = StubTrack()
    qtbot.addWidget(t1)
    qtbot.addWidget(t2)
    coord = LayoutCoordinator(tracks=[t1, t2])
    coord.set_depth_range(100.0, 500.0)
    assert t1.synced_range == (100.0, 500.0)
    assert t2.synced_range == (100.0, 500.0)


def test_coordinator_total_width(qtbot):
    t1 = StubTrack(width=60)
    t2 = StubTrack(width=150)
    t3 = StubTrack(width=100)
    qtbot.addWidget(t1)
    qtbot.addWidget(t2)
    qtbot.addWidget(t3)
    coord = LayoutCoordinator(tracks=[t1, t2, t3])
    assert coord.total_width == 310
