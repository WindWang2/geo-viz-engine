import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.models import IntervalItem, FaciesData
from geoviz_well_log.renderer.facies_track import FaciesTrack


def _make_facies_data():
    return FaciesData(
        phase=[
            IntervalItem(top=0, bottom=150, name="三角洲"),
            IntervalItem(top=150, bottom=300, name="陆棚"),
        ],
        sub_phase=[
            IntervalItem(top=0, bottom=80, name="前三角洲"),
            IntervalItem(top=80, bottom=150, name="三角洲前缘"),
            IntervalItem(top=150, bottom=300, name="碳酸盐台地"),
        ],
        micro_phase=[
            IntervalItem(top=0, bottom=40, name="砂泥质陆棚"),
            IntervalItem(top=40, bottom=80, name="混积浅水陆棚"),
            IntervalItem(top=80, bottom=120, name="河口坝"),
            IntervalItem(top=120, bottom=150, name="远砂坝"),
            IntervalItem(top=150, bottom=220, name="局限台地"),
            IntervalItem(top=220, bottom=300, name="开阔台地"),
        ],
    )


def test_facies_track_creation(qtbot):
    track = FaciesTrack(facies_data=_make_facies_data(), label="Facies", width=80)
    qtbot.addWidget(track)
    assert track.label == "Facies"


def test_facies_track_paint_single_column(qtbot):
    """Default mode: single column showing most specific level."""
    track = FaciesTrack(facies_data=_make_facies_data(), label="Facies", width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_facies_track_paint_nested_columns(qtbot):
    """Nested mode: three columns for phase/sub_phase/micro_phase."""
    track = FaciesTrack(facies_data=_make_facies_data(), label="Facies", width=180,
                        nested=True)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(180, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 180, 800))
    painter.end()


def test_facies_track_export_render(qtbot):
    track = FaciesTrack(facies_data=_make_facies_data(), label="Facies", width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 80, 832))
    painter.end()


def test_facies_track_empty_data(qtbot):
    data = FaciesData()
    track = FaciesTrack(facies_data=data, label="Facies", width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_facies_track_partial_data(qtbot):
    """Only phase data, no sub/micro."""
    data = FaciesData(
        phase=[IntervalItem(top=0, bottom=100, name="三角洲")],
    )
    track = FaciesTrack(facies_data=data, label="Facies", width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()
