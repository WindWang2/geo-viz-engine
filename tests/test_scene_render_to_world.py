"""Round-trip tests for WellSeismicScene.render_to_world_xyz_array (V5).

The inverse map must be the exact symmetric partner of
``world_to_render_xyz_array`` across registration strides, survey line
numbering steps, and the depth transform.
"""

from __future__ import annotations

import numpy as np
import pytest

from geoviz_well_seismic_3d.depth_transform import select_depth_transform
from geoviz_well_seismic_3d.models import VerticalDomain
from geoviz_well_seismic_3d.registration import VolumeRegistration
from geoviz_well_seismic_3d.scene import WellSeismicScene
from geoviz_well_seismic_3d.survey import survey_from_corners


def make_survey():
    return survey_from_corners(
        (100, 2000, 500000.0, 4000000.0),
        (100, 2100, 524000.0, 4020000.0),
        (200, 2100, 548000.0, 4034000.0),
        n_samples=200,
        dt_ms=4.0,
        t0_ms=100.0,
        iline_step=2,
        xline_step=2,
        n_inlines=51,
        n_crosslines=51,
    )


def make_scene(*, depth=False):
    scene = WellSeismicScene()
    survey = make_survey()
    scene.set_survey(survey)
    reg = VolumeRegistration.from_survey_and_shape(survey, (26, 26, 100))
    scene._rebuild_registration = lambda: None  # inject directly
    scene._registration = reg
    if depth:
        # transform first: set_vertical_domain refuses DEPTH without one
        scene.set_depth_transform(select_depth_transform(constant_v0=True, v0_m_s=2000.0))
        scene.set_vertical_domain(VerticalDomain.DEPTH)
    return scene


@pytest.mark.parametrize("depth", [False, True])
def test_round_trip_world_render_world(depth):
    scene = make_scene(depth=depth)
    rng = np.random.default_rng(42)
    world = np.column_stack(
        [
            rng.uniform(500000, 546000, 50),
            rng.uniform(4000000, 4033000, 50),
            rng.uniform(100, 900, 50) if not depth else rng.uniform(0, 1800, 50),
        ]
    )
    idx = scene.world_to_render_xyz_array(world)
    back = scene.render_to_world_xyz_array(idx)
    assert np.allclose(back, world, atol=1e-2)


def test_registration_stride_is_inverted_exactly():
    scene = make_scene()
    reg = scene.registration
    assert reg.strides[0] == 2  # fixture downsampled inlines
    world = np.array([[505000.0, 4010000.0, 300.0]])
    idx = scene.world_to_render_xyz_array(world)
    back = scene.render_to_world_xyz_array(idx)
    assert np.allclose(back, world, atol=1e-6)


def test_identity_without_survey():
    scene = WellSeismicScene()
    pts = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    out = scene.render_to_world_xyz_array(pts)
    assert np.allclose(out, pts)


def test_depth_without_transform_raises_symmetrically():
    scene = make_scene()
    # Simulate the inconsistent state directly: DEPTH domain without a
    # transform (set_vertical_domain refuses to create this state).
    scene._domain = VerticalDomain.DEPTH
    # forward raises (fail-closed)
    with pytest.raises(RuntimeError):
        scene.world_to_render_xyz_array(np.array([[505000.0, 4010000.0, 100.0]]))
    with pytest.raises(RuntimeError):
        scene.render_to_world_xyz_array(np.array([[5.0, 5.0, 5.0]]))


def test_scalar_wrapper():
    scene = make_scene()
    world = (505000.0, 4010000.0, 300.0)
    idx = scene.world_to_render_xyz_array(np.array([world]))[0]
    x, y, z = scene.render_to_world_xyz(float(idx[0]), float(idx[1]), float(idx[2]))
    assert (x, y, z) == pytest.approx(world, abs=1e-2)
