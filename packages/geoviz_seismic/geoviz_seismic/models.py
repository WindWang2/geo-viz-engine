from pydantic import BaseModel


class SeismicVolumeMeta(BaseModel):
    filename: str
    n_inlines: int
    n_crosslines: int
    n_samples: int
    sample_interval: float
    iline_start: int
    iline_step: int
    xline_start: int
    xline_step: int
    dt_ms: float
    t0_ms: float = 0.0


class SliceInfo(BaseModel):
    slice_type: str
    position: int
    axis_h_label: str
    axis_v_label: str
    axis_h_values: list[float]
    axis_v_values: list[float]


class HorizonData(BaseModel):
    name: str
    unit: str
    shape: tuple[int, int]
    filled: bool
