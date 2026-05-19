from pydantic import BaseModel
from typing import Optional
from enum import Enum
from geoviz_well_log.models import (
    LineStyle,
    CurveData,
    IntervalItem,
    FaciesData,
    WellIntervals,
    WellLogData,
)


class CorrelationLink(BaseModel):
    source_well: str
    target_well: str
    source_interval_id: str  # Format: "top_bottom_name"
    target_interval_id: str
    color: str
    is_manual: bool = False


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


# Extend the WellLogData definition from geoviz_well_log to include app-specific fields
class AppWellLogData(WellLogData):
    lithology: list[LithologyInterval] = []
    facies: list[FaciesInterval] = []


# Override WellLogData with the extended one so existing code doesn't break
WellLogData = AppWellLogData


class WellCoordinates(BaseModel):
    name: str
    latitude: float
    longitude: float
