from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, model_validator


class CurveData(BaseModel):
    name: str
    unit: str
    data: List[float]
    depth: List[float]
    min_value: float
    max_value: float
    display_range: Tuple[float, float]
    color: str
    line_style: str  # "solid" | "dashed" | "dotted"


class WellLogData(BaseModel):
    well_id: str
    well_name: str
    depth_start: float
    depth_end: float
    depth_step: float
    location: Optional[Tuple[float, float]] = None
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    curves: List[CurveData]


class WellMetadata(BaseModel):
    well_id: str
    well_name: str
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    depth_start: float
    depth_end: float
    curve_names: List[str]


class GenerateDataRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=100)
    depth_start: float = Field(default=0.0, ge=0.0)
    depth_end: float = Field(default=3000.0, gt=0.0)
    depth_step: float = Field(default=0.125, gt=0.0)

    @model_validator(mode="after")
    def depth_end_must_exceed_depth_start(self) -> "GenerateDataRequest":
        if self.depth_end <= self.depth_start:
            raise ValueError(f"depth_end ({self.depth_end}) must be greater than depth_start ({self.depth_start})")
        return self


class GenerateDataResponse(BaseModel):
    wells: List[WellMetadata]
    message: str
    generated_count: int
