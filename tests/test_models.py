from src.data.models import WellLogData, CurveData, LithologyInterval, WellCoordinates


def test_curve_data():
    c = CurveData(name="GR", unit="gAPI", depth=[0, 1, 2], values=[10, 20, 30])
    assert c.name == "GR"
    assert len(c.depth) == 3


def test_well_log_data():
    w = WellLogData(well_name="Test-1", top_depth=0, bottom_depth=100)
    assert w.well_name == "Test-1"
    assert w.curves == []


def test_lithology_interval():
    li = LithologyInterval(top=10, bottom=20, lithology="sandstone", description="砂岩")
    assert li.lithology == "sandstone"


def test_well_coordinates():
    wc = WellCoordinates(name="HZ25-10-1", latitude=38.5, longitude=117.8)
    assert wc.name == "HZ25-10-1"
