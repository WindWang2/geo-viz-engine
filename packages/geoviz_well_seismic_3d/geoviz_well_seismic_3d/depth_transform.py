"""Depth transform priority chain (#63 / grill E)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import numpy as np


class DepthTransformKind(str, Enum):
    EXTERNAL_VOLUME = "external_volume"
    CONSTANT_V0 = "constant_v0"
    WELL_TZ_FIELD = "well_tz_field"  # reserved


@dataclass
class ConstantVelocityDepth:
    """Z_depth_m = V0_m_s * TWT_s / 2."""

    v0_m_s: float = 3000.0

    def time_ms_to_depth_m(self, time_ms: float | np.ndarray) -> float | np.ndarray:
        return (np.asarray(time_ms, dtype=np.float64) * 1e-3) * self.v0_m_s / 2.0

    def depth_m_to_time_ms(self, depth_m: float | np.ndarray) -> float | np.ndarray:
        return (np.asarray(depth_m, dtype=np.float64) * 2.0 / self.v0_m_s) * 1e3


@dataclass
class DepthTransformState:
    """Active depth transform selection."""

    kind: DepthTransformKind = DepthTransformKind.CONSTANT_V0
    constant: ConstantVelocityDepth = None  # type: ignore[assignment]
    approximate_warning: str | None = None

    def __post_init__(self) -> None:
        if self.constant is None:
            self.constant = ConstantVelocityDepth()
        if self.kind is DepthTransformKind.CONSTANT_V0:
            self.approximate_warning = (
                f"Depth uses constant V0={self.constant.v0_m_s:.0f} m/s (approximate)"
            )
        elif self.kind is DepthTransformKind.WELL_TZ_FIELD:
            self.approximate_warning = "Well T–Z field not implemented; using V0"
            self.kind = DepthTransformKind.CONSTANT_V0


def select_depth_transform(
    *,
    has_external_volume: bool = False,
    v0_m_s: float = 3000.0,
) -> DepthTransformState:
    """Priority: external volume → constant V0 → (reserved well T–Z)."""
    if has_external_volume:
        return DepthTransformState(
            kind=DepthTransformKind.EXTERNAL_VOLUME,
            constant=ConstantVelocityDepth(v0_m_s=v0_m_s),
            approximate_warning=None,
        )
    return DepthTransformState(
        kind=DepthTransformKind.CONSTANT_V0,
        constant=ConstantVelocityDepth(v0_m_s=v0_m_s),
    )
