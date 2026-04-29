from pathlib import Path

from src.renderers.well_log.config import (
    ChartConfig, TrackConfig, TrackType,
    CurveTrackConfig, IntervalTrackConfig, TextTrackConfig,
    SystemsTractTrackConfig, PatternMapping,
)

_PATTERNS_DIR = str(Path(__file__).parent.parent.parent.parent / "patterns")

LITHOLOGY_MAPPING = PatternMapping(
    patterns={
        "白云岩": "dolomite", "白云质": "dolomite",
        "砂岩": "sandstone", "细砂岩": "sandstone",
        "粉砂岩": "siltstone",
        "泥岩": "mudstone",
        "页岩": "shale",
        "灰岩": "limestone", "石灰岩": "limestone",
    },
    colors={
        "白云岩": "#dbeafe", "白云质": "#bfdbfe",
        "砂岩": "#fef08a", "细砂岩": "#fef9c3",
        "粉砂岩": "#f3f4f6",
        "泥质粉砂岩": "#e2e8f0", "泥岩": "#d1d5db",
        "页岩": "#9ca3af",
        "灰岩": "#e0e7ff", "石灰岩": "#c7d2fe",
        "紫红色": "#fecaca", "灰绿色": "#bbf7d0",
        "灰黑色": "#6b7280", "深灰色": "#9ca3af",
        "浅灰色": "#f3f4f6", "灰色": "#e5e7eb",
    },
)

FACIES_MAPPING = PatternMapping(
    patterns={
        "潮坪": "tidal_flat", "陆棚": "shelf",
        "砂坪": "sand_flat", "泥坪": "mud_flat",
        "混积": "mixed", "碎屑岩": "clastic_shelf",
        "云质": "dolomitic_flat", "泥质": "muddy_shelf",
        "砂质": "sandy_shelf", "砂泥质": "sand_mud_shelf",
    },
    colors={
        "潮坪": "#dbeafe", "陆棚": "#d1fae5",
        "砂坪": "#fef3c7", "泥坪": "#e5e7eb",
        "混积": "#fde68a", "碎屑岩": "#fcd34d",
        "云质": "#93c5fd", "泥质": "#e2e8f0",
        "砂质": "#fef08a", "砂泥质": "#fef9c3",
        "河流相": "#fef3c7", "三角洲相": "#dbeafe",
    },
)

laolong1_config = ChartConfig(
    tracks=[
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=40, label="地层系统", label2="系",
            data_key="series", rotate_text=True,
            color_mapping=PatternMapping(colors={"default": "#e5e7eb"}),
        ),
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=40, label="统",
            data_key="system", rotate_text=True,
            color_mapping=PatternMapping(colors={"default": "#e5e7eb"}),
        ),
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=40, label="组",
            data_key="formation", rotate_text=True,
            color_mapping=PatternMapping(colors={"default": "#e5e7eb"}),
        ),
        CurveTrackConfig(
            type=TrackType.CURVES, width=120, label="AC/GR",
            curve_names=["AC", "GR"],
        ),
        TrackConfig(
            type=TrackType.DEPTH, width=40, label="深度", label2="(m)",
        ),
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=60, label="岩性",
            data_key="lithology",
            color_mapping=LITHOLOGY_MAPPING,
            pattern_dir=_PATTERNS_DIR,
        ),
        CurveTrackConfig(
            type=TrackType.CURVES, width=120, label="RT/RXO",
            curve_names=["RT", "RXO"],
        ),
        TextTrackConfig(
            type=TrackType.TEXT, width=150, label="岩性描述",
            data_key="lithology",
        ),
        CurveTrackConfig(
            type=TrackType.CURVES, width=120, label="SH/PERM\n/PHIE",
            curve_names=["SH", "PERM", "PHIE"],
        ),
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=80, label="微相",
            data_key="facies", facies_level="micro_phase",
            color_mapping=FACIES_MAPPING, pattern_dir=_PATTERNS_DIR,
        ),
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=80, label="亚相",
            data_key="facies", facies_level="sub_phase",
            color_mapping=FACIES_MAPPING, pattern_dir=_PATTERNS_DIR,
        ),
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=80, label="相",
            data_key="facies", facies_level="phase",
            color_mapping=FACIES_MAPPING, pattern_dir=_PATTERNS_DIR,
        ),
        SystemsTractTrackConfig(
            type=TrackType.SYSTEMS_TRACT, width=60, label="体系域",
            data_key="systems_tract",
        ),
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=40, label="层序",
            data_key="sequence", rotate_text=True,
            color_mapping=PatternMapping(colors={"default": "#e5e7eb"}),
        ),
    ],
    pixel_ratio=14.0,
    grid_interval=1.0,
    header_height=40,
)
