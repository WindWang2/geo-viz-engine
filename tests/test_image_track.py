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
