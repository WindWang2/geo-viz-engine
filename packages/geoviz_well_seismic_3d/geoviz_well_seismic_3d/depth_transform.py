"""Depth transform priority chain (#63 / grill E).

Fail-closed policy: without an authoritative time-depth transform (velocity
model, checkshot fit, or depth-converted cube) the Depth domain is
**unavailable**. A constant-V0 conversion is only ever installed through an
explicit :func:`select_depth_transform(constant_v0=True)` opt-in so callers
(tests / synthetic demos) cannot mistake approximate scaling for depth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class DepthTransformKind(str, Enum):
    NONE = "none"  # no authoritative transform → Depth unavailable
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
    """Active depth transform selection.

    ``kind == NONE`` means no transform is available; Depth-domain features
    must refuse to run rather than fake depth with uniform scaling.
    """

    kind: DepthTransformKind = DepthTransformKind.NONE
    constant: ConstantVelocityDepth | None = None
    approximate_warning: str | None = None

    def __post_init__(self) -> None:
        if self.kind is DepthTransformKind.CONSTANT_V0 and self.constant is None:
            self.constant = ConstantVelocityDepth()
        if self.kind is DepthTransformKind.CONSTANT_V0:
            self.approximate_warning = (
                f"Depth uses constant V0={self.constant.v0_m_s:.0f} m/s (approximate)"
            )
        elif self.kind is DepthTransformKind.WELL_TZ_FIELD:
            # Reserved slot: not implemented; degrade explicitly to V0 with a
            # warning so callers can surface the approximation.
            self.kind = DepthTransformKind.CONSTANT_V0
            if self.constant is None:
                self.constant = ConstantVelocityDepth()
            self.approximate_warning = "Well T–Z field not implemented; using V0"
        elif self.kind is DepthTransformKind.NONE:
            self.constant = None
            self.approximate_warning = None

    @property
    def available(self) -> bool:
        """True when a real (or explicitly opted-in approximate) transform exists."""
        return self.kind is not DepthTransformKind.NONE

    def time_ms_to_depth_m(self, time_ms: float | np.ndarray) -> float | np.ndarray:
        if not self.available or self.constant is None:
            raise RuntimeError("no depth transform available")
        return self.constant.time_ms_to_depth_m(time_ms)

    def depth_m_to_time_ms(self, depth_m: float | np.ndarray) -> float | np.ndarray:
        if not self.available or self.constant is None:
            raise RuntimeError("no depth transform available")
        return self.constant.depth_m_to_time_ms(depth_m)


def select_depth_transform(
    *,
    has_external_volume: bool = False,
    v0_m_s: float = 3000.0,
    constant_v0: bool = False,
) -> DepthTransformState:
    """Priority: external volume → explicit constant V0 → none.

    The default return is an *unavailable* transform (fail-closed): Depth is
    only usable after a caller explicitly opts into an approximation or
    supplies an external depth-converted volume.
    """
    if has_external_volume:
        return DepthTransformState(
            kind=DepthTransformKind.EXTERNAL_VOLUME,
            constant=ConstantVelocityDepth(v0_m_s=v0_m_s),
            approximate_warning=None,
        )
    if constant_v0:
        return DepthTransformState(
            kind=DepthTransformKind.CONSTANT_V0,
            constant=ConstantVelocityDepth(v0_m_s=v0_m_s),
        )
    return DepthTransformState(kind=DepthTransformKind.NONE)
