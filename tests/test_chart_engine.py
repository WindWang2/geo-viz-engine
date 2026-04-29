from src.data.models import CurveData, IntervalItem, WellIntervals, WellLogData, FaciesData
from src.renderers.well_log.config import (
    ChartConfig, TrackConfig, TrackType, CurveTrackConfig, IntervalTrackConfig,
)
from src.renderers.well_log.chart_engine import ChartEngine


def _sample_data() -> WellLogData:
    return WellLogData(
        well_name="Test-Well", top_depth=0, bottom_depth=100,
        curves=[
            CurveData(name="GR", unit="gAPI", depth=[0, 50, 100],
                      values=[10, 50, 30], display_range=(0, 150)),
        ],
        intervals=WellIntervals(
            lithology=[
                IntervalItem(top=0, bottom=50, name="砂岩"),
                IntervalItem(top=50, bottom=100, name="泥岩"),
            ],
        ),
    )


def _sample_config() -> ChartConfig:
    return ChartConfig(
        tracks=[
            TrackConfig(type=TrackType.DEPTH, width=40, label="深度"),
            CurveTrackConfig(type=TrackType.CURVES, width=120, label="GR",
                             curve_names=["GR"]),
            IntervalTrackConfig(type=TrackType.INTERVAL, width=80, label="岩性",
                                data_key="lithology"),
        ],
        pixel_ratio=14.0,
    )


def test_chart_engine_creates_tracks(qtbot):
    engine = ChartEngine(_sample_data(), _sample_config())
    qtbot.addWidget(engine)
    assert len(engine._tracks) == 3


def test_chart_engine_resolve_curves():
    engine = ChartEngine.__new__(ChartEngine)
    engine._data = _sample_data()
    result = engine._resolve_curves(["GR"])
    assert len(result) == 1
    assert result[0].name == "GR"

    result_empty = engine._resolve_curves(["NONEXIST"])
    assert len(result_empty) == 0


def test_chart_engine_resolve_intervals():
    engine = ChartEngine.__new__(ChartEngine)
    engine._data = _sample_data()
    result = engine._resolve_intervals("lithology")
    assert result is not None
    assert len(result) == 2

    result_none = engine._resolve_intervals("nonexist")
    assert result_none is None
