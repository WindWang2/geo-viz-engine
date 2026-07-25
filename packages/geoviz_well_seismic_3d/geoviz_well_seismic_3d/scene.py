"""WellSeismicScene — primary public seam for joint well–seismic analysis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .depth_transform import DepthTransformState, select_depth_transform
from .fence import FenceExtraction, FenceSection, extract_fence_strip, well_to_well_path
from .models import TimeDepthTable, VerticalDomain, WellHead, WellTrajectory3D
from .probe import ProbeState, probe_from_fence_s
from .registration import VolumeRegistration
from .survey import Corner, SurveySpec, survey_from_corners
from .volume_access import VolumeAccess
from .well_geometry import project_well_trajectory

DEFAULT_CURVE_FALLBACK = ("GR", "DT", "RHOB")


@dataclass
class ProfileWellHit:
    """Well projected onto active fence for 2D assembly."""

    name: str
    s_m: float
    distance_m: float
    tops: list[tuple[str, float]]  # (top_name, z in active domain)
    curve_name: str | None = None
    curve_md: np.ndarray | None = None
    curve_values: np.ndarray | None = None


class WellSeismicScene:
    """Joint scene graph state (survey, wells, domain, fences, probe, volume)."""

    def __init__(self) -> None:
        self._survey: SurveySpec | None = None
        self._domain: VerticalDomain = VerticalDomain.TIME
        self._wells: list[WellHead] = []
        self._td_tables: dict[str, TimeDepthTable] = {}
        self._volume: VolumeAccess | None = None
        self._traj_cache: dict[str, WellTrajectory3D] | None = None
        self._fences: list[FenceSection] = []
        self._active_fence_id: str | None = None
        # Key: (fence_id, VerticalDomain value, n_along) so Time/Depth extracts coexist
        self._extract_cache: dict[tuple, FenceExtraction] = {}
        self._probe: ProbeState | None = None
        self._depth_transform: DepthTransformState = select_depth_transform()
        self._near_well_m: float = 100.0
        self._curve_names: list[str] = list(DEFAULT_CURVE_FALLBACK[:2])
        self._tops_by_well: dict[str, list[tuple[str, float]]] = {}
        self._curves_by_well: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]] = {}
        self.las_paths: list[str] = []
        self.preview_mode: bool = True  # #65 formalization flag
        self._registration: VolumeRegistration | None = None

    # ------------------------------------------------------------------
    # Survey
    # ------------------------------------------------------------------

    @property
    def survey(self) -> SurveySpec | None:
        return self._survey

    def set_survey(self, survey: SurveySpec) -> None:
        self._survey = survey
        self._invalidate_traj()
        self._extract_cache.clear()
        self._rebuild_registration()

    def set_survey_from_corners(
        self,
        p1: Corner,
        p2: Corner,
        p3: Corner,
        *,
        n_samples: int,
        dt_ms: float,
        t0_ms: float = 0.0,
    ) -> SurveySpec:
        survey = survey_from_corners(
            p1, p2, p3, n_samples=n_samples, dt_ms=dt_ms, t0_ms=t0_ms
        )
        self.set_survey(survey)
        return survey

    def validate_against_corners(
        self,
        p1: Corner,
        p2: Corner,
        p3: Corner,
        *,
        tol_m: float = 25.0,
        tol_il_xl: float = 1.0,
    ) -> tuple[bool, str]:
        if self._survey is None:
            return False, "No survey set"

        for label, corner in (("P1", p1), ("P2", p2), ("P3", p3)):
            il, xl, x, y = corner
            sx, sy = self._survey.il_xl_to_xy(float(il), float(xl))
            if abs(sx - x) > tol_m or abs(sy - y) > tol_m:
                return (
                    False,
                    f"Survey mismatch at {label}: expected XY≈({x}, {y}), "
                    f"survey gives ({sx:.3f}, {sy:.3f})",
                )
            sil, sxl = self._survey.xy_to_il_xl(float(x), float(y))
            if abs(sil - il) > tol_il_xl or abs(sxl - xl) > tol_il_xl:
                return (
                    False,
                    f"Survey mismatch at {label}: expected IL/XL≈({il}, {xl}), "
                    f"survey gives ({sil:.3f}, {sxl:.3f})",
                )
        return True, ""

    # ------------------------------------------------------------------
    # Vertical domain / depth
    # ------------------------------------------------------------------

    @property
    def vertical_domain(self) -> VerticalDomain:
        return self._domain

    @property
    def depth_transform(self) -> DepthTransformState:
        return self._depth_transform

    def set_depth_transform(self, state: DepthTransformState) -> None:
        self._depth_transform = state

    def set_vertical_domain(self, domain: VerticalDomain) -> None:
        if domain is self._domain:
            return
        self._domain = domain
        if domain is VerticalDomain.DEPTH:
            self._depth_transform = select_depth_transform(
                has_external_volume=False,
                v0_m_s=self._depth_transform.constant.v0_m_s,
            )
        self._invalidate_traj()
        self._extract_cache.clear()

    # ------------------------------------------------------------------
    # Wells
    # ------------------------------------------------------------------

    def set_wells(
        self,
        wells: list[WellHead],
        td_tables: dict[str, TimeDepthTable] | None = None,
    ) -> None:
        self._wells = list(wells)
        self._td_tables = dict(td_tables or {})
        self._invalidate_traj()

    def well_trajectories(self) -> dict[str, WellTrajectory3D]:
        if self._traj_cache is None:
            self._traj_cache = {}
            for well in self._wells:
                td = self._td_tables.get(well.name)
                traj = project_well_trajectory(well, domain=self._domain, td=td)
                if self._domain is VerticalDomain.DEPTH and traj.has_td is False:
                    # Depth path uses MD; reproject with domain DEPTH
                    traj = project_well_trajectory(
                        well, domain=VerticalDomain.DEPTH, td=td
                    )
                elif self._domain is VerticalDomain.DEPTH and td is not None:
                    # Prefer converting TWT path to depth via V0 if we had time
                    pass
                if self._domain is VerticalDomain.DEPTH and td is not None:
                    # Rebuild Z from MD via constant (MD as depth) already done
                    pass
                self._traj_cache[well.name] = traj
        return self._traj_cache

    def set_formation_tops(self, tops_by_well: dict[str, list[tuple[str, float]]]) -> None:
        """Tops as (name, z) already in active domain units (ms or m)."""
        self._tops_by_well = dict(tops_by_well)

    def set_well_curves(
        self, curves_by_well: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]]
    ) -> None:
        """curves_by_well[well][curve] = (md, values)."""
        self._curves_by_well = curves_by_well

    def set_curve_names(self, names: list[str]) -> None:
        self._curve_names = list(names)[:2]

    def set_near_well_distance_m(self, distance_m: float) -> None:
        self._near_well_m = float(distance_m)

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def set_volume_access(self, access: VolumeAccess | None) -> None:
        self._volume = access
        self._extract_cache.clear()
        self._rebuild_registration()

    @property
    def volume_access(self) -> VolumeAccess | None:
        return self._volume

    @property
    def registration(self) -> VolumeRegistration | None:
        """Survey ↔ loaded volume index map (preview-aware)."""
        return self._registration

    def _rebuild_registration(self) -> None:
        if self._survey is None or self._volume is None:
            self._registration = None
            return
        self._registration = VolumeRegistration.from_survey_and_shape(
            self._survey, self._volume.shape
        )

    def set_preview_mode(self, enabled: bool) -> None:
        """#65: mark whether current volume is a downsampled preview."""
        self.preview_mode = bool(enabled)

    def slice_inline(self, il_index: int):
        self._require_volume()
        return self._volume.slice_inline(il_index)

    def slice_crossline(self, xl_index: int):
        self._require_volume()
        return self._volume.slice_crossline(xl_index)

    def slice_time(self, sample_index: int):
        self._require_volume()
        return self._volume.slice_time(sample_index)

    # ------------------------------------------------------------------
    # Fences (#60–#61)
    # ------------------------------------------------------------------

    @property
    def fences(self) -> list[FenceSection]:
        return list(self._fences)

    @property
    def active_fence_id(self) -> str | None:
        return self._active_fence_id

    def add_fence(self, fence: FenceSection, *, activate: bool = True) -> FenceSection:
        self._fences.append(fence)
        if activate or self._active_fence_id is None:
            self._active_fence_id = fence.id
        return fence

    def set_active_fence(self, fence_id: str) -> None:
        if not any(f.id == fence_id for f in self._fences):
            raise KeyError(fence_id)
        self._active_fence_id = fence_id

    def remove_fence(self, fence_id: str) -> None:
        """Remove a fence by id; reassign active to last remaining if needed."""
        before = len(self._fences)
        self._fences = [f for f in self._fences if f.id != fence_id]
        if len(self._fences) == before:
            raise KeyError(fence_id)
        # Drop cache entries for this fence
        self._extract_cache = {
            k: v
            for k, v in self._extract_cache.items()
            if not (isinstance(k, tuple) and k and k[0] == fence_id)
        }
        if self._active_fence_id == fence_id:
            self._active_fence_id = self._fences[-1].id if self._fences else None

    def remove_active_fence(self) -> bool:
        """Remove the active fence. Returns False if none."""
        fid = self._active_fence_id
        if fid is None:
            return False
        self.remove_fence(fid)
        return True

    def set_fence_visible(self, fence_id: str, visible: bool) -> None:
        for f in self._fences:
            if f.id == fence_id:
                f.visible = visible
                return
        raise KeyError(fence_id)

    def add_well_to_well_fence(
        self, well_names: list[str], *, name: str = "Wells"
    ) -> FenceSection:
        xy = []
        by_name = {w.name: w for w in self._wells}
        for n in well_names:
            w = by_name.get(n)
            if w is None:
                raise KeyError(n)
            xy.append((w.x, w.y))
        fence = FenceSection(name=name, vertices_xy=well_to_well_path(xy))
        return self.add_fence(fence, activate=True)

    def active_fence(self) -> FenceSection | None:
        if self._active_fence_id is None:
            return None
        for f in self._fences:
            if f.id == self._active_fence_id:
                return f
        return None

    def extract_active_fence(
        self,
        *,
        n_along: int = 128,
        domain: VerticalDomain | None = None,
    ) -> FenceExtraction | None:
        """Extract active fence strip.

        domain:
            If set, sample axis uses this domain instead of scene ``vertical_domain``.
            Workbench 2D profile forces Time while 3D may stay on Depth (#122).
        """
        fence = self.active_fence()
        if fence is None or self._volume is None or self._survey is None:
            return None
        use_domain = domain if domain is not None else self._domain
        cache_key = (fence.id, use_domain, int(n_along))
        if cache_key in self._extract_cache:
            return self._extract_cache[cache_key]
        survey = self._survey
        nt = getattr(self._volume, "shape", (0, 0, 0))[2]
        if use_domain is VerticalDomain.TIME:
            saxis = survey.t0_ms + np.arange(nt) * survey.dt_ms
        else:
            saxis = self._depth_transform.constant.time_ms_to_depth_m(
                survey.t0_ms + np.arange(nt) * survey.dt_ms
            )
        if self._registration is None:
            self._rebuild_registration()
        ext = extract_fence_strip(
            self._volume,
            fence=fence,
            xy_to_il_xl=survey.xy_to_il_xl,
            iline_start=survey.iline_start,
            iline_step=survey.iline_step,
            xline_start=survey.xline_start,
            xline_step=survey.xline_step,
            n_along=n_along,
            sample_axis=np.asarray(saxis, dtype=np.float64),
            registration=self._registration,
        )
        self._extract_cache[cache_key] = ext
        return ext

    # ------------------------------------------------------------------
    # Active 2D assembly (#62)
    # ------------------------------------------------------------------

    def assemble_active_profile_wells(self) -> list[ProfileWellHit]:
        fence = self.active_fence()
        if fence is None:
            return []
        hits: list[ProfileWellHit] = []
        verts = fence.vertices_xy
        for well in self._wells:
            s, dist = _project_point_to_polyline(well.x, well.y, verts)
            if dist > self._near_well_m:
                continue
            curve_name, cmd, cval = self._pick_curve(well.name)
            hits.append(
                ProfileWellHit(
                    name=well.name,
                    s_m=s,
                    distance_m=dist,
                    tops=list(self._tops_by_well.get(well.name, [])),
                    curve_name=curve_name,
                    curve_md=cmd,
                    curve_values=cval,
                )
            )
        hits.sort(key=lambda h: h.s_m)
        return hits

    def _pick_curve(
        self, well_name: str
    ) -> tuple[str | None, np.ndarray | None, np.ndarray | None]:
        curves = self._curves_by_well.get(well_name, {})
        # Prefer configured names, then GR→DT→RHOB
        order = list(self._curve_names) + [c for c in DEFAULT_CURVE_FALLBACK if c not in self._curve_names]
        for name in order:
            # case-insensitive match
            for k, (md, val) in curves.items():
                if k.upper() == name.upper():
                    return k, md, val
        return None, None, None

    # ------------------------------------------------------------------
    # Probe (#64)
    # ------------------------------------------------------------------

    @property
    def probe(self) -> ProbeState | None:
        return self._probe

    def set_probe(self, s_m: float, z: float) -> ProbeState:
        fence = self.active_fence()
        if fence is None:
            raise RuntimeError("No active fence for probe")
        self._probe = probe_from_fence_s(
            s_m=s_m,
            z=z,
            vertices_xy=fence.vertices_xy,
            survey=self._survey,
            domain=self._domain.value,
        )
        return self._probe

    def probe_slice_indices(self) -> tuple[int, int, int] | None:
        if self._probe is None:
            return None
        if self._registration is not None:
            p = self._probe
            z = p.z
            if p.domain == "depth":
                # Convert depth m → time ms via inverse V0 for sample axis
                z = float(self._depth_transform.constant.depth_m_to_time_ms(z))
            return self._registration.world_xyz_to_volume(
                p.x, p.y, z, domain="time"
            )
        return self._probe.slice_indices(self._survey)

    def world_to_render_xyz(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """Map world XY + domain Z to volume/render index space."""
        if self._registration is not None:
            if self._domain is VerticalDomain.DEPTH:
                z = float(self._depth_transform.constant.depth_m_to_time_ms(z))
            vi, vx = self._registration.xy_to_volume_idx(x, y)
            vt = self._registration.time_ms_to_sample_idx(z)
            return float(vi), float(vx), float(vt)
        if self._survey is None:
            return x, y, z
        s = self._survey
        il, xl = s.xy_to_il_xl(x, y)
        il_idx = (il - s.iline_start) / (s.iline_step or 1)
        xl_idx = (xl - s.xline_start) / (s.xline_step or 1)
        t_idx = (z - s.t0_ms) / s.dt_ms if s.dt_ms else z
        return il_idx, xl_idx, t_idx

    def _require_volume(self) -> None:
        if self._volume is None:
            raise RuntimeError("No volume access set on WellSeismicScene")

    def _invalidate_traj(self) -> None:
        self._traj_cache = None


def _project_point_to_polyline(
    x: float, y: float, verts: np.ndarray
) -> tuple[float, float]:
    """Return (arc_length_s, distance) of closest point on polyline."""
    best_d = float("inf")
    best_s = 0.0
    cum = 0.0
    p = np.array([x, y], dtype=np.float64)
    for i in range(len(verts) - 1):
        a, b = verts[i], verts[i + 1]
        ab = b - a
        lab2 = float(np.dot(ab, ab)) or 1e-12
        t = float(np.clip(np.dot(p - a, ab) / lab2, 0.0, 1.0))
        q = a + t * ab
        d = float(np.linalg.norm(p - q))
        s = cum + t * float(np.linalg.norm(ab))
        if d < best_d:
            best_d = d
            best_s = s
        cum += float(np.linalg.norm(ab))
    return best_s, best_d
