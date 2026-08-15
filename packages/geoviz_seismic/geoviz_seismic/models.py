"""Pydantic data models for seismic volume metadata, slice info, and horizons."""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
from pydantic import BaseModel


class BinGridGeometry(BaseModel):
    """Bin-grid geometry for mapping inline/crossline to world coordinates.

    Attributes:
        x_origin: Origin X coordinate (e.g. UTM easting).
        y_origin: Origin Y coordinate (e.g. UTM northing).
        il_azimuth_deg: Azimuth of inline axis in degrees from north.
        il_spacing_m: Inline spacing in metres.
        xl_spacing_m: Crossline spacing in metres.
    """

    x_origin: float
    y_origin: float
    il_azimuth_deg: float = 0.0
    il_spacing_m: float
    xl_spacing_m: float

    def xy_to_il_xl(self, x: float, y: float) -> tuple[float, float]:
        """Convert world (x, y) to fractional (inline, crossline) indices.

        Azimuth is measured clockwise from north (Y axis). When azimuth=0,
        inline direction is north (+Y) and crossline is east (+X).
        """
        dx = x - self.x_origin
        dy = y - self.y_origin
        az = math.radians(self.il_azimuth_deg)
        cos_a, sin_a = math.cos(az), math.sin(az)
        il_frac = (-dx * sin_a + dy * cos_a) / self.il_spacing_m
        xl_frac = (dx * cos_a + dy * sin_a) / self.xl_spacing_m
        return il_frac, xl_frac

    def il_xl_to_xy(self, il_frac: float, xl_frac: float) -> tuple[float, float]:
        """Convert fractional (inline, crossline) indices to world (x, y) coordinates."""
        az = math.radians(self.il_azimuth_deg)
        cos_a, sin_a = math.cos(az), math.sin(az)
        x = self.x_origin - il_frac * self.il_spacing_m * sin_a + xl_frac * self.xl_spacing_m * cos_a
        y = self.y_origin + il_frac * self.il_spacing_m * cos_a + xl_frac * self.xl_spacing_m * sin_a
        return x, y

    def nearest_il_xl(self, x: float, y: float) -> tuple[int, int]:
        """Convert world (x, y) to nearest integer (inline, crossline)."""
        il_f, xl_f = self.xy_to_il_xl(x, y)
        return round(il_f), round(xl_f)


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
        bin_grid: Optional bin-grid geometry for coordinate conversion.
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
    bin_grid: BinGridGeometry | None = None

    def xy_to_il_xl(self, x: float, y: float) -> tuple[float, float] | None:
        """Convert world (x, y) to absolute (inline_number, crossline_number).

        Returns ``None`` when no ``bin_grid`` is available — the volume has
        no geographic calibration, so fabricated default coordinates would
        be misleading.  Callers must surface "未标定" instead of fake values.
        """
        if self.bin_grid is None:
            return None
        il_frac, xl_frac = self.bin_grid.xy_to_il_xl(x, y)
        return (
            self.iline_start + il_frac * self.iline_step,
            self.xline_start + xl_frac * self.xline_step,
        )

    def il_xl_to_xy(self, iline: float, xline: float) -> tuple[float, float] | None:
        """Convert absolute (inline, crossline) numbers to world (x, y) coordinates.

        Returns ``None`` when no ``bin_grid`` is available (volume has no
        geographic calibration).
        """
        if self.bin_grid is None:
            return None
        il_step = self.iline_step if self.iline_step != 0 else 1
        xl_step = self.xline_step if self.xline_step != 0 else 1
        il_frac = (iline - self.iline_start) / il_step
        xl_frac = (xline - self.xline_start) / xl_step
        return self.bin_grid.il_xl_to_xy(il_frac, xl_frac)


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

    slice_type: Literal["inline", "crossline", "time", "arbitrary"]
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


class SeismicAnnotation(BaseModel):
    """A text annotation placed on a seismic profile panel."""

    text: str
    h_value: float
    v_value: float
    slice_type: str
    slice_position: int
    color: str = "#ffff00"
