"""Map survey IL/XL/sample ↔ loaded volume indices (preview-safe).

Wayfinder #81/#84: survey axes must match volume axes
``(n_inline, n_crossline, n_sample)``. A downsampled preview produced by
``SeismicLoader.get_volume_downsampled(factor=...)`` samples native indices
``range(0, n, stride)``, so preview index *p* corresponds **exactly** to
native index ``p * stride``. Registration therefore carries the per-axis
stride explicitly and maps through it — never through an endpoint-normalised
shape ratio, which drifts by up to one sample on non-divisible (odd) sizes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .survey import SurveySpec


def _infer_stride(native: int, loaded: int) -> int:
    """Stride implied by a loaded axis length (ceil(n/f) == loaded)."""
    native = max(1, int(native))
    loaded = max(1, int(loaded))
    if loaded >= native:
        return 1
    stride = int(math.ceil(native / loaded))
    # Grow until the implied preview length does not exceed the loaded one.
    while math.ceil(native / stride) > loaded:
        stride += 1
    return stride


@dataclass(frozen=True)
class VolumeRegistration:
    """Linear map from survey absolute IL/XL/time to volume array indices.

    ``n_*`` match the loaded array shape (preview or native) while *survey*
    still describes the full native geometry. ``strides`` is the per-axis
    ``(inline, crossline, sample)`` downsample stride of the loaded cube
    relative to the native survey grid, so::

        native_index = preview_index * stride
        preview_index = native_index / stride

    is exact at every sampled position and invertible on the stride lattice.
    """

    survey: SurveySpec
    n_inline: int
    n_crossline: int
    n_sample: int
    strides: tuple[int, int, int] = (1, 1, 1)

    def __post_init__(self) -> None:
        strides = tuple(int(s) for s in self.strides)
        if len(strides) != 3 or any(s < 1 for s in strides):
            raise ValueError(f"strides must be three positive ints: {strides}")
        object.__setattr__(self, "strides", strides)
        native = (
            int(self.survey.n_inlines),
            int(self.survey.n_crosslines),
            int(self.survey.n_samples),
        )
        loaded = (int(self.n_inline), int(self.n_crossline), int(self.n_sample))
        for axis, (n_nat, n_load, stride) in enumerate(
            zip(native, loaded, strides, strict=True)
        ):
            if n_load < 1 or n_load > n_nat:
                raise ValueError(
                    f"axis {axis}: loaded size {n_load} outside native 1..{n_nat}"
                )
            if math.ceil(n_nat / stride) != n_load:
                raise ValueError(
                    f"axis {axis}: stride {stride} implies "
                    f"{math.ceil(n_nat / stride)} samples, loaded {n_load}"
                )

    @classmethod
    def from_survey_and_shape(
        cls,
        survey: SurveySpec,
        shape: tuple[int, int, int],
        strides: tuple[int, int, int] | None = None,
    ) -> VolumeRegistration:
        ni, nx, nt = (int(shape[0]), int(shape[1]), int(shape[2]))
        if strides is None:
            # Legacy caller: infer the stride the preview length implies.
            strides = (
                _infer_stride(survey.n_inlines, ni),
                _infer_stride(survey.n_crosslines, nx),
                _infer_stride(survey.n_samples, nt),
            )
        return cls(
            survey=survey,
            n_inline=ni,
            n_crossline=nx,
            n_sample=nt,
            strides=strides,
        )

    # ------------------------------------------------------------------
    # Survey coordinates → loaded volume indices
    # ------------------------------------------------------------------
    def il_xl_to_volume_idx(
        self, iline: float | np.ndarray, xline: float | np.ndarray
    ) -> tuple[float, float] | tuple[np.ndarray, np.ndarray]:
        """Fractional volume indices (il_idx, xl_idx), exact on the stride lattice."""
        s = self.survey
        il_step = s.iline_step or 1
        xl_step = s.xline_step or 1
        il_arr = np.asarray(iline, dtype=np.float64)
        xl_arr = np.asarray(xline, dtype=np.float64)
        native_il = (il_arr - s.iline_start) / il_step  # 0 .. n_inlines-1
        native_xl = (xl_arr - s.xline_start) / xl_step
        vi = native_il / self.strides[0]
        vx = native_xl / self.strides[1]
        if vi.ndim == 0:
            return float(vi), float(vx)
        return vi, vx

    def xy_to_volume_idx(
        self, x: float | np.ndarray, y: float | np.ndarray
    ) -> tuple[float, float] | tuple[np.ndarray, np.ndarray]:
        il, xl = self.survey.xy_to_il_xl(x, y)
        return self.il_xl_to_volume_idx(il, xl)

    def time_ms_to_sample_idx(self, time_ms: float | np.ndarray) -> float | np.ndarray:
        s = self.survey
        t = np.asarray(time_ms, dtype=np.float64)
        if not (s.dt_ms and s.dt_ms > 0):
            # #147: treating TWT milliseconds as sample indices silently maps
            # 2500 ms to sample 2500. Fail closed — the sample domain is
            # unusable without a parsed sample interval.
            raise ValueError(
                "survey dt_ms is missing or non-positive; cannot convert "
                "TWT ms to sample indices (fail-closed, #147)"
            )
        native_t = (t - s.t0_ms) / s.dt_ms
        out = native_t / self.strides[2]
        if out.ndim == 0:
            return float(out)
        return out

    def sample_idx_to_time_ms(self, sample_index: float) -> float:
        """Map a loaded/preview sample index back to represented TWT ms."""
        native_index = float(sample_index) * self.strides[2]
        return float(self.survey.t0_ms + native_index * self.survey.dt_ms)

    # ------------------------------------------------------------------
    # Stride lattice helpers
    # ------------------------------------------------------------------
    def sample_idx_to_native(self, sample_index: int) -> int:
        return int(sample_index) * self.strides[2]

    def native_to_sample_idx(self, native_index: float) -> float:
        return float(native_index) / self.strides[2]

    def volume_idx_to_il_xl(self, il_idx: float, xl_idx: float) -> tuple[float, float]:
        """Inverse of :meth:`il_xl_to_volume_idx` (loaded indices → survey numbers)."""
        s = self.survey
        native_il = float(il_idx) * self.strides[0]
        native_xl = float(xl_idx) * self.strides[1]
        return (
            s.iline_start + native_il * (s.iline_step or 1),
            s.xline_start + native_xl * (s.xline_step or 1),
        )

    def clamp_indices(self, il_idx: float, xl_idx: float, t_idx: float) -> tuple[int, int, int]:
        return (
            int(max(0, min(self.n_inline - 1, round(il_idx)))),
            int(max(0, min(self.n_crossline - 1, round(xl_idx)))),
            int(max(0, min(self.n_sample - 1, round(t_idx)))),
        )

    def world_xyz_to_volume(
        self, x: float, y: float, z: float, *, domain: str = "time"
    ) -> tuple[int, int, int]:
        vi, vx = self.xy_to_volume_idx(x, y)
        vt = self.time_ms_to_sample_idx(z)
        return self.clamp_indices(vi, vx, vt)
