from pydantic import BaseModel
from typing import Optional
from enum import Enum


class LineStyle(str, Enum):
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


class CurveData(BaseModel):
    name: str
    unit: str = ""
    depth: list[float]
    values: list[float]
    display_range: tuple[float, float] = (0.0, 100.0)
    color: str = "#63b3ed"
    line_style: LineStyle = LineStyle.SOLID


class IntervalItem(BaseModel):
    top: float
    bottom: float
    name: str


class FaciesData(BaseModel):
    phase: list[IntervalItem] = []
    sub_phase: list[IntervalItem] = []
    micro_phase: list[IntervalItem] = []


class WellIntervals(BaseModel):
    series: list[IntervalItem] = []
    system: list[IntervalItem] = []
    formation: list[IntervalItem] = []
    member: list[IntervalItem] = []
    lithology: list[IntervalItem] = []
    lithology_desc: list[IntervalItem] = []
    systems_tract: list[IntervalItem] = []
    sequence: list[IntervalItem] = []
    facies: FaciesData = FaciesData()


# Legacy models — kept for backward compatibility with existing loaders/tests
class LithologyInterval(BaseModel):
    top: float
    bottom: float
    lithology: str
    description: str = ""


class FaciesInterval(BaseModel):
    top: float
    bottom: float
    facies: str
    sub_facies: str = ""
    micro_facies: str = ""


class WellLogData(BaseModel):
    well_name: str
    top_depth: float
    bottom_depth: float
    curves: list[CurveData] = []
    lithology: list[LithologyInterval] = []
    facies: list[FaciesInterval] = []
    intervals: Optional[WellIntervals] = None


class WellCoordinates(BaseModel):
    name: str
    latitude: float
    longitude: float


class SeismicVolumeMeta(BaseModel):
    filename: str
    n_inlines: int
    n_crosslines: int
    n_samples: int
    sample_interval: float
