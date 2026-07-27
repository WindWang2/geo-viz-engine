"""Domain models for the well–seismic joint scene."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType

import numpy as np

JointWellId = NewType("JointWellId", str)


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
