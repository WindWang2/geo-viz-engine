from src.data.models import IntervalItem
from src.renderers.well_log.config import IntervalTrackConfig, TrackType, PatternMapping
from src.renderers.well_log.tracks.interval_track import IntervalTrack, _lookup_color, _lookup_pattern


def test_interval_track_renders(qtbot):
    intervals = [
        IntervalItem(top=0, bottom=50, name="砂岩"),
        IntervalItem(top=50, bottom=100, name="泥岩"),
    ]
    config = IntervalTrackConfig(
        type=TrackType.INTERVAL, width=80, label="岩性",
        data_key="lithology",
        color_mapping=PatternMapping(
            colors={"砂岩": "#fef08a", "泥岩": "#d1d5db"},
        ),
    )
    track = IntervalTrack(config, intervals, top_depth=0, bottom_depth=100)
    qtbot.addWidget(track)
    assert track._content is not None
    assert len(track._content._pattern_pixmaps) == 0  # no pattern_dir set


def test_interval_track_color_lookup():
    mapping = PatternMapping(
        patterns={"砂岩": "sandstone"},
        colors={"砂岩": "#fef08a", "泥岩": "#d1d5db"},
    )
    assert _lookup_color("砂岩", mapping) == "#fef08a"
    assert _lookup_color("细砂岩", mapping) == "#fef08a"  # substring match
    assert _lookup_color("灰岩", mapping) == "#e5e7eb"  # default

    assert _lookup_pattern("砂岩", mapping) == "sandstone"
    assert _lookup_pattern("泥岩", mapping) is None


def test_interval_track_dynamic_density(qtbot):
    from src.data.models import IntervalItem
    from src.renderers.well_log.config import IntervalTrackConfig, TrackType, PatternMapping

    intervals = [
        IntervalItem(top=0, bottom=50, name="砂岩"),
        IntervalItem(top=50, bottom=100, name="泥岩"),
    ]
    config = IntervalTrackConfig(
        type=TrackType.INTERVAL, width=80, label="岩性",
        data_key="lithology",
        color_mapping=PatternMapping(colors={"砂岩": "#fef08a", "泥岩": "#d1d5db"}),
    )
    track = IntervalTrack(config, intervals, top_depth=0, bottom_depth=100)
    qtbot.addWidget(track)
    track.setFixedHeight(200)

    track.sync_depth(0, 100)
    track.set_pixel_density(2.0)

    track.sync_depth(0, 50)
    track.set_pixel_density(4.0)  # 200/50=4px/m

    assert track._content._visible_top == 0
    assert track._content._visible_bottom == 50
    assert abs(track._content._px_per_m - 4.0) < 1e-6
