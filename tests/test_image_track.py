"""Unit tests for ImageTrack, CorePhotoSegment, and BoreholeImageSegment."""
import pytest
from PySide6.QtGui import QPixmap, QColor
from geoviz_well_log.tracks.image_track import ImageTrack, CorePhotoSegment

@pytest.fixture
def image_track(qtbot):
    track = ImageTrack(name="Core Photo Track", width=160)
    return track

def test_image_track_segments(image_track):
    seg1 = CorePhotoSegment(depth_top=2100.0, depth_bottom=2105.0, title="Core Segment #1")
    image_track.add_core_photo(seg1)

    assert len(image_track.core_photos) == 1
    assert image_track.core_photos[0].depth_top == 2100.0
    assert image_track.core_photos[0].depth_bottom == 2105.0


def test_image_track_set_depth_range_updates_base_limits(image_track):
    """#723: ImageTrack must keep BaseTrack depth_top/bottom in sync."""
    image_track.set_depth_range(1500.0, 2500.0)
    assert image_track.depth_top == 1500.0
    assert image_track.depth_bottom == 2500.0
    assert image_track.depth_span == 1000.0


def test_image_track_double_click_opens_preview_at_realistic_depth(qtbot, monkeypatch):
    """#723: photo at 2000-2050m must be hittable on a 1500-2500m canvas."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent, QPixmap, QColor

    from geoviz_well_log.renderer.canvas import WellLogCanvas

    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    pix = QPixmap(20, 20)
    pix.fill(QColor(10, 20, 30))
    photo = CorePhotoSegment(
        depth_top=2000.0, depth_bottom=2050.0, title="Core 2000", pixmap=pix
    )
    track = ImageTrack(name="Core Photos", width=160)
    track.add_core_photo(photo)
    canvas.add_track(track)
    canvas.set_depth_range(1500.0, 2500.0)
    canvas.resize(160, 556)

    opened = []

    class _FakeDialog:
        def __init__(self, pixmap, title, parent=None):
            opened.append(title)

        def exec(self):
            return 1

    monkeypatch.setattr(
        "geoviz_well_log.image_preview_dialog.ImagePreviewDialog", _FakeDialog
    )

    # header 56, content 500 → depth 2025 sits at y = 56 + 262.5
    event = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        QPointF(80.0, 318.5),
        QPointF(80.0, 318.5),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseDoubleClickEvent(event)
    assert opened == ["Core 2000"]
