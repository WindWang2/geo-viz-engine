from src.data.models import CurveData
from src.renderers.well_log.config import CurveTrackConfig, TrackType
from src.renderers.well_log.tracks.curve_track import CurveTrack


def test_curve_track_single_curve(qtbot):
    curve = CurveData(
        name="GR", unit="gAPI", depth=[0, 1, 2, 3, 4],
        values=[10, 25, 40, 30, 15], display_range=(0, 150),
    )
    config = CurveTrackConfig(
        type=TrackType.CURVES, width=120, label="GR",
        curve_names=["GR"],
    )
    track = CurveTrack(config, [curve])
    qtbot.addWidget(track)
    assert track.view_box is not None


def test_curve_track_multi_curve(qtbot):
    curves = [
        CurveData(name="AC", unit="μs/ft", depth=[0, 1, 2], values=[2400, 2200, 2000],
                  display_range=(2000, 2600), color="#68d391"),
        CurveData(name="GR", unit="gAPI", depth=[0, 1, 2], values=[50, 80, 30],
                  display_range=(0, 150), color="#63b3ed"),
    ]
    config = CurveTrackConfig(
        type=TrackType.CURVES, width=120, label="AC/GR",
        curve_names=["AC", "GR"],
    )
    track = CurveTrack(config, curves)
    qtbot.addWidget(track)
    assert len(track._curves) == 2
