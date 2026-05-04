from pathlib import Path

from src.renderers.well_log.config import (
    ChartConfig, TrackConfig, TrackType,
    CurveTrackConfig, IntervalTrackConfig, SystemsTractTrackConfig,
    TextTrackConfig, PatternMapping,
)

_PATTERNS_DIR = str(Path(__file__).parent.parent.parent.parent / "patterns")

LITHOLOGY_MAPPING = PatternMapping(
    patterns={
        "白云岩": "dolomite", "白云质": "dolomite",
        "砂岩": "sandstone", "粗砂岩": "sandstone", "细砂岩": "sandstone",
        "中砂岩": "sandstone", "钙质砂岩": "sandstone",
        "粉砂岩": "siltstone", "粉砂质": "siltstone",
        "泥岩": "mudstone", "泥质": "mudstone",
        "页岩": "shale",
        "灰岩": "limestone", "石灰岩": "limestone",
        "煤": "shale",  # TODO: create coal.svg per GB/T 附录M
    },
    colors={
        "白云岩": "#dbeafe", "白云质": "#bfdbfe",
        "砂岩": "#fef08a", "粗砂岩": "#fef08a", "细砂岩": "#fef9c3",
        "中砂岩": "#fef08a", "钙质砂岩": "#fde68a",
        "粉砂岩": "#f3f4f6", "粉砂质泥岩": "#e2e8f0",
        "泥岩": "#d1d5db", "泥质粉砂岩": "#e2e8f0",
        "页岩": "#9ca3af",
        "灰岩": "#e0e7ff", "石灰岩": "#c7d2fe",
        "煤": "#4a5568",
        "紫红色": "#fecaca", "灰绿色": "#bbf7d0",
        "灰黑色": "#6b7280", "深灰色": "#9ca3af",
        "浅灰色": "#f3f4f6", "灰色": "#e5e7eb",
    },
)

FACIES_MAPPING = PatternMapping(
    patterns={
        # Specific patterns first so substring search finds the right one
        "砂泥质陆棚": "sand_mud_shelf",
        "砂质陆棚": "sandy_shelf",
        "泥质陆棚": "muddy_shelf",
        "碎屑岩浅水陆棚": "clastic_shelf",
        "碎屑岩潮坪": "clastic_shelf",
        "混积浅水陆棚": "mixed",
        "混积潮坪": "mixed",
        "云质砂坪": "dolomitic_flat",
        "浅海陆棚": "shelf",
        "滨外陆棚": "shelf",
        "陆棚砂脊": "shelf",
        "水下分流河道间": "mud_flat",
        "分流河道间": "mud_flat",
        "水下分流河道": "delta",
        "分流河道": "delta",
        "前三角洲泥": "mud_flat",
        "前三角洲": "mud_flat",
        "三角洲前缘": "delta",
        "三角洲平原": "delta",
        "扇三角洲平原": "delta",
        "扇三角洲": "delta",
        "三角洲": "delta",
        "河口坝": "delta",
        "席状砂": "delta",
        "远砂坝": "delta",
        "天然堤": "mud_flat",
        "滨浅湖泥": "mud_flat",
        "滨浅湖": "mud_flat",
        "陆棚泥": "mud_flat",
        "潮坪": "tidal_flat",
        "陆棚": "shelf",
        "浅海": "shelf",
        "砂坪": "sand_flat",
        "泥坪": "mud_flat",
        "湖泊": "mud_flat",
        "混积": "mixed",
        "碎屑岩": "clastic_shelf",
        "云质": "dolomitic_flat",
        "泥质": "muddy_shelf",
        "砂质": "sandy_shelf",
        "砂泥质": "sand_mud_shelf",
    },
    colors={
        # 老龙1 specific entries first (substring search stops at first match)
        "云质砂坪": "#fde68a",
        "砂坪": "#fef08a",
        "砂泥质陆棚": "#bbf7d0",
        "泥质陆棚": "#d1fae5",
        "砂质陆棚": "#a7f3d0",
        "混积潮坪": "#fde68a",
        "碎屑岩潮坪": "#fef08a",
        "碎屑岩浅水陆棚": "#86efac",
        "混积浅水陆棚": "#bbf7d0",
        "潮坪相": "#fef9c3",
        "陆棚相": "#bfdbfe",
        # Generic entries
        "浅海陆棚": "#dbeafe",
        "陆棚": "#d1fae5",
        "滨外陆棚": "#dbeafe",
        "三角洲前缘": "#fde68a",
        "前三角洲": "#e5e7eb",
        "三角洲平原": "#fcd34d",
        "扇三角洲平原": "#fcd34d",
        "三角洲": "#fef3c7",
        "扇三角洲": "#fef3c7",
        "湖泊": "#d1fae5",
        "滨浅湖泥": "#e5e7eb",
        "滨浅湖": "#d1fae5",
        "陆棚砂脊": "#fef3c7",
        "陆棚泥": "#e5e7eb",
        "水下分流河道间": "#e5e7eb",
        "水下分流河道": "#fef08a",
        "分流河道间": "#e5e7eb",
        "分流河道": "#fef08a",
        "水下天然堤": "#e2e8f0",
        "前三角洲泥": "#d1d5db",
        "河口坝": "#fde68a",
        "席状砂": "#fef9c3",
        "远砂坝": "#f3f4f6",
    },
)

laolong1_config = ChartConfig(
    tracks=[
        # 地层系统 — 系, 统, 组
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=35, label="系",
            data_key="series", rotate_text=True, group="地层系统",
            color_mapping=PatternMapping(colors={"default": "#e5e7eb"}),
        ),
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=35, label="统",
            data_key="system", rotate_text=True, group="地层系统",
            color_mapping=PatternMapping(colors={"default": "#e5e7eb"}),
        ),
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=55, label="组",
            data_key="formation", rotate_text=True, group="地层系统",
            color_mapping=PatternMapping(colors={"default": "#e5e7eb"}),
        ),
        # AC/GR curves (AC 40-80 dashed blue, GR 0-100 solid green)
        CurveTrackConfig(
            type=TrackType.CURVES, width=120, label="AC/GR",
            curve_names=["AC", "GR"],
        ),
        # Depth axis
        TrackConfig(
            type=TrackType.DEPTH, width=50, label="深度", label2="(m)",
        ),
        # Lithology pattern track
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=60, label="岩性",
            data_key="lithology",
            color_mapping=LITHOLOGY_MAPPING,
            pattern_dir=_PATTERNS_DIR,
        ),
        # RT/RXO curves (RT 0.1-1000 solid red, RXO 0.1-1000 dashed orange)
        CurveTrackConfig(
            type=TrackType.CURVES, width=120, label="RT/RXO",
            curve_names=["RT", "RXO"],
        ),
        # Lithology text descriptions
        TextTrackConfig(
            type=TrackType.TEXT, width=160, label="岩性描述",
            data_key="lithology_desc",
        ),
        # 沉积相 — 微相, 亚相, 相
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=100, label="微相",
            data_key="facies", facies_level="micro_phase", group="沉积相",
            color_mapping=FACIES_MAPPING, pattern_dir=_PATTERNS_DIR,
        ),
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=90, label="亚相",
            data_key="facies", facies_level="sub_phase", group="沉积相",
            color_mapping=FACIES_MAPPING, pattern_dir=_PATTERNS_DIR,
        ),
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=60, label="相",
            data_key="facies", facies_level="phase", group="沉积相",
            color_mapping=FACIES_MAPPING, pattern_dir=_PATTERNS_DIR,
        ),
        # 体系域 (HST/TST triangles)
        SystemsTractTrackConfig(
            type=TrackType.SYSTEMS_TRACT, width=55, label="体系域",
        ),
        # 层序 (SQ1/SQ2)
        IntervalTrackConfig(
            type=TrackType.INTERVAL, width=50, label="层序",
            data_key="sequence", rotate_text=True,
            color_mapping=PatternMapping(colors={
                "SQ1": "#bfdbfe", "SQ2": "#fef9c3", "default": "#e5e7eb",
            }),
        ),
    ],
    pixel_ratio=6.0,
    grid_interval=5.0,
    header_height=60,
)
