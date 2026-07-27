"""Domain models for the well–seismic joint scene."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType

import numpy as np

JointWellId = NewType("JointWellId", str)
MAX_TIME_SLICES = 8


@dataclass(frozen=True)
class JointDisplaySettings:
    """Project-persisted color scales and shared well trajectory width."""

    seismic_color_scale: str = "blue-white-red"
    gr_color_scale: str = "viridis"
    well_width_px: int = 5

    def __post_init__(self) -> None:
        if not 2 <= int(self.well_width_px) <= 10:
            raise ValueError("well_width_px must be between 2 and 10")


@dataclass(frozen=True)
class TimeSliceState:
    """One persisted horizontal seismic slice in TWT milliseconds."""

    time_ms: float
    visible: bool = True

    def __post_init__(self) -> None:
        if not np.isfinite(float(self.time_ms)):
            raise ValueError("time_ms must be finite")


@dataclass(frozen=True)
class OrthogonalSliceState:
    """Joint-scene state for one IL, one XL and a Time slice stack."""

    inline_index: int | None = None
    crossline_index: int | None = None
    time_slices: tuple[TimeSliceState, ...] = ()
    active_time_ms: float | None = None
    time_opacity: float = 0.8

    def __post_init__(self) -> None:
        object.__setattr__(self, "time_slices", tuple(self.time_slices))
        if len(self.time_slices) > MAX_TIME_SLICES:
            raise ValueError(
                f"time_slices cannot contain more than {MAX_TIME_SLICES} items"
            )
        opacity = float(self.time_opacity)
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("time_opacity must be between 0 and 1")
        if self.active_time_ms is not None and not np.isfinite(
            float(self.active_time_ms)
        ):
            raise ValueError("active_time_ms must be finite")


class VerticalDomain(str, Enum):
    """Shared vertical axis for the joint scene."""

    TIME = "time"
    DEPTH = "depth"


@dataclass(frozen=True)
class WellHead:
    """Well surface/bottom location in Local Rectangular XY (metres)."""

    name: str
    x: float
    y: float
    bottom_x: float
    bottom_y: float
    total_depth_m: float
    kb_m: float = 0.0
    id: JointWellId | None = None


@dataclass
class TimeDepthTable:
    """TIME (ms) ↔ MD (m) pairs for one well (SMI-style TD)."""

    well_name: str
    time_ms: np.ndarray
    md_m: np.ndarray

    def __post_init__(self) -> None:
        self.time_ms = np.asarray(self.time_ms, dtype=np.float64).reshape(-1)
        self.md_m = np.asarray(self.md_m, dtype=np.float64).reshape(-1)
        if self.time_ms.size != self.md_m.size:
            raise ValueError("time_ms and md_m must have the same length")
        if self.time_ms.size < 2:
            raise ValueError("TimeDepthTable requires at least two samples")

    def md_to_time_ms(self, md: float | np.ndarray) -> float | np.ndarray:
        """Interpolate MD → TWT (ms). Extrapolates with edge values."""
        return np.interp(md, self.md_m, self.time_ms)

    def time_ms_to_md(self, twt: float | np.ndarray) -> float | np.ndarray:
        """Interpolate TWT (ms) → MD. Extrapolates with edge values."""
        return np.interp(twt, self.time_ms, self.md_m)


@dataclass
class WellTrajectory3D:
    """Well path in scene coordinates (x, y, z) for the active vertical domain."""

    name: str
    points: np.ndarray  # (N, 3) float64
    has_td: bool
    warning: str | None = None

    def __post_init__(self) -> None:
        self.points = np.asarray(self.points, dtype=np.float64)
        if self.points.ndim != 2 or self.points.shape[1] != 3:
            raise ValueError("points must have shape (N, 3)")


@dataclass
class WellGrTrajectory:
    """Well path samples paired with GR values for color rendering."""

    id: JointWellId
    name: str
    display_name: str
    points: np.ndarray
    gr_values: np.ndarray

    def __post_init__(self) -> None:
        self.points = np.asarray(self.points, dtype=np.float64)
        self.gr_values = np.asarray(
            self.gr_values, dtype=np.float64
        ).reshape(-1)
        if self.points.ndim != 2 or self.points.shape[1] != 3:
            raise ValueError("points must have shape (N, 3)")
        if len(self.points) != len(self.gr_values):
            raise ValueError("points and gr_values must have the same length")
