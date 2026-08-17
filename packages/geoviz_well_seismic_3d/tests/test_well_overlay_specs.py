"""#542: well overlay specs must be vectorized (no per-sample Python loop)."""
from __future__ import annotations

import time

import numpy as np
import pytest

from geoviz_well_seismic_3d import (
    JointWellId,
    TimeDepthTable,
    WellHead,
    WellSeismicScene,
)
from geoviz_well_seismic_3d.joint_widget import WellSeismicJointWidget

P1 = (1315, 4165, 0.0, 0.0)
P2 = (1315, 4805, 12793.0, 0.0)
P3 = (1725, 4805, 12793.0, 16406.0)


def _scene_with_gr(n_wells: int, n_samples: int) -> WellSeismicScene:
    scene = WellSeismicScene()
    scene.set_survey_from_corners(P1, P2, P3, n_samples=901, dt_ms=2.0)
    wells = []
    tds = {}
    curves = {}
    for i in range(n_wells):
        name = f"W{i}"
        well_id = JointWellId(f"src:{name}")
        x = 1000.0 + 200.0 * i
        wells.append(
            WellHead(
                name=name,
                x=x,
                y=2000.0,
                bottom_x=x,
                bottom_y=2000.0,
                total_depth_m=2500.0,
                id=well_id,
            )
        )
        tds[name] = TimeDepthTable(
            well_name=name,
            time_ms=np.array([0.0, 2000.0], dtype=np.float64),
            md_m=np.array([0.0, 2500.0], dtype=np.float64),
        )
        md = np.linspace(0.0, 2500.0, n_samples)
        gr = np.linspace(40.0, 120.0, n_samples)
        if n_samples > 10:
            gr[n_samples // 2] = np.nan
        curves[name] = {"GR": (md, gr)}
    scene.set_wells(wells, td_tables=tds)
    scene.set_well_curves(curves)
    return scene


def _overlay_host(scene: WellSeismicScene) -> WellSeismicJointWidget:
    host = WellSeismicJointWidget.__new__(WellSeismicJointWidget)
    host._scene = scene
    host._overlay_specs_token = None
    host._overlay_specs_cached = None
    return host


def test_world_to_render_xyz_array_matches_scalar():
    scene = _scene_with_gr(1, 32)
    tracks = scene.gr_well_trajectories()
    points = next(iter(tracks.values())).points
    batched = scene.world_to_render_xyz_array(points)
    for i, (x, y, z) in enumerate(points):
        expect = scene.world_to_render_xyz(float(x), float(y), float(z))
        assert batched[i] == pytest.approx(expect, abs=1e-4)


def test_well_overlay_specs_match_scalar_reference():
    scene = _scene_with_gr(1, 40)
    host = _overlay_host(scene)
    specs = host.well_overlay_specs()
    assert len(specs) == 1
    spec = next(iter(specs.values()))
    track = next(iter(scene.gr_well_trajectories().values()))
    pos = scene.world_to_render_xyz_array(track.points)
    assert spec.positions.shape == ((len(pos) - 1) * 2, 3)
    np.testing.assert_allclose(spec.positions[0::2], pos[:-1], atol=1e-5)
    np.testing.assert_allclose(spec.positions[1::2], pos[1:], atol=1e-5)
    # NaN GR sample in the middle forces the two adjacent segments to missing.
    mid = 20
    missing = spec.colors[mid * 2]
    assert missing[3] == pytest.approx(1.0)
    assert spec.colors.shape[0] == spec.positions.shape[0]


def test_well_overlay_specs_large_tracks_are_fast():
    import inspect

    specs_src = inspect.getsource(WellSeismicJointWidget.well_overlay_specs)
    traj_src = inspect.getsource(WellSeismicJointWidget._traj_to_render)
    assert "for index in range(max(len(pos) - 1, 0))" not in specs_src
    assert "for i, (x, y, z)" not in traj_src

    scene = _scene_with_gr(5, 20_000)
    host = _overlay_host(scene)
    t0 = time.perf_counter()
    specs = host.well_overlay_specs()
    elapsed = time.perf_counter() - t0
    assert len(specs) == 5
    assert elapsed < 0.05, f"well_overlay_specs took {elapsed:.3f}s"
    t1 = time.perf_counter()
    again = host.well_overlay_specs()
    cached = time.perf_counter() - t1
    assert again is specs
    assert cached < 0.02
