"""WellSeismicScene — primary public seam for joint well–seismic analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import numpy as np

from .depth_transform import DepthTransformState, select_depth_transform
from .fence import FenceExtraction, FenceSection, extract_fence_strip, well_to_well_path
from .models import (
    JointDisplaySettings,
    JointWellId,
    MAX_TIME_SLICES,
    OrthogonalSliceState,
    TimeDepthTable,
    TimeSliceState,
    VerticalDomain,
    WellGrTrajectory,
    WellHead,
    WellTrajectory3D,
)
from .probe import ProbeState, probe_from_fence_s
from .registration import VolumeRegistration
from .survey import Corner, SurveySpec, survey_from_corners
from .volume_access import VolumeAccess
from .well_geometry import project_well_trajectory

DEFAULT_CURVE_FALLBACK = ("GR", "DT", "RHOB")


@dataclass
class ProfileWellHit:
    """Well projected onto active fence for 2D assembly."""

    id: JointWellId
    name: str
    display_name: str
    s_m: float
    distance_m: float
    tops: list[tuple[str, float]]  # (top_name, z in active domain)
    curve_name: str | None = None
    curve_md: np.ndarray | None = None
    curve_z: np.ndarray | None = None
    curve_values: np.ndarray | None = None


@dataclass(frozen=True)
class JointWellPresentation:
    """Stable well identity and user-facing label for joint-workbench chrome."""

    id: JointWellId
    name: str
    display_name: str
    visible: bool


class WellSeismicScene:
    """Joint scene graph state (survey, wells, domain, fences, probe, volume)."""

    def __init__(self) -> None:
        self._survey: SurveySpec | None = None
        self._domain: VerticalDomain = VerticalDomain.TIME
        self._display_settings = JointDisplaySettings()
        self._orthogonal_slice_state = OrthogonalSliceState()
        self._slice_state_warning = ""
        self._wells: list[WellHead] = []
        self._well_ids: list[JointWellId] = []
        self._well_visibility: dict[JointWellId, bool] = {}
        self._td_tables: dict[str, TimeDepthTable] = {}
        self._volume: VolumeAccess | None = None
        self._traj_cache: dict[JointWellId, WellTrajectory3D] | None = None
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
        self._reconcile_orthogonal_slice_state()

    def set_survey_from_corners(
        self,
        p1: Corner,
        p2: Corner,
        p3: Corner,
        *,
        n_samples: int,
        dt_ms: float,
        t0_ms: float = 0.0,
        iline_step: int | None = None,
        xline_step: int | None = None,
        n_inlines: int | None = None,
        n_crosslines: int | None = None,
    ) -> SurveySpec:
        survey = survey_from_corners(
            p1,
            p2,
            p3,
            n_samples=n_samples,
            dt_ms=dt_ms,
            t0_ms=t0_ms,
            iline_step=iline_step,
            xline_step=xline_step,
            n_inlines=n_inlines,
            n_crosslines=n_crosslines,
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
    def display_settings(self) -> JointDisplaySettings:
        return self._display_settings

    def set_display_settings(self, settings: JointDisplaySettings) -> None:
        self._display_settings = settings

    @property
    def orthogonal_slice_state(self) -> OrthogonalSliceState:
        return self._orthogonal_slice_state

    @property
    def slice_state_warning(self) -> str:
        return self._slice_state_warning

    def restore_orthogonal_slice_state(
        self, state: OrthogonalSliceState
    ) -> None:
        """Restore project state now; reconcile once survey/volume are ready."""
        self._orthogonal_slice_state = state
        self._reconcile_orthogonal_slice_state()

    def set_orthogonal_slice_indices(
        self,
        *,
        inline_index: int | None = None,
        crossline_index: int | None = None,
    ) -> None:
        state = self._orthogonal_slice_state
        il = state.inline_index if inline_index is None else int(inline_index)
        xl = (
            state.crossline_index
            if crossline_index is None
            else int(crossline_index)
        )
        registration = self._registration
        if registration is not None:
            il = max(0, min(registration.n_inline - 1, int(il or 0)))
            xl = max(0, min(registration.n_crossline - 1, int(xl or 0)))
        self._orthogonal_slice_state = OrthogonalSliceState(
            inline_index=il,
            crossline_index=xl,
            time_slices=state.time_slices,
            active_time_ms=state.active_time_ms,
            time_opacity=state.time_opacity,
        )

    def add_time_slice(self, time_ms: float) -> float:
        """Add or activate a snapped Time slice; raise at the eight-item cap."""
        snapped = self._snap_time_ms(time_ms)
        state = self._orthogonal_slice_state
        existing = self._find_time_slice(snapped)
        if existing is not None:
            self._replace_slice_state(active_time_ms=existing.time_ms)
            return existing.time_ms
        if len(state.time_slices) >= MAX_TIME_SLICES:
            raise ValueError(
                f"Time slice stack is limited to {MAX_TIME_SLICES} items"
            )
        slices = tuple(
            sorted(
                (*state.time_slices, TimeSliceState(snapped)),
                key=lambda item: item.time_ms,
            )
        )
        self._replace_slice_state(
            time_slices=slices,
            active_time_ms=snapped,
        )
        return snapped

    def update_time_slice(
        self, current_time_ms: float, new_time_ms: float
    ) -> float:
        """Move one slice, merging with an existing slice after snapping."""
        state = self._orthogonal_slice_state
        current = self._find_time_slice(current_time_ms)
        if current is None:
            raise KeyError(current_time_ms)
        snapped = self._snap_time_ms(new_time_ms)
        target = self._find_time_slice(snapped)
        remaining = tuple(
            item
            for item in state.time_slices
            if item is not current and item is not target
        )
        moved = target or TimeSliceState(snapped, visible=current.visible)
        slices = tuple(
            sorted((*remaining, moved), key=lambda item: item.time_ms)
        )
        self._replace_slice_state(
            time_slices=slices,
            active_time_ms=moved.time_ms,
        )
        return moved.time_ms

    def remove_time_slice(self, time_ms: float) -> bool:
        state = self._orthogonal_slice_state
        current = self._find_time_slice(time_ms)
        if current is None or len(state.time_slices) <= 1:
            return False
        slices = tuple(item for item in state.time_slices if item is not current)
        active = state.active_time_ms
        if self._same_time(active, current.time_ms):
            active = slices[0].time_ms
        self._replace_slice_state(
            time_slices=slices,
            active_time_ms=active,
        )
        return True

    def set_time_slice_visible(
        self, time_ms: float, visible: bool
    ) -> None:
        current = self._find_time_slice(time_ms)
        if current is None:
            raise KeyError(time_ms)
        slices = tuple(
            TimeSliceState(item.time_ms, bool(visible))
            if item is current
            else item
            for item in self._orthogonal_slice_state.time_slices
        )
        self._replace_slice_state(time_slices=slices)

    def set_active_time_slice(self, time_ms: float) -> None:
        current = self._find_time_slice(time_ms)
        if current is None:
            raise KeyError(time_ms)
        self._replace_slice_state(active_time_ms=current.time_ms)

    def set_time_slice_opacity(self, opacity: float) -> None:
        self._replace_slice_state(
            time_opacity=max(0.0, min(1.0, float(opacity)))
        )

    def move_active_time_slice_to_sample(self, sample_index: int) -> float:
        """Compatibility/probe seam: move only ActiveTimeSlice."""
        registration = self._registration
        state = self._orthogonal_slice_state
        if registration is None or state.active_time_ms is None:
            raise RuntimeError("Time slice stack is not ready")
        sample = max(0, min(registration.n_sample - 1, int(sample_index)))
        return self.update_time_slice(
            state.active_time_ms,
            registration.sample_idx_to_time_ms(sample),
        )

    def orthogonal_slice_render_state(
        self,
    ) -> tuple[
        int,
        int,
        tuple[tuple[int, bool], ...],
        int,
        float,
    ] | None:
        """Return renderer-ready preview indices for the orthogonal planes."""
        registration = self._registration
        state = self._orthogonal_slice_state
        if (
            registration is None
            or state.inline_index is None
            or state.crossline_index is None
            or not state.time_slices
            or state.active_time_ms is None
        ):
            return None
        times = tuple(
            (
                registration.clamp_indices(
                    state.inline_index,
                    state.crossline_index,
                    registration.time_ms_to_sample_idx(item.time_ms),
                )[2],
                item.visible,
            )
            for item in state.time_slices
        )
        active = registration.clamp_indices(
            state.inline_index,
            state.crossline_index,
            registration.time_ms_to_sample_idx(state.active_time_ms),
        )[2]
        return (
            state.inline_index,
            state.crossline_index,
            times,
            active,
            state.time_opacity,
        )

    def _replace_slice_state(self, **changes) -> None:
        state = self._orthogonal_slice_state
        values = {
            "inline_index": state.inline_index,
            "crossline_index": state.crossline_index,
            "time_slices": state.time_slices,
            "active_time_ms": state.active_time_ms,
            "time_opacity": state.time_opacity,
        }
        values.update(changes)
        self._orthogonal_slice_state = OrthogonalSliceState(**values)

    def _find_time_slice(
        self, time_ms: float | None
    ) -> TimeSliceState | None:
        if time_ms is None:
            return None
        for item in self._orthogonal_slice_state.time_slices:
            if self._same_time(item.time_ms, time_ms):
                return item
        return None

    @staticmethod
    def _same_time(left: float | None, right: float | None) -> bool:
        if left is None or right is None:
            return False
        return bool(np.isclose(float(left), float(right), atol=1e-7))

    def _snap_time_ms(self, time_ms: float) -> float:
        registration = self._registration
        if registration is None:
            if not np.isfinite(float(time_ms)):
                raise ValueError("time_ms must be finite")
            return float(time_ms)
        sample = registration.clamp_indices(
            0,
            0,
            registration.time_ms_to_sample_idx(float(time_ms)),
        )[2]
        return registration.sample_idx_to_time_ms(sample)

    def _reconcile_orthogonal_slice_state(self) -> None:
        registration = self._registration
        if registration is None:
            return
        state = self._orthogonal_slice_state
        il = (
            registration.n_inline // 2
            if state.inline_index is None
            else max(
                0,
                min(registration.n_inline - 1, int(state.inline_index)),
            )
        )
        xl = (
            registration.n_crossline // 2
            if state.crossline_index is None
            else max(
                0,
                min(registration.n_crossline - 1, int(state.crossline_index)),
            )
        )
        survey = registration.survey
        lower = float(survey.t0_ms)
        upper = float(
            survey.t0_ms
            + max(survey.n_samples - 1, 0) * survey.dt_ms
        )
        dropped = 0
        by_sample: dict[int, TimeSliceState] = {}
        for item in state.time_slices:
            if not lower <= item.time_ms <= upper:
                dropped += 1
                continue
            sample = registration.clamp_indices(
                il,
                xl,
                registration.time_ms_to_sample_idx(item.time_ms),
            )[2]
            snapped = registration.sample_idx_to_time_ms(sample)
            if sample not in by_sample:
                by_sample[sample] = TimeSliceState(
                    snapped, visible=item.visible
                )
        slices = tuple(
            sorted(by_sample.values(), key=lambda item: item.time_ms)
        )[:MAX_TIME_SLICES]
        if not slices:
            middle = registration.n_sample // 2
            slices = (
                TimeSliceState(
                    registration.sample_idx_to_time_ms(middle)
                ),
            )
        active = state.active_time_ms
        active_item = None
        if active is not None and lower <= active <= upper:
            active_sample = registration.clamp_indices(
                il,
                xl,
                registration.time_ms_to_sample_idx(active),
            )[2]
            active_ms = registration.sample_idx_to_time_ms(active_sample)
            active_item = next(
                (
                    item
                    for item in slices
                    if self._same_time(item.time_ms, active_ms)
                ),
                None,
            )
        if active_item is None:
            active_item = slices[0]
        self._orthogonal_slice_state = OrthogonalSliceState(
            inline_index=il,
            crossline_index=xl,
            time_slices=slices,
            active_time_ms=active_item.time_ms,
            time_opacity=state.time_opacity,
        )
        self._slice_state_warning = (
            f"已丢弃 {dropped} 张越界 Time 切片"
            if dropped
            else ""
        )

    @property
    def depth_transform(self) -> DepthTransformState:
        return self._depth_transform

    @property
    def depth_available(self) -> bool:
        """True only when an authoritative (or explicitly opted-in) T-D transform exists."""
        return bool(self._depth_transform.available)

    def set_depth_transform(self, state: DepthTransformState) -> None:
        self._depth_transform = state

    def set_vertical_domain(self, domain: VerticalDomain) -> None:
        """Switch the scene-wide vertical domain (shared by 3D and 2D consumers).

        Fail-closed: Depth is refused when no time-depth transform is
        available — uniform scaling must never masquerade as depth.
        """
        if domain is self._domain:
            return
        if domain is VerticalDomain.DEPTH and not self._depth_transform.available:
            raise ValueError(
                "Depth domain unavailable: no time-depth transform "
                "(velocity model / checkshot / depth cube) is set"
            )
        self._domain = domain
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
        new_wells = list(wells)
        missing_ids = [well.name for well in new_wells if not well.id]
        if missing_ids:
            raise ValueError(
                "Every joint well requires a stable source JointWellId; "
                f"missing for: {', '.join(missing_ids)}"
            )
        new_ids = [JointWellId(str(well.id)) for well in new_wells if well.id]
        duplicate_ids = [
            well_id
            for well_id, count in Counter(new_ids).items()
            if count > 1
        ]
        if duplicate_ids:
            raise ValueError(
                "JointWellId values must be unique; duplicates: "
                + ", ".join(duplicate_ids)
            )

        previous_visibility = dict(self._well_visibility)
        self._wells = new_wells
        self._well_ids = new_ids
        self._well_visibility = {
            well_id: previous_visibility.get(well_id, True)
            for well_id in self._well_ids
        }
        self._td_tables = dict(td_tables or {})
        self._invalidate_traj()

    def well_presentations(self) -> list[JointWellPresentation]:
        """Return wells in source order with stable identities and unique labels."""
        counts = Counter(well.name for well in self._wells)
        occurrences: Counter[str] = Counter()
        presentations: list[JointWellPresentation] = []
        for well_id, well in zip(self._well_ids, self._wells, strict=True):
            occurrences[well.name] += 1
            display_name = well.name
            if counts[well.name] > 1:
                display_name = f"{well.name} ({occurrences[well.name]})"
            presentations.append(
                JointWellPresentation(
                    id=well_id,
                    name=well.name,
                    display_name=display_name,
                    visible=self._well_visibility.get(well_id, True),
                )
            )
        return presentations

    def set_well_visibility(
        self, well_id: JointWellId | str, visible: bool
    ) -> None:
        """Set one well's presentation visibility without altering analysis data."""
        identity = JointWellId(str(well_id))
        if identity not in self._well_visibility:
            raise KeyError(identity)
        self._well_visibility[identity] = bool(visible)

    def well_trajectories(
        self, *, visible_only: bool = False
    ) -> dict[JointWellId, WellTrajectory3D]:
        if self._traj_cache is None:
            self._traj_cache = {}
            for well_id, well in zip(self._well_ids, self._wells, strict=True):
                td = self._td_tables.get(
                    str(well_id), self._td_tables.get(well.name)
                )
                traj = project_well_trajectory(
                    well,
                    domain=self._domain,
                    td=td,
                    depth_transform=self._depth_transform,
                )
                self._traj_cache[well_id] = traj
        if visible_only:
            return {
                well_id: trajectory
                for well_id, trajectory in self._traj_cache.items()
                if self._well_visibility.get(well_id, True)
            }
        return dict(self._traj_cache)

    def set_formation_tops(self, tops_by_well: dict[str, list[tuple[str, float]]]) -> None:
        """Tops as (name, z) already in active domain units (ms or m)."""
        self._tops_by_well = dict(tops_by_well)

    def set_well_curves(
        self, curves_by_well: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]]
    ) -> None:
        """curves_by_well[well][curve] = (md, values)."""
        self._curves_by_well = curves_by_well

    def gr_value_range(self) -> tuple[float, float] | None:
        """Return one robust P2–P98 GR range shared by all loaded wells."""
        samples: list[np.ndarray] = []
        for curves in self._curves_by_well.values():
            curve = _find_gr_curve(curves)
            if curve is None:
                continue
            values = np.asarray(curve[1], dtype=np.float64).reshape(-1)
            finite = values[np.isfinite(values)]
            if finite.size:
                samples.append(finite)
        if not samples:
            return None
        values = np.concatenate(samples)
        lo, hi = np.nanpercentile(values, [2.0, 98.0])
        return float(lo), float(hi)

    def gr_well_trajectories(
        self, *, visible_only: bool = False
    ) -> dict[JointWellId, WellGrTrajectory]:
        """Return well paths sampled at GR measurement depths."""
        tracks: dict[JointWellId, WellGrTrajectory] = {}
        base_trajectories = self.well_trajectories()
        for presentation, well in zip(
            self.well_presentations(), self._wells, strict=True
        ):
            if visible_only and not presentation.visible:
                continue
            curves = self._curves_by_well.get(
                presentation.id,
                self._curves_by_well.get(well.name, {}),
            )
            curve = _find_gr_curve(curves)
            td = self._td_tables.get(
                str(presentation.id), self._td_tables.get(well.name)
            )
            if curve is None or td is None:
                # No GR curve, or no TD table to place it in the seismic
                # vertical domain (Time or Depth both need the MD→TWT leg).
                points = base_trajectories[presentation.id].points
                values = np.full(len(points), np.nan, dtype=np.float64)
            else:
                md = np.asarray(curve[0], dtype=np.float64).reshape(-1)
                values = np.asarray(curve[1], dtype=np.float64).reshape(-1)
                count = min(md.size, values.size)
                md, values = md[:count], values[:count]
                keep = (
                    np.isfinite(md)
                    & (md >= 0.0)
                    & (md <= float(well.total_depth_m))
                )
                md, values = md[keep], values[keep]
                order = np.argsort(md, kind="stable")
                md, values = md[order], values[order]
                frac = md / max(float(well.total_depth_m), 1e-12)
                x = well.x + frac * (well.bottom_x - well.x)
                y = well.y + frac * (well.bottom_y - well.y)
                if self._domain is VerticalDomain.TIME:
                    z = np.asarray(td.md_to_time_ms(md), dtype=np.float64)
                else:
                    # Depth from MD goes through the TD table and the scene's
                    # (real) time-depth transform — MD itself is never used as
                    # scene depth for a deviated/measured-depth well.
                    twt = np.asarray(td.md_to_time_ms(md), dtype=np.float64)
                    z = np.asarray(
                        self._depth_transform.time_ms_to_depth_m(twt),
                        dtype=np.float64,
                    )
                points = np.column_stack([x, y, z])
            tracks[presentation.id] = WellGrTrajectory(
                id=presentation.id,
                name=well.name,
                display_name=presentation.display_name,
                points=points,
                gr_values=values,
            )
        return tracks

    def set_curve_names(self, names: list[str]) -> None:
        self._curve_names = list(names)[:2]

    def set_near_well_distance_m(self, distance_m: float) -> None:
        self._near_well_m = float(distance_m)

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def set_volume_access(self, access: VolumeAccess | None) -> None:
        self._rescale_slice_indices(self._volume, access)
        self._volume = access
        self._extract_cache.clear()
        self._rebuild_registration()
        self._reconcile_orthogonal_slice_state()

    def _rescale_slice_indices(
        self, old_access: VolumeAccess | None, new_access: VolumeAccess | None
    ) -> None:
        """Keep IL/XL slice indices physically stationary across LOD changes.

        Indices live in loaded-volume space, so a preview refinement (L0→L1)
        changes their meaning. Convert through the OLD registration into
        survey iline/xline numbers, then back through the NEW registration —
        without this the displayed plane jumps to a different physical line
        whenever the preview shape changes.
        """
        if old_access is None or new_access is None:
            return
        old_reg = self._registration
        if old_reg is None:
            return
        state = self._orthogonal_slice_state
        if state.inline_index is None and state.crossline_index is None:
            return
        new_shape = new_access.shape
        # Prefer the new access's EXPLICIT strides; inference is only a
        # fallback for volume objects that do not carry them.
        new_strides = getattr(new_access, "strides", None)
        try:
            if new_strides is not None:
                new_reg = VolumeRegistration(
                    survey=self._survey,
                    n_inline=int(new_shape[0]),
                    n_crossline=int(new_shape[1]),
                    n_sample=int(new_shape[2]),
                    strides=tuple(int(s) for s in new_strides),
                )
            else:
                new_reg = VolumeRegistration.from_survey_and_shape(
                    self._survey, new_shape
                )
        except ValueError:
            return
        il_num, xl_num = old_reg.volume_idx_to_il_xl(
            float(state.inline_index or 0), float(state.crossline_index or 0)
        )
        vi, vx = new_reg.il_xl_to_volume_idx(il_num, xl_num)
        il = int(max(0, min(new_shape[0] - 1, round(vi))))
        xl = int(max(0, min(new_shape[1] - 1, round(vx))))
        self._orthogonal_slice_state = OrthogonalSliceState(
            inline_index=il,
            crossline_index=xl,
            time_slices=state.time_slices,
            active_time_ms=state.active_time_ms,
            time_opacity=state.time_opacity,
        )

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
        # Source-backed previews expose the exact per-axis downsample stride;
        # registration maps through it instead of guessing from shape ratios.
        strides = getattr(self._volume, "strides", None)
        if strides is not None:
            strides = tuple(int(s) for s in strides)
            try:
                self._registration = VolumeRegistration(
                    survey=self._survey,
                    n_inline=int(self._volume.shape[0]),
                    n_crossline=int(self._volume.shape[1]),
                    n_sample=int(self._volume.shape[2]),
                    strides=strides,
                )
                return
            except ValueError:
                # Stride/shape mismatch: fall through to inference, which will
                # also raise if the shape is impossible for the survey.
                pass
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

    def clear_fences(self) -> None:
        """Drop all fences (e.g. when rebinding a different survey/project).

        Stale fence vertices are meaningless against a new survey and would
        otherwise silently clamp into invalid extraction strips.
        """
        self._fences = []
        self._active_fence_id = None
        self._extract_cache.clear()
        self._probe = None

    def set_fence_visible(self, fence_id: str, visible: bool) -> None:
        for f in self._fences:
            if f.id == fence_id:
                f.visible = visible
                return
        raise KeyError(fence_id)

    def add_well_to_well_fence(
        self, well_refs: list[JointWellId | str], *, name: str = "Wells"
    ) -> FenceSection:
        xy = []
        by_id = dict(zip(self._well_ids, self._wells, strict=True))
        name_counts = Counter(well.name for well in self._wells)
        by_unique_name = {
            well.name: well
            for well in self._wells
            if name_counts[well.name] == 1
        }
        for ref in well_refs:
            w = by_id.get(ref, by_unique_name.get(ref))
            if w is None:
                raise KeyError(ref)
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
            Kept as an extraction-time override for callers that manage their
            own domain; the workbench UI passes ``None`` so 2D and 3D share
            the single scene domain (the old #122 "2D stays Time" split is
            gone — both views must agree).
        """
        fence = self.active_fence()
        if fence is None or self._volume is None or self._survey is None:
            return None
        use_domain = domain if domain is not None else self._domain
        cache_key = (fence.id, use_domain, int(n_along))
        if cache_key in self._extract_cache:
            return self._extract_cache[cache_key]
        survey = self._survey
        if self._registration is None:
            self._rebuild_registration()
        registration = self._registration
        nt = getattr(self._volume, "shape", (0, 0, 0))[2]
        # Preview sample i represents native sample i*stride_t, so the axis
        # must span the FULL survey time range with spacing dt*stride_t —
        # arange(nt)*dt alone would compress the axis by the stride factor.
        stride_t = registration.strides[2] if registration is not None else 1
        times_native = survey.t0_ms + np.arange(nt) * (survey.dt_ms * stride_t)
        if use_domain is VerticalDomain.TIME:
            saxis = times_native
        else:
            saxis = self._depth_transform.time_ms_to_depth_m(times_native)
        if registration is None:
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

    def assemble_active_profile_wells(
        self, *, domain: VerticalDomain | None = None
    ) -> list[ProfileWellHit]:
        fence = self.active_fence()
        if fence is None:
            return []
        use_domain = domain if domain is not None else self._domain
        hits: list[ProfileWellHit] = []
        verts = fence.vertices_xy
        for presentation, well in zip(
            self.well_presentations(), self._wells, strict=True
        ):
            if not self._well_visibility.get(presentation.id, True):
                continue
            s, dist = _project_point_to_polyline(well.x, well.y, verts)
            if dist > self._near_well_m:
                continue
            curve_name, cmd, cval = self._pick_curve(
                presentation.id, fallback_name=well.name
            )
            curve_z = None
            if cmd is not None:
                if use_domain is VerticalDomain.DEPTH:
                    # Curve depth = TD(MD→TWT) then the active transform —
                    # never raw MD (which is a well-path parameter, not a
                    # seismic vertical coordinate).
                    td = self._td_tables.get(
                        str(presentation.id),
                        self._td_tables.get(well.name),
                    )
                    if td is not None and self._depth_transform.available:
                        twt = np.asarray(
                            td.md_to_time_ms(cmd), dtype=np.float64
                        )
                        curve_z = np.asarray(
                            self._depth_transform.time_ms_to_depth_m(twt),
                            dtype=np.float64,
                        )
                else:
                    td = self._td_tables.get(
                        str(presentation.id),
                        self._td_tables.get(well.name),
                    )
                    if td is not None:
                        curve_z = np.asarray(
                            td.md_to_time_ms(cmd), dtype=np.float64
                        )
            hits.append(
                ProfileWellHit(
                    id=presentation.id,
                    name=well.name,
                    display_name=presentation.display_name,
                    s_m=s,
                    distance_m=dist,
                    tops=list(
                        self._tops_in_domain(
                            self._tops_by_well.get(
                                presentation.id,
                                self._tops_by_well.get(well.name, []),
                            ),
                            use_domain,
                        )
                    ),
                    curve_name=curve_name,
                    curve_md=cmd,
                    curve_z=curve_z,
                    curve_values=cval,
                )
            )
        hits.sort(key=lambda h: h.s_m)
        return hits

    def _tops_in_domain(
        self,
        tops: list[tuple[str, float]],
        domain: VerticalDomain,
    ) -> list[tuple[str, float]]:
        """Tops are stored as TWT ms; convert to the requested display domain."""
        if domain is not VerticalDomain.DEPTH or not self._depth_transform.available:
            return tops
        return [
            (name, float(self._depth_transform.time_ms_to_depth_m(z)))
            for name, z in tops
        ]

    def _pick_curve(
        self, well_id: JointWellId | str, *, fallback_name: str
    ) -> tuple[str | None, np.ndarray | None, np.ndarray | None]:
        curves = self._curves_by_well.get(
            well_id, self._curves_by_well.get(fallback_name, {})
        )
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
                # Convert depth m → time ms via the active transform for the
                # sample axis; unavailable transforms raise (fail-closed).
                z = float(self._depth_transform.depth_m_to_time_ms(z))
            return self._registration.world_xyz_to_volume(
                p.x, p.y, z, domain="time"
            )
        return self._probe.slice_indices(self._survey)

    def world_to_render_xyz(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """Map world XY + domain Z to volume/render index space."""
        mapped = self.world_to_render_xyz_array(
            np.array([[x, y, z]], dtype=np.float64)
        )
        return float(mapped[0, 0]), float(mapped[0, 1]), float(mapped[0, 2])

    def world_to_render_xyz_array(self, points: np.ndarray) -> np.ndarray:
        """Vectorized world XY + domain Z → render index space, shape (N, 3)."""
        pts = np.asarray(points, dtype=np.float64)
        if pts.size == 0:
            return np.zeros((0, 3), dtype=np.float32)
        if pts.ndim == 1:
            pts = pts.reshape(1, 3)
        x = pts[:, 0]
        y = pts[:, 1]
        z = np.array(pts[:, 2], dtype=np.float64, copy=True)
        if self._registration is not None:
            if self._domain is VerticalDomain.DEPTH:
                z = np.asarray(
                    self._depth_transform.depth_m_to_time_ms(z), dtype=np.float64
                )
            vi, vx = self._registration.xy_to_volume_idx(x, y)
            vt = self._registration.time_ms_to_sample_idx(z)
            return np.column_stack((vi, vx, vt)).astype(np.float32)
        if self._survey is None:
            return pts.astype(np.float32)
        s = self._survey
        if self._domain is VerticalDomain.DEPTH:
            z = np.asarray(
                self._depth_transform.depth_m_to_time_ms(z), dtype=np.float64
            )
        il, xl = s.xy_to_il_xl(x, y)
        il_idx = (il - s.iline_start) / (s.iline_step or 1)
        xl_idx = (xl - s.xline_start) / (s.xline_step or 1)
        t_idx = (z - s.t0_ms) / s.dt_ms if s.dt_ms else z
        return np.column_stack((il_idx, xl_idx, t_idx)).astype(np.float32)

    def _require_volume(self) -> None:
        if self._volume is None:
            raise RuntimeError("No volume access set on WellSeismicScene")

    def _invalidate_traj(self) -> None:
        self._traj_cache = None


def _find_gr_curve(
    curves: dict[str, tuple[np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, np.ndarray] | None:
    aliases = {"GR", "GAMMA", "SGR", "CGR"}
    for name, curve in curves.items():
        if name.upper() in aliases:
            return curve
    return None


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
