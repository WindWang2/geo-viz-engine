"""TimeDepthTable range honesty (scientific V6 §8 / audit P1-4).

The repo's calibration policy is fail-closed: interpolate ONLY inside the
calibrated range. The engine table used to clamp ("extrapolates with edge
values"), fabricating a constant-TWT trajectory tail for wells deeper than
their TD table — contradicting the workbench's TimeDepthCalibration, which
returns None out of range.
"""

from __future__ import annotations

import numpy as np
import pytest

from geoviz_well_seismic_3d.models import TimeDepthTable
from geoviz_well_seismic_3d.well_geometry import _project_time
from geoviz_well_seismic_3d.models import WellHead


def _table() -> TimeDepthTable:
    return TimeDepthTable(
        well_name="W-1",
        md_m=np.array([0.0, 1000.0, 2000.0]),
        time_ms=np.array([0.0, 1000.0, 2000.0]),
    )


def _well(total_depth: float = 3500.0) -> WellHead:
    return WellHead(
        id="w1",
        name="W-1",
        x=0.0,
        y=0.0,
        bottom_x=0.0,
        bottom_y=0.0,
        kb_m=0.0,
        total_depth_m=total_depth,
    )


class TestTableRangeHonesty:
    def test_inside_range_interpolates(self):
        td = _table()
        assert td.md_to_time_ms(500.0) == pytest.approx(500.0)
        assert td.time_ms_to_md(1500.0) == pytest.approx(1500.0)

    def test_outside_range_is_nan_not_clamped(self):
        td = _table()
        assert np.isnan(td.md_to_time_ms(2500.0))  # was: clamped to 2000.0
        assert np.isnan(td.md_to_time_ms(-10.0))
        assert np.isnan(td.time_ms_to_md(3000.0))
        assert np.isnan(td.time_ms_to_md(-5.0))

    def test_array_input_masks_outside_range(self):
        td = _table()
        out = np.asarray(td.md_to_time_ms(np.array([500.0, 2500.0])))
        assert out[0] == pytest.approx(500.0)
        assert np.isnan(out[1])

    def test_md_range_property(self):
        td = _table()
        assert td.md_range == (0.0, 2000.0)


class TestTrajectoryTruncation:
    def test_trajectory_truncated_to_calibrated_range_with_warning(self):
        td = _table()  # calibrates to 2000 m; well TD is 3500 m
        traj = _project_time(_well(total_depth=3500.0), td=td, n_samples=64)
        assert traj.has_td
        assert traj.points.shape[0] >= 2
        # no fabricated constant-TWT tail: max TWT stays at table max
        assert float(np.nanmax(traj.points[:, 2])) == pytest.approx(2000.0)
        assert traj.warning and "2000" in traj.warning

    def test_fully_calibrated_well_has_no_truncation_warning(self):
        td = _table()
        traj = _project_time(_well(total_depth=2000.0), td=td, n_samples=32)
        assert traj.warning is None
        assert float(np.nanmax(traj.points[:, 2])) == pytest.approx(2000.0)
