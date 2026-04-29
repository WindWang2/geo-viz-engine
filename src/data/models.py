from pydantic import BaseModel


class CurveData(BaseModel):
    name: str
    unit: str = ""
    depth: list[float]
    values: list[float]


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
