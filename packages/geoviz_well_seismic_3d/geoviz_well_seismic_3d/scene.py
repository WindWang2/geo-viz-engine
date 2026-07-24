"""WellSeismicScene — primary public seam for joint well–seismic analysis."""

from __future__ import annotations

from .models import TimeDepthTable, VerticalDomain, WellHead, WellTrajectory3D
from .survey import Corner, SurveySpec, survey_from_corners
from .volume_access import VolumeAccess
from .well_geometry import project_well_trajectory


class WellSeismicScene:
    """Joint scene graph state (survey, wells, domain, injectable volume).

    Visualization widgets observe this object; geometry/projection algorithms
    live here so tests do not need OpenGL.
    """

    def __init__(self) -> None:
        self._survey: SurveySpec | None = None
        self._domain: VerticalDomain = VerticalDomain.TIME
        self._wells: list[WellHead] = []
        self._td_tables: dict[str, TimeDepthTable] = {}
        self._volume: VolumeAccess | None = None
        self._traj_cache: dict[str, WellTrajectory3D] | None = None

    # ------------------------------------------------------------------
    # Survey
    # ------------------------------------------------------------------

    @property
    def survey(self) -> SurveySpec | None:
        return self._survey

    def set_survey(self, survey: SurveySpec) -> None:
        self._survey = survey
        self._invalidate_traj()

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
        """Check that horizon-style corners match the active survey within tolerance."""
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
    # Vertical domain
    # ------------------------------------------------------------------

    @property
    def vertical_domain(self) -> VerticalDomain:
        return self._domain

    def set_vertical_domain(self, domain: VerticalDomain) -> None:
        if domain is self._domain:
            return
        self._domain = domain
        self._invalidate_traj()

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
                self._traj_cache[well.name] = project_well_trajectory(
                    well, domain=self._domain, td=td
                )
        return self._traj_cache

    # ------------------------------------------------------------------
    # Volume access
    # ------------------------------------------------------------------

    def set_volume_access(self, access: VolumeAccess | None) -> None:
        self._volume = access

    @property
    def volume_access(self) -> VolumeAccess | None:
        return self._volume

    def slice_inline(self, il_index: int):
        self._require_volume()
        return self._volume.slice_inline(il_index)

    def slice_crossline(self, xl_index: int):
        self._require_volume()
        return self._volume.slice_crossline(xl_index)

    def slice_time(self, sample_index: int):
        self._require_volume()
        return self._volume.slice_time(sample_index)

    def _require_volume(self) -> None:
        if self._volume is None:
            raise RuntimeError("No volume access set on WellSeismicScene")

    def _invalidate_traj(self) -> None:
        self._traj_cache = None
