"""Shared probe state for 2D↔3D↔slice linkage (#64)."""

from __future__ import annotations

from dataclasses import dataclass

from .survey import SurveySpec


@dataclass
class ProbeState:
    """Probe on active fence: arc-length s and vertical z."""

    s_m: float
    z: float  # TWT ms or depth m depending on domain
    x: float = 0.0
    y: float = 0.0
    il: float = 0.0
    xl: float = 0.0
    domain: str = "time"

    def slice_indices(
        self,
        survey: SurveySpec | None,
    ) -> tuple[int, int, int]:
        """Nearest orthogonal slice indices (il_idx, xl_idx, sample_idx)."""
        if survey is None:
            return 0, 0, int(round(self.z))
        il_idx = int(round((self.il - survey.iline_start) / (survey.iline_step or 1)))
        xl_idx = int(round((self.xl - survey.xline_start) / (survey.xline_step or 1)))
        if survey.dt_ms and survey.dt_ms > 0 and self.domain == "time":
            t_idx = int(round((self.z - survey.t0_ms) / survey.dt_ms))
        else:
            t_idx = int(round(self.z))
        return (
            max(0, min(survey.n_inlines - 1, il_idx)),
            max(0, min(survey.n_crosslines - 1, xl_idx)),
            max(0, min(survey.n_samples - 1, t_idx)),
        )


def probe_from_fence_s(
    *,
    s_m: float,
    z: float,
    vertices_xy,
    survey: SurveySpec | None,
    domain: str = "time",
) -> ProbeState:
    """Map arc-length along fence to world XY and IL/XL."""
    import numpy as np

    verts = np.asarray(vertices_xy, dtype=np.float64).reshape(-1, 2)
    seg = np.diff(verts, axis=0)
    seg_len = np.linalg.norm(seg, axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    total = float(cum[-1]) or 1.0
    s = float(np.clip(s_m, 0.0, total))
    j = int(np.searchsorted(cum, s, side="right") - 1)
    j = max(0, min(j, len(seg_len) - 1))
    local = (s - cum[j]) / (seg_len[j] if seg_len[j] > 1e-12 else 1.0)
    xy = verts[j] + local * (verts[j + 1] - verts[j])
    x, y = float(xy[0]), float(xy[1])
    il = xl = 0.0
    if survey is not None:
        il, xl = survey.xy_to_il_xl(x, y)
    return ProbeState(s_m=s, z=z, x=x, y=y, il=il, xl=xl, domain=domain)
