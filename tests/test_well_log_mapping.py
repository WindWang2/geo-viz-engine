import json
import math
from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QWidget
from src.pages.well_log_page import WellLogPage
from src.data.models import WellLogData, WellIntervals, IntervalItem, CurveData, FaciesData

class MockChartEngineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bridge = MagicMock()
        self.render_data = MagicMock()
        self.export_svg = MagicMock()

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
    # Mock get_well_data to return our mock data
    mock_entry = (lambda path, well_name: mock_well_data, "fake_path", {})
    monkeypatch.setattr("src.pages.well_log_page.get_well_data", lambda name: mock_entry)
    
    page = WellLogPage()
    qtbot.addWidget(page)
    
    mock_instance = MockChartEngineWidget()
    
    # We need to bypass the creation of real ChartEngine in load_well
    monkeypatch.setattr("src.pages.well_log_page.ChartEngine", lambda parent: mock_instance)
    
    page.load_well("TestWell")
    
    # Verify render_data was called with expected JSON
    assert mock_instance.render_data.called
    payload_json = mock_instance.render_data.call_args[0][0]
    payload = json.loads(payload_json)
    
    tracks = payload["tracks"]
    track_types = [t["type"] for t in tracks]
    
    # Expected order: Strat, Curve, Depth, Lith, Desc, Curve, Facies, Seq
    assert "IntervalTrack" in track_types # Strat
    assert "CurveTrack" in track_types # Curves
    assert "DepthTrack" in track_types
    assert "LithologyTrack" in track_types
    
    # Check for specific tracks by name
    track_names = [t.get("name") for t in tracks]
    assert "系" in track_names
    assert "组" in track_names
    assert "岩性描述" in track_names
    assert "相" in track_names
    assert "层序" in track_names
    
    # Check CurveTrack content
    curve_tracks = [t for t in tracks if t["type"] == "CurveTrack"]
    assert len(curve_tracks) >= 2
    assert any(any(s["name"] == "GR" for s in ct["series"]) for ct in curve_tracks)
    assert any(any(s["name"] == "RT" for s in ct["series"]) for ct in curve_tracks)

def test_systems_tract_shapes(qtbot, monkeypatch):
    from src.data.models import WellLogData, WellIntervals, IntervalItem
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
    monkeypatch.setattr("src.pages.well_log_page.get_well_data", lambda name: mock_entry)
    
    mock_instance = MockChartEngineWidget()
    monkeypatch.setattr("src.pages.well_log_page.ChartEngine", lambda parent: mock_instance)
    
    page = WellLogPage()
    page.load_well("TestWell")
    
    payload = json.loads(mock_instance.render_data.call_args[0][0])
    st_track = next(t for t in payload["tracks"] if t.get("name") == "体系域")
    
    tst_item = next(i for i in st_track["data"] if "TST" in i["name"])
    hst_item = next(i for i in st_track["data"] if "HST" in i["name"])
    
    assert tst_item["color"] == "#93c5fd"
    assert tst_item["shape"] == "triangle-up"
    assert hst_item["color"] == "#fde047"
    assert hst_item["shape"] == "triangle-down"

def test_stratigraphy_vertical_text(qtbot, monkeypatch):
    from src.data.models import WellLogData, WellIntervals, IntervalItem
    intervals = WellIntervals(
        system=[IntervalItem(top=1000, bottom=1100, name="系")]
    )
    mock_well_data = WellLogData(
        well_name="TestWell", top_depth=1000, bottom_depth=1100,
        curves=[], intervals=intervals
    )
    mock_entry = (lambda path, well_name: mock_well_data, "fake_path", {})
    monkeypatch.setattr("src.pages.well_log_page.get_well_data", lambda name: mock_entry)
    
    mock_instance = MockChartEngineWidget()
    monkeypatch.setattr("src.pages.well_log_page.ChartEngine", lambda parent: mock_instance)
    
    page = WellLogPage()
    page.load_well("TestWell")
    
    payload = json.loads(mock_instance.render_data.call_args[0][0])
    system_track = next(t for t in payload["tracks"] if t.get("name") == "系")
    
    assert system_track["textOrientation"] == "vertical"
