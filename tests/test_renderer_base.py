# tests/test_renderer_base.py
import pytest
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF


def test_base_track_is_abstract():
    """BaseTrack cannot be instantiated directly."""
    from geoviz_well_log.renderer.track_base import BaseTrack
    with pytest.raises(TypeError):
        BaseTrack(label="Test", width=100)


def test_concrete_track_paint_content_called(qtbot):
    """A concrete subclass can be created and paint_content is callable."""
    from geoviz_well_log.renderer.track_base import BaseTrack

    class ConcreteTrack(BaseTrack):
        def __init__(self):
            super().__init__(label="GR", width=100)
            self.painted = False

        def paint_content(self, painter, rect):
            self.painted = True

    track = ConcreteTrack()
    qtbot.addWidget(track)
    assert track.label == "GR"
    assert track.width == 100
    assert track.header_height == 56

    # Simulate paint
    pm = QPixmap(100, 200)
    painter = QPainter(pm)
    track.paint_content(painter, pm.rect().toRectF())
    painter.end()
    assert track.painted is True


def test_base_track_depth_range(qtbot):
    """set_depth_range updates stored range."""
    from geoviz_well_log.renderer.track_base import BaseTrack

    class ConcreteTrack(BaseTrack):
        def __init__(self):
            super().__init__(label="D", width=60)
        def paint_content(self, painter, rect):
            pass

    track = ConcreteTrack()
    qtbot.addWidget(track)
    track.set_depth_range(100.0, 200.0)
    assert track.depth_top == 100.0
    assert track.depth_bottom == 200.0


def test_base_track_depth_span(qtbot):
    """depth_span returns bottom - top."""
    from geoviz_well_log.renderer.track_base import BaseTrack

    class ConcreteTrack(BaseTrack):
        def __init__(self):
            super().__init__(label="D", width=60)
        def paint_content(self, painter, rect):
            pass

    track = ConcreteTrack()
    qtbot.addWidget(track)
    track.set_depth_range(50.0, 150.0)
    assert track.depth_span == 100.0


def test_subclass_without_paint_content_raises(qtbot):
    """Subclass that doesn't override paint_content raises NotImplementedError."""
    from geoviz_well_log.renderer.track_base import BaseTrack

    class IncompleteTrack(BaseTrack):
        pass

    track = IncompleteTrack(label="X", width=50)
    qtbot.addWidget(track)
    pm = QPixmap(50, 100)
    painter = QPainter(pm)
    with pytest.raises(NotImplementedError):
        track.paint_content(painter, QRectF(0, 0, 50, 100))
    painter.end()
