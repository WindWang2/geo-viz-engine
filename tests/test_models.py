from src.data.models import (
    CurveData, IntervalItem, WellIntervals, WellLogData, WellCoordinates,
    FaciesData,
)


def test_curve_data_defaults():
    c = CurveData(name="GR", unit="gAPI", depth=[0, 1, 2], values=[10, 20, 30])
    assert c.name == "GR"
    assert c.display_range == (0.0, 100.0)
    assert c.color == "#63b3ed"
    assert c.line_style == "solid"


def test_curve_data_custom():
    c = CurveData(
        name="RT", unit="Ω·m", depth=[0, 1], values=[1, 5],
        display_range=(0.2, 2000), color="#f6ad55", line_style="dashed",
    )
    assert c.display_range == (0.2, 2000)
    assert c.line_style == "dashed"


def test_interval_item():
    iv = IntervalItem(top=10, bottom=20, name="砂岩")
    assert iv.name == "砂岩"


def test_well_intervals():
    wi = WellIntervals(
        lithology=[IntervalItem(top=0, bottom=100, name="砂岩")],
        facies=FaciesData(
            phase=[IntervalItem(top=0, bottom=100, name="潮坪")],
        ),
    )
    assert len(wi.lithology) == 1
    assert len(wi.facies.phase) == 1


def test_well_log_data_with_intervals():
    w = WellLogData(well_name="Test-1", top_depth=0, bottom_depth=100)
    assert w.intervals is None

    w2 = WellLogData(
        well_name="Test-2", top_depth=0, bottom_depth=100,
        intervals=WellIntervals(),
    )
    assert w2.intervals is not None


def test_well_coordinates():
    wc = WellCoordinates(name="HZ25-10-1", latitude=38.5, longitude=117.8)
    assert wc.name == "HZ25-10-1"
