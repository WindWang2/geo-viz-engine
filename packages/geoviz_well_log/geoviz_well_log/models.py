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

class CorrelationLink(BaseModel):
    source_well: str
    target_well: str
    source_interval_id: str
    target_interval_id: str
    color: str = "#f59e0b"
    is_manual: bool = False


class WellLogData(BaseModel):
    well_name: str
    top_depth: float
    bottom_depth: float
    datum_elevation: float = 0.0
    curves: list[CurveData] = []
    lithology: list[LithologyInterval] = []
    facies: list[FaciesInterval] = []
    intervals: Optional[WellIntervals] = None
    custom_tracks: list[dict] = []
    # #1193 (paleo-workbench): preview decimation provenance. Preview
    # loaders (min-max binning / strided sampling) set total_rows to the
    # source row count and decimated=True when rows were dropped, so
    # inference callers never mistake display data for full resolution.
    total_rows: Optional[int] = None
    decimated: bool = False
