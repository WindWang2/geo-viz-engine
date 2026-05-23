import pytest
from PySide6.QtWidgets import QWidget
from src.pages.well_log import WellLogPage
from geoviz_well_log.models import WellLogData, WellIntervals, IntervalItem, CurveData, FaciesData
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.renderer.lithology_track import LithologyTrack
from geoviz_well_log.renderer.interval_track import IntervalTrack
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.systems_tract import SystemsTractTrack, _TRACT_COLORS, _TRACT_SHAPES


@pytest.fixture
def mock_well_data():
    intervals = WellIntervals(
        system=[IntervalItem(top=1000, bottom=1100, name="Test System")],
        formation=[IntervalItem(top=1000, bottom=1050, name="Test Formation")],
        lithology=[IntervalItem(top=1000, bottom=1020, name="砂岩")],
        lithology_desc=[IntervalItem(top=1000, bottom=1020, name="砂岩描述")],
        facies=FaciesData(phase=[IntervalItem(top=1000, bottom=1100, name="Test Phase")]),
        sequence=[IntervalItem(top=1000, bottom=1100, name="Test Seq")]
    )

    curves = [
        CurveData(name="GR", depth=[1000, 1010], values=[40, 50]),
        CurveData(name="RT", depth=[1000, 1010], values=[10, 20])
    ]

    return WellLogData(
        well_name="TestWell",
        top_depth=1000,
        bottom_depth=1100,
        curves=curves,
        intervals=intervals
    )


def test_well_log_page_mapping(qtbot, mock_well_data, monkeypatch):
    mock_entry = (lambda path, well_name: mock_well_data, "fake_path", {})
    monkeypatch.setattr("src.pages.well_log.page.get_well_data", lambda name: mock_entry)

    page = WellLogPage()
    qtbot.addWidget(page)
    page.load_well("TestWell")

    tracks = page._all_tracks
    track_labels = [t.label for t in tracks]
    track_types = [type(t).__name__ for t in tracks]

    assert "IntervalTrack" in track_types
    assert "CurveTrack" in track_types
    assert "DepthTrack" in track_types
    assert "LithologyTrack" in track_types

    assert "系" in track_labels
    assert "组" in track_labels
    assert "岩性描述" in track_labels
    assert "沉积相" in track_labels
    assert "层序" in track_labels

    curve_tracks = [t for t in tracks if isinstance(t, CurveTrack)]
    assert len(curve_tracks) >= 1
    all_curve_names = [c.name for ct in curve_tracks for c in ct._curves]
    assert "GR" in all_curve_names
    assert "RT" in all_curve_names


def test_systems_tract_colors_and_shapes(qtbot, monkeypatch):
    from geoviz_well_log.models import WellLogData, WellIntervals, IntervalItem
    intervals = WellIntervals(
        systems_tract=[
            IntervalItem(top=1000, bottom=1050, name="TST1"),
            IntervalItem(top=1050, bottom=1100, name="HST1")
        ]
    )
    mock_well_data = WellLogData(
        well_name="TestWell", top_depth=1000, bottom_depth=1100,
        curves=[], intervals=intervals
    )
    mock_entry = (lambda path, well_name: mock_well_data, "fake_path", {})
    monkeypatch.setattr("src.pages.well_log.page.get_well_data", lambda name: mock_entry)

    page = WellLogPage()
    qtbot.addWidget(page)
    page.load_well("TestWell")

    st_track = next((t for t in page._all_tracks if isinstance(t, SystemsTractTrack)), None)
    assert st_track is not None, "SystemsTractTrack not found in tracks"

    # Verify TST and HST colors from module-level mapping
    assert _TRACT_COLORS["TST"] == "#93c5fd"
    assert _TRACT_COLORS["HST"] == "#fde047"

    # Verify shapes
    assert _TRACT_SHAPES["TST"] == "triangle_up"
    assert _TRACT_SHAPES["HST"] == "triangle_down"


def test_stratigraphy_interval_track_created(qtbot, monkeypatch):
    from geoviz_well_log.models import WellLogData, WellIntervals, IntervalItem
    intervals = WellIntervals(
        system=[IntervalItem(top=1000, bottom=1100, name="系")]
    )
    mock_well_data = WellLogData(
        well_name="TestWell", top_depth=1000, bottom_depth=1100,
        curves=[], intervals=intervals
    )
    mock_entry = (lambda path, well_name: mock_well_data, "fake_path", {})
    monkeypatch.setattr("src.pages.well_log.page.get_well_data", lambda name: mock_entry)

    page = WellLogPage()
    qtbot.addWidget(page)
    page.load_well("TestWell")

    system_track = next((t for t in page._all_tracks if t.label == "系"), None)
    assert system_track is not None
    assert isinstance(system_track, IntervalTrack)
    assert len(system_track._intervals) == 1
    assert system_track._intervals[0].name == "系"


def test_ai_facies_prediction_applies_tracks(qtbot, monkeypatch, tmp_path):
    import pandas as pd
    from geoviz_well_log.models import WellLogData, CurveData, WellIntervals

    mock_well_data = WellLogData(
        well_name="TestWell", top_depth=1000, bottom_depth=1100,
        curves=[CurveData(name="GR", depth=[1000, 1010], values=[40, 50])],
        intervals=WellIntervals()
    )

    xls_path = tmp_path / "test.xlsx"
    pd.DataFrame().to_excel(xls_path)

    mock_entry = (lambda path, well_name: mock_well_data, str(xls_path), {})
    monkeypatch.setattr("src.pages.well_log.page.get_well_data", lambda name: mock_entry)

    page = WellLogPage()
    qtbot.addWidget(page)
    page.load_well("TestWell")

    records = [{"深度": 1000.0, "预测相": "1", "置信度": 0.95}]
    page._apply_ai_prediction(records)

    track_labels = [t.label for t in page._all_tracks]
    assert "AI预测相" in track_labels
    assert "AI预测置信度" in track_labels

    ai_track = next(t for t in page._all_tracks if t.label == "AI预测相")
    assert isinstance(ai_track, IntervalTrack)
    assert len(ai_track._intervals) == 1
    assert ai_track._intervals[0].name == "1"
