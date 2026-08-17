"""Scene-level tests for survey mapping and Time-domain well projection (#58)."""

from __future__ import annotations

import numpy as np
import pytest

from geoviz_well_seismic_3d import (
    FenceSection,
    InMemoryVolumeAccess,
    JointWellId,
    TimeDepthTable,
    VerticalDomain,
    WellHead,
    WellSeismicScene,
    select_depth_transform,
    survey_from_corners,
)


# Local rectangular corners matching data/层位 + SEGY text header style:
# P1 IL1315 XL4165 (0, 0), P2 IL1315 XL4805 (12793, 0), P3 IL1725 XL4805 (12793, 16406)
P1 = (1315, 4165, 0.0, 0.0)
P2 = (1315, 4805, 12793.0, 0.0)
P3 = (1725, 4805, 12793.0, 16406.0)


def test_survey_from_corners_maps_xy_to_il_xl():
    survey = survey_from_corners(
        p1=P1, p2=P2, p3=P3, n_samples=901, dt_ms=2.0, t0_ms=0.0
    )
    il, xl = survey.xy_to_il_xl(0.0, 0.0)
    assert il == pytest.approx(1315.0, abs=0.5)
    assert xl == pytest.approx(4165.0, abs=0.5)

    il2, xl2 = survey.xy_to_il_xl(12793.0, 0.0)
    assert il2 == pytest.approx(1315.0, abs=0.5)
    assert xl2 == pytest.approx(4805.0, abs=0.5)

    il3, xl3 = survey.xy_to_il_xl(12793.0, 16406.0)
    assert il3 == pytest.approx(1725.0, abs=0.5)
    assert xl3 == pytest.approx(4805.0, abs=0.5)


def test_survey_roundtrip_il_xl_xy():
    survey = survey_from_corners(P1, P2, P3, n_samples=100, dt_ms=2.0)
    x, y = survey.il_xl_to_xy(1500.0, 4500.0)
    il, xl = survey.xy_to_il_xl(x, y)
    assert il == pytest.approx(1500.0, abs=0.5)
    assert xl == pytest.approx(4500.0, abs=0.5)


def test_scene_set_survey_from_corners_and_validate():
    scene = WellSeismicScene()
    scene.set_survey_from_corners(P1, P2, P3, n_samples=901, dt_ms=2.0)
    assert scene.survey is not None
    # Horizon-style validation: same corners should match
    ok, msg = scene.validate_against_corners(P1, P2, P3)
    assert ok is True
    assert msg == ""


def test_scene_validate_against_mismatched_corners():
    scene = WellSeismicScene()
    scene.set_survey_from_corners(P1, P2, P3, n_samples=100, dt_ms=2.0)
    bad = (1315, 4165, 100.0, 100.0)  # shifted origin
    ok, msg = scene.validate_against_corners(bad, P2, P3, tol_m=1.0)
    assert ok is False
    assert "mismatch" in msg.lower() or "differ" in msg.lower()


def test_well_trajectory_time_domain_with_td():
    scene = WellSeismicScene()
    scene.set_survey_from_corners(P1, P2, P3, n_samples=901, dt_ms=2.0)
    scene.set_vertical_domain(VerticalDomain.TIME)

    # Simple TD: 0 ms @ 0 m MD, 1000 ms @ 2000 m MD (linear)
    td = TimeDepthTable(
        well_name="A1",
        time_ms=np.array([0.0, 1000.0], dtype=np.float64),
        md_m=np.array([0.0, 2000.0], dtype=np.float64),
    )
    well = WellHead(
        name="A1",
        x=5288.67,
        y=8219.94,
        bottom_x=5288.67,
        bottom_y=8219.94,
        total_depth_m=2000.0,
        kb_m=0.0,
        id=JointWellId("source:a1"),
    )
    scene.set_wells([well], td_tables={"A1": td})

    traj = next(iter(scene.well_trajectories().values()))
    assert traj.has_td is True
    assert traj.warning is None
    assert traj.points.shape[1] == 3
    # Bottom should land near 1000 ms TWT
    assert traj.points[-1, 2] == pytest.approx(1000.0, abs=1.0)
    # XY stays at well location for vertical well
    assert traj.points[0, 0] == pytest.approx(5288.67)
    assert traj.points[-1, 0] == pytest.approx(5288.67)


def test_well_trajectory_missing_td_safe_behaviour():
    scene = WellSeismicScene()
    scene.set_survey_from_corners(P1, P2, P3, n_samples=100, dt_ms=2.0)
    scene.set_vertical_domain(VerticalDomain.TIME)
    well = WellHead(
        name="A2",
        x=1000.0,
        y=2000.0,
        bottom_x=1000.0,
        bottom_y=2000.0,
        total_depth_m=2100.0,
        id=JointWellId("source:a2"),
    )
    scene.set_wells([well], td_tables={})

    traj = next(iter(scene.well_trajectories().values()))
    assert traj.has_td is False
    assert traj.warning is not None
    # Only surface/wellhead point — no fabricated full-depth path in Time
    assert len(traj.points) == 1
    assert traj.points[0, 0] == pytest.approx(1000.0)
    assert traj.points[0, 1] == pytest.approx(2000.0)


def test_deviated_well_head_to_bottom_xy():
    scene = WellSeismicScene()
    scene.set_survey_from_corners(P1, P2, P3, n_samples=100, dt_ms=2.0)
    scene.set_vertical_domain(VerticalDomain.TIME)
    td = TimeDepthTable(
        well_name="A10",
        time_ms=np.array([0.0, 500.0, 1000.0], dtype=np.float64),
        md_m=np.array([0.0, 1000.0, 2000.0], dtype=np.float64),
    )
    well = WellHead(
        name="A10",
        x=10547.09,
        y=11754.19,
        bottom_x=10457.533,
        bottom_y=11189.500,
        total_depth_m=2000.0,
        id=JointWellId("source:a10"),
    )
    scene.set_wells([well], td_tables={"A10": td})
    pts = next(iter(scene.well_trajectories().values())).points
    assert pts[0, 0] == pytest.approx(10547.09)
    assert pts[0, 1] == pytest.approx(11754.19)
    assert pts[-1, 0] == pytest.approx(10457.533)
    assert pts[-1, 1] == pytest.approx(11189.500)


def test_volume_access_injectable_slice():
    vol = np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4)
    access = InMemoryVolumeAccess(vol)
    scene = WellSeismicScene()
    scene.set_volume_access(access)
    sl = scene.slice_inline(0)
    assert sl.shape == (3, 4)
    assert sl[0, 0] == pytest.approx(0.0)
    sl_xl = scene.slice_crossline(1)
    assert sl_xl.shape == (2, 4)
    sl_t = scene.slice_time(2)
    assert sl_t.shape == (2, 3)


def test_scene_default_vertical_domain_is_time():
    scene = WellSeismicScene()
    assert scene.vertical_domain is VerticalDomain.TIME


def test_set_depth_transform_invalidates_traj_and_extract_caches():
    """#672: swapping V0 must recompute cached Depth-domain geometry."""
    scene = WellSeismicScene()
    scene.set_survey_from_corners(P1, P2, P3, n_samples=20, dt_ms=2.0)
    scene.set_volume_access(InMemoryVolumeAccess(np.zeros((2, 3, 20), dtype=np.float32)))
    scene.set_depth_transform(select_depth_transform(constant_v0=True, v0_m_s=3000.0))
    scene.set_vertical_domain(VerticalDomain.DEPTH)

    td = TimeDepthTable(
        well_name="A1",
        time_ms=np.array([0.0, 1000.0], dtype=np.float64),
        md_m=np.array([0.0, 2000.0], dtype=np.float64),
    )
    well = WellHead(
        name="A1",
        x=5288.67,
        y=8219.94,
        bottom_x=5288.67,
        bottom_y=8219.94,
        total_depth_m=2000.0,
        kb_m=0.0,
        id=JointWellId("source:a1"),
    )
    scene.set_wells([well], td_tables={"A1": td})
    scene.add_fence(FenceSection(name="f", vertices_xy=np.array([[0.0, 0.0], [1000.0, 0.0]])))

    traj_v0 = next(iter(scene.well_trajectories().values()))
    ext_v0 = scene.extract_active_fence(n_along=8)
    assert ext_v0 is not None
    z_v0 = float(traj_v0.points[-1, 2])
    assert z_v0 == pytest.approx(1500.0, rel=1e-6)  # 1000 ms * 3000 / 2 / 1000

    scene.set_depth_transform(select_depth_transform(constant_v0=True, v0_m_s=2000.0))
    traj_v1 = next(iter(scene.well_trajectories().values()))
    ext_v1 = scene.extract_active_fence(n_along=8)
    assert ext_v1 is not None
    assert float(traj_v1.points[-1, 2]) == pytest.approx(z_v0 * (2000.0 / 3000.0), rel=1e-6)
    np.testing.assert_allclose(ext_v1.sample_axis, ext_v0.sample_axis * (2000.0 / 3000.0))
