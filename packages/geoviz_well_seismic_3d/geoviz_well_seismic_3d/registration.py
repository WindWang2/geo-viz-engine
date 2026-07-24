"""Map survey IL/XL/sample ↔ loaded volume indices (preview-safe)."""

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

    def il_xl_to_volume_idx(self, iline: float, xline: float) -> tuple[float, float]:
        """Fractional volume indices (il_idx, xl_idx) in [0, n-1]."""
        s = self.survey
        il_step = s.iline_step or 1
        xl_step = s.xline_step or 1
        # Full-grid fractional index along survey axes
        il_frac = (iline - s.iline_start) / il_step  # 0 .. n_inlines-1 full
        xl_frac = (xline - s.xline_start) / xl_step
        full_il = max(s.n_inlines - 1, 1)
        full_xl = max(s.n_crosslines - 1, 1)
        vi = il_frac / full_il * max(self.n_inline - 1, 0)
        vx = xl_frac / full_xl * max(self.n_crossline - 1, 0)
        return vi, vx

    def xy_to_volume_idx(self, x: float, y: float) -> tuple[float, float]:
        il, xl = self.survey.xy_to_il_xl(x, y)
        return self.il_xl_to_volume_idx(il, xl)

    def time_ms_to_sample_idx(self, time_ms: float) -> float:
        s = self.survey
        if s.dt_ms and s.dt_ms > 0:
            full_t = (time_ms - s.t0_ms) / s.dt_ms  # 0 .. n_samples-1 full
        else:
            full_t = time_ms
        full_nt = max(s.n_samples - 1, 1)
        return full_t / full_nt * max(self.n_sample - 1, 0)

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
        if domain == "time":
            vt = self.time_ms_to_sample_idx(z)
        else:
            # depth m: map via full survey sample axis proportion if dt known
            vt = self.time_ms_to_sample_idx(z)  # caller should convert depth→time first
        return self.clamp_indices(vi, vx, vt)
