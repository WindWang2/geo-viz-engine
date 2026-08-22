"""ActiveTimeSlice pierce points and well-order fence geometry."""

from __future__ import annotations

import numpy as np
import pytest

from geoviz_well_seismic_3d import (
    InMemoryVolumeAccess,
    JointWellId,
    TimeDepthTable,
    WellHead,
    WellSeismicScene,
)
from geoviz_well_seismic_3d.well_geometry import pierce_xy_at_z

P1 = (1315, 4165, 0.0, 0.0)
P2 = (1315, 4805, 12793.0, 0.0)
P3 = (1725, 4805, 12793.0, 16406.0)


def test_pierce_xy_interpolates_segment():
    points = np.array(
        [[0.0, 0.0, 0.0], [10.0, 20.0, 1000.0]],
        dtype=np.float64,
    )
    xy = pierce_xy_at_z(points, 250.0)
    assert xy is not None
    assert xy[0] == pytest.approx(2.5)
    assert xy[1] == pytest.approx(5.0)


def test_pierce_xy_none_outside_range():
    points = np.array([[0.0, 0.0, 100.0], [1.0, 1.0, 200.0]], dtype=np.float64)
    assert pierce_xy_at_z(points, 50.0) is None
    assert pierce_xy_at_z(points, 250.0) is None


def test_pierce_xy_hits_endpoint():
    points = np.array([[3.0, 4.0, 0.0], [5.0, 6.0, 100.0]], dtype=np.float64)
    xy = pierce_xy_at_z(points, 0.0)
    assert xy == pytest.approx((3.0, 4.0))


def _td(name: str, t_max: float = 1000.0, md_max: float = 2000.0) -> TimeDepthTable:
    return TimeDepthTable(
        well_name=name,
        time_ms=np.array([0.0, t_max], dtype=np.float64),
        md_m=np.array([0.0, md_max], dtype=np.float64),
    )


def _scene_with_two_wells(*, deviate: bool = False) -> WellSeismicScene:
    scene = WellSeismicScene()
    scene.set_survey_from_corners(P1, P2, P3, n_samples=101, dt_ms=10.0)
    scene.set_volume_access(
        InMemoryVolumeAccess(np.zeros((8, 8, 101), dtype=np.float32))
    )
    btm = (1200.0, 2500.0) if deviate else (1000.0, 2000.0)
    scene.set_wells(
        [
            WellHead(
                "A1",
                1000.0,
                2000.0,
                btm[0],
                btm[1],
                2000.0,
                id=JointWellId("source:a1"),
            ),
            WellHead(
                "B1",
                3000.0,
                4000.0,
                3000.0,
                4000.0,
                2000.0,
                id=JointWellId("source:b1"),
            ),
        ],
        td_tables={"A1": _td("A1"), "B1": _td("B1")},
    )
    return scene


def test_pierce_points_skip_missing_td_and_out_of_range():
    scene = _scene_with_two_wells()
    scene.set_wells(
        [
            WellHead(
                "A1", 1000, 2000, 1000, 2000, 2000, id=JointWellId("source:a1")
            ),
            WellHead(
                "C1", 5000, 6000, 5000, 6000, 2000, id=JointWellId("source:c1")
            ),
        ],
        td_tables={"A1": _td("A1", t_max=400.0)},
    )
    scene.update_time_slice(scene.orthogonal_slice_state.active_time_ms, 500.0)
    pierces = {p.well_id for p in scene.pierce_points_on_active_time()}
    assert pierces == set()


def test_pierce_points_at_mid_time_for_vertical_well():
    scene = _scene_with_two_wells()
    scene.update_time_slice(scene.orthogonal_slice_state.active_time_ms, 500.0)
    pierces = {p.well_id: p for p in scene.pierce_points_on_active_time()}
    a = pierces[JointWellId("source:a1")]
    assert a.x == pytest.approx(1000.0)
    assert a.y == pytest.approx(2000.0)
    assert a.z == pytest.approx(500.0, abs=10.0)
    assert a.display_name == "A1"


def test_append_unique_and_pop_rebuilds_pierce_path():
    scene = _scene_with_two_wells()
    scene.update_time_slice(scene.orthogonal_slice_state.active_time_ms, 500.0)
    assert scene.append_fence_well("A1") is True
    assert scene.append_fence_well("A1") is False
    assert scene.fences == []
    assert scene.append_fence_well(JointWellId("source:b1")) is True
    fence = scene.active_fence()
    assert fence is not None
    np.testing.assert_allclose(
        fence.vertices_xy,
        np.array([[1000.0, 2000.0], [3000.0, 4000.0]]),
        atol=1e-5,
    )
    popped = scene.pop_fence_well()
    assert popped == JointWellId("source:b1")
    assert scene.active_fence() is None
    assert scene.fence_well_ids == [JointWellId("source:a1")]


def test_well_order_fence_repeirces_when_time_moves():
    scene = _scene_with_two_wells(deviate=True)
    scene.update_time_slice(scene.orthogonal_slice_state.active_time_ms, 0.0)
    scene.add_well_to_well_fence(["A1", "B1"], name="path")
    at_zero = scene.active_fence().vertices_xy.copy()
    assert at_zero[0, 0] == pytest.approx(1000.0)
    scene.update_time_slice(scene.orthogonal_slice_state.active_time_ms, 1000.0)
    at_deep = scene.active_fence().vertices_xy
    assert at_deep[0, 0] == pytest.approx(1200.0)
    assert at_deep[0, 1] == pytest.approx(2500.0)
    assert at_deep[1, 0] == pytest.approx(3000.0)


def test_skipped_non_piercing_well_keeps_order():
    scene = _scene_with_two_wells()
    shallow = _td("A1", t_max=200.0)
    deep = _td("B1", t_max=1000.0)
    scene.set_wells(
        [
            WellHead(
                "A1", 1000, 2000, 1000, 2000, 2000, id=JointWellId("source:a1")
            ),
            WellHead(
                "B1", 3000, 4000, 3000, 4000, 2000, id=JointWellId("source:b1")
            ),
            WellHead(
                "C1", 5000, 6000, 5000, 6000, 2000, id=JointWellId("source:c1")
            ),
        ],
        td_tables={"A1": shallow, "B1": deep, "C1": deep},
    )
    scene.update_time_slice(scene.orthogonal_slice_state.active_time_ms, 100.0)
    scene.add_well_to_well_fence(["A1", "B1", "C1"])
    scene.update_time_slice(scene.orthogonal_slice_state.active_time_ms, 500.0)
    fence = scene.active_fence()
    assert fence is not None
    assert len(fence.vertices_xy) == 2
    np.testing.assert_allclose(
        fence.vertices_xy,
        np.array([[3000.0, 4000.0], [5000.0, 6000.0]]),
        atol=1e-5,
    )
    assert scene.fence_well_ids == [
        JointWellId("source:a1"),
        JointWellId("source:b1"),
        JointWellId("source:c1"),
    ]
