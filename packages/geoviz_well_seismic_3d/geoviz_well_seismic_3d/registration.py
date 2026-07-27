"""Map survey IL/XL/sample ↔ loaded volume indices (preview-safe).

Wayfinder #81/#84: survey axes must match volume axes
``(n_inline, n_crossline, n_sample)``. Registration only scales full-grid
survey indices onto a downsampled preview shape.
"""

from __future__ import annotations

from dataclasses import dataclass

from .survey import SurveySpec


@dataclass(frozen=True)
class VolumeRegistration:
    """Linear map from survey absolute IL/XL/time to volume array indices.

    When the loaded cube is a downsampled preview, ``n_*`` match the array shape
    while survey still describes full geometry. Indices are scaled accordingly.
    """

    survey: SurveySpec
    n_inline: int
    n_crossline: int
    n_sample: int

    @classmethod
    def from_survey_and_shape(
        cls,
        survey: SurveySpec,
        shape: tuple[int, int, int],
    ) -> VolumeRegistration:
        ni, nx, nt = (int(shape[0]), int(shape[1]), int(shape[2]))
        return cls(
            survey=survey,
            n_inline=ni,
            n_crossline=nx,
            n_sample=nt,
        )

    def il_xl_to_volume_idx(self, iline: float, xline: float) -> tuple[float, float]:
        """Fractional volume indices (il_idx, xl_idx) in [0, n-1]."""
        s = self.survey
        il_step = s.iline_step or 1
        xl_step = s.xline_step or 1
        il_frac = (float(iline) - s.iline_start) / il_step  # 0 .. n_inlines-1 full
        xl_frac = (float(xline) - s.xline_start) / xl_step
        full_il = max(s.n_inlines - 1, 1)
        full_xl = max(s.n_crosslines - 1, 1)
        vi = il_frac / full_il * max(self.n_inline - 1, 0)
        vx = xl_frac / full_xl * max(self.n_crossline - 1, 0)
        return vi, vx

    def xy_to_volume_idx(self, x: float, y: float) -> tuple[float, float]:
        il, xl = self.survey.xy_to_il_xl(float(x), float(y))
        return self.il_xl_to_volume_idx(il, xl)

    def time_ms_to_sample_idx(self, time_ms: float) -> float:
        s = self.survey
        if s.dt_ms and s.dt_ms > 0:
            full_t = (float(time_ms) - s.t0_ms) / s.dt_ms
        else:
            full_t = float(time_ms)
        full_nt = max(s.n_samples - 1, 1)
        return full_t / full_nt * max(self.n_sample - 1, 0)

    def sample_idx_to_time_ms(self, sample_index: float) -> float:
        """Map a loaded/preview sample index back to represented TWT ms."""
        preview_nt = max(self.n_sample - 1, 1)
        full_index = (
            float(sample_index)
            / preview_nt
            * max(self.survey.n_samples - 1, 0)
        )
        return float(
            self.survey.t0_ms + full_index * self.survey.dt_ms
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
