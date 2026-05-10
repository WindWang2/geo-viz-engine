"""Pydantic data models for seismic volume metadata, slice info, and horizons."""

from typing import Literal

from pydantic import BaseModel


class SeismicVolumeMeta(BaseModel):
    """Metadata describing a 3-D seismic volume.

    Attributes:
        filename: Source file path or ``"demo"`` for synthetic data.
        n_inlines: Number of inline traces.
        n_crosslines: Number of crossline traces.
        n_samples: Number of time/depth samples per trace.
        sample_interval: Sample interval in milliseconds.
        iline_start: First inline number (segyio convention).
        iline_step: Step between consecutive inline numbers.
        xline_start: First crossline number.
        xline_step: Step between consecutive crossline numbers.
        dt_ms: Same as *sample_interval*; kept for backward compat.
        t0_ms: Time of first sample in milliseconds (default 0.0).
    """

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
    """Metadata for a single 2-D seismic slice.

    Attributes:
        slice_type: Orientation — ``"inline"``, ``"crossline"``, or ``"time"``.
        position: Inline/crossline number or sample index of the slice.
        axis_h_label: Display label for the horizontal axis.
        axis_v_label: Display label for the vertical axis.
        axis_h_values: Tick values for the horizontal axis.
        axis_v_values: Tick values for the vertical axis.
    """

    slice_type: Literal["inline", "crossline", "time"]
    position: int
    axis_h_label: str
    axis_v_label: str
    axis_h_values: list[float]
    axis_v_values: list[float]


class HorizonData(BaseModel):
    """Describes a parsed horizon surface.

    Attributes:
        name: Horizon identifier (e.g. file basename).
        unit: Depth/time unit — ``"ms"``, ``"m"``, or ``"ft"``.
        shape: Grid dimensions ``(n_inlines, n_crosslines)``.
        filled: Whether NaN gaps have been interpolated.
    """

    name: str
    unit: Literal["ms", "m", "ft"]
    shape: tuple[int, int]
    filled: bool
