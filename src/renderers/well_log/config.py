from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


class TrackType(str, Enum):
    DEPTH = "depth"
    CURVES = "curves"
    INTERVAL = "interval"
    TEXT = "text"
    SYSTEMS_TRACT = "systems_tract"


class PatternMapping(BaseModel):
    patterns: dict[str, str] = Field(default_factory=dict)
    colors: dict[str, str] = Field(default_factory=dict)


class TrackConfig(BaseModel):
    type: TrackType
    width: int = 80
    label: str = ""
    label2: str = ""


class CurveTrackConfig(TrackConfig):
    type: TrackType = TrackType.CURVES
    curve_names: list[str] = Field(default_factory=list)
    alt_shading: bool = False


class IntervalTrackConfig(TrackConfig):
    type: TrackType = TrackType.INTERVAL
    data_key: str = ""
    facies_level: Optional[str] = None
    color_mapping: PatternMapping = PatternMapping()
    pattern_dir: Optional[str] = None
    rotate_text: bool = False


class TextTrackConfig(TrackConfig):
    type: TrackType = TrackType.TEXT
    data_key: str = ""
    editable: bool = False


class SystemsTractTrackConfig(TrackConfig):
    type: TrackType = TrackType.SYSTEMS_TRACT
    data_key: str = "systems_tract"


class CurveGroupConfig(BaseModel):
    """描述一条成组曲线（一个 CompositeModule），对应 AC+GR、RT+RXO 等配对"""
    label: str = ""
    curve_names: list[str] = Field(default_factory=list)
    width: int = 120


class ChartLayoutConfig(BaseModel):
    """
    新一代列配置：支持更清晰的曲线成组表达。
    现与旧 `tracks` 列表并存，两套均可被 ChartEngine 消费。
    迁移路径：ChartEngine 检测 `columns` 是否非空，非空则用新版，否则降级走 `tracks`。
    """
    columns: list[str | CurveGroupConfig] = Field(default_factory=list)


class ChartConfig(BaseModel):
    tracks: list[TrackConfig]
    pixel_ratio: float = 14.0
    grid_interval: float = 1.0
    header_height: int = 40
