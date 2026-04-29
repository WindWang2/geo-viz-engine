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


class ChartConfig(BaseModel):
    tracks: list[TrackConfig]
    pixel_ratio: float = 14.0
    grid_interval: float = 1.0
    header_height: int = 40
