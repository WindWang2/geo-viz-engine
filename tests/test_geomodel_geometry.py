"""Tests for the headless geological-model geometry promoted into geoviz_plots.geomodel.

阶段 1 engine sink-down: these algorithms used to live in
``paleo_workbench/viz/geomodel/{engine,borehole_tunnel,fault_dislocation}.py``.
"""

from __future__ import annotations

import numpy as np
import pytest

from geoviz_plots.geomodel import (
    BoreholeTraceGenerator,
    FaultCuttingEngine,
    TunnelMeshGenerator,
    generate_cylinder_geometry,
    generate_fault_geometry,
    generate_tube_geometry,
    get_seam_boundaries,
)


class TestPrimitives:
    def test_cylinder_has_tube_and_caps(self):
        verts, faces, colors = generate_cylinder_geometry((0, 0, 0), (0, 0, 10), radius=2.0, resolution=8)
        # 8 rings x 2 ends + 2 cap centres
        assert verts.shape == (18, 3)
        # 2 tube triangles + 2 cap triangles per radial step
        assert faces.shape == (32, 3)
        assert colors.shape == (32, 4)
        assert faces.max() < len(verts)

    def test_cylinder_radius_is_respected(self):
        verts, _, _ = generate_cylinder_geometry((0, 0, 0), (0, 0, 10), radius=3.0, resolution=12)
        # Drop the two cap centres, then every tube vertex sits on the radius.
        radial = np.linalg.norm(verts[:-2, :2], axis=1)
        assert np.allclose(radial, 3.0, atol=1e-5)

    def test_cylinder_degenerate_returns_empty(self):
        verts, faces, colors = generate_cylinder_geometry((1, 2, 3), (1, 2, 3))
        assert verts.shape == (0, 3)
        assert faces.shape == (0, 3)
        assert colors.shape == (0, 4)

    def test_cylinder_survives_x_aligned_axis(self):
        """The orthonormal-basis seed flips when |axis.x| >= 0.9; both branches must work."""
        for p2 in [(10, 0, 0), (0, 0, 10)]:
            verts, faces, _ = generate_cylinder_geometry((0, 0, 0), p2, radius=1.0, resolution=6)
            assert np.isfinite(verts).all()
            assert len(faces) > 0

    def test_tube_follows_polyline(self):
        path = [(0, 0, 0), (0, 0, -10), (5, 0, -20)]
        verts, faces, colors = generate_tube_geometry(path, radius=1.5, resolution=6)
        assert verts.shape == (len(path) * 6, 3)
        assert faces.shape == ((len(path) - 1) * 6 * 2, 3)
        assert colors.shape == (len(faces), 4)
        assert np.isfinite(verts).all()

    def test_tube_needs_two_points(self):
        verts, faces, _ = generate_tube_geometry([(0, 0, 0)])
        assert verts.shape == (0, 3)
        assert faces.shape == (0, 3)

    def test_tube_handles_duplicate_stations(self):
        verts, _, _ = generate_tube_geometry([(0, 0, 0), (0, 0, 0), (0, 0, -5)], radius=1.0, resolution=4)
        assert np.isfinite(verts).all()

    def test_fault_surface_grid_and_throw(self):
        verts, faces, colors = generate_fault_geometry(nx=10, ny=8)
        assert verts.shape == (80, 3)
        assert faces.shape == (2 * 9 * 7, 3)
        assert colors.shape == (len(faces), 4)
        # The throw is +25 on one side, so the Z range must exceed the 15-amplitude dome.
        assert np.ptp(verts[:, 2]) > 25.0


class TestSeamBoundaries:
    def test_flat_fields_win(self):
        assert get_seam_boundaries(
            {"seam_1_top": -5.0, "seam_1_bottom": -12.0, "seam_3_top": -90.0, "seam_3_bottom": -99.0}
        ) == (-5.0, -12.0, -90.0, -99.0)

    def test_nested_seams_fallback(self):
        data = {"seams": {"seam 1": {"top": -1.0, "bottom": -2.0}, "seam 3": {"top": -30.0, "bottom": -33.0}}}
        assert get_seam_boundaries(data) == (-1.0, -2.0, -30.0, -33.0)

    def test_defaults_when_absent(self):
        assert get_seam_boundaries({}) == (0.0, -10.0, -100.0, -110.0)


class TestBoreholeTraceGenerator:
    def test_vertical_well_splits_at_every_seam(self):
        well = {
            "name": "W1",
            "trajectory": [[0, 0, 10], [0, 0, -120]],
            "seam_1_top": 0.0,
            "seam_1_bottom": -10.0,
            "seam_3_top": -100.0,
            "seam_3_bottom": -110.0,
        }
        (result,) = BoreholeTraceGenerator.generate_segments([well])
        assert result["well_id"] == "W1"
        assert [s["type"] for s in result["segments"]] == [
            "above_seam_1",
            "seam_1",
            "between_seam_1_and_3",
            "seam_3",
            "below_seam_3",
        ]

    def test_segments_are_contiguous(self):
        well = {"name": "W1", "trajectory": [[0, 0, 10], [0, 0, -120]]}
        (result,) = BoreholeTraceGenerator.generate_segments([well])
        segments = result["segments"]
        for prev, nxt in zip(segments, segments[1:]):
            assert np.allclose(prev["points"][-1], nxt["points"][0])

    def test_deviated_well_interpolates_xy_at_crossings(self):
        well = {
            "name": "D1",
            "trajectory": [[0, 0, 0], [100, 50, -100]],
            "seam_1_top": 0.0,
            "seam_1_bottom": -50.0,
            "seam_3_top": -80.0,
            "seam_3_bottom": -90.0,
        }
        (result,) = BoreholeTraceGenerator.generate_segments([well])
        crossing = next(
            s["points"][0] for s in result["segments"] if s["type"] == "between_seam_1_and_3"
        )
        # Z = -50 is halfway down, so X/Y must be halfway across.
        assert np.allclose(crossing, [50.0, 25.0, -50.0])

    def test_too_short_trajectory_yields_no_segments(self):
        for trajectory in ([], [[0, 0, 0]], [[0, 0, 0], [0, 0, 0]]):
            (result,) = BoreholeTraceGenerator.generate_segments(
                [{"name": "W", "trajectory": trajectory}]
            )
            assert result["segments"] == []

    def test_missing_trajectory_key(self):
        (result,) = BoreholeTraceGenerator.generate_segments([{"name": "W"}])
        assert result == {"well_id": "W", "segments": []}

    def test_id_preferred_over_name(self):
        (result,) = BoreholeTraceGenerator.generate_segments(
            [{"id": "ID", "name": "NAME", "trajectory": [[0, 0, 0], [0, 0, -5]]}]
        )
        assert result["well_id"] == "ID"


class TestTunnelMeshGenerator:
    def test_straight_tube_shape_and_radius(self):
        trajectory = np.array([[0, 0, 0], [0, 0, -10], [0, 0, -20]], dtype=float)
        verts, faces = TunnelMeshGenerator.generate_tube(trajectory, radius=2.0, segments=6)
        assert verts.shape == (3 * 6, 3)
        assert faces.shape == (2 * 6 * 2, 3)
        # Every vertex sits exactly `radius` from its station axis.
        for i in range(3):
            ring = verts[i * 6 : (i + 1) * 6]
            assert np.allclose(np.linalg.norm(ring - trajectory[i], axis=1), 2.0)

    def test_rmf_frame_is_twist_free_on_a_curve(self):
        t = np.linspace(0, np.pi, 12)
        trajectory = np.column_stack([np.cos(t) * 20, np.sin(t) * 20, -t * 5])
        verts, _ = TunnelMeshGenerator.generate_tube(trajectory, radius=1.0, segments=8)
        assert np.isfinite(verts).all()
        # Consecutive ring-0 vertices must not jump — a twisting frame would.
        ring0 = verts[0::8]
        steps = np.linalg.norm(np.diff(ring0, axis=0), axis=1)
        assert steps.max() < 4.0 * steps.min()

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"radius": 0.0}, "Radius must be positive"),
            ({"radius": -1.0}, "Radius must be positive"),
            ({"radius": 1.0, "segments": 2}, "Segments must be at least 3"),
        ],
    )
    def test_rejects_bad_parameters(self, kwargs, message):
        trajectory = np.array([[0, 0, 0], [0, 0, -1]], dtype=float)
        with pytest.raises(ValueError, match=message):
            TunnelMeshGenerator.generate_tube(trajectory, **kwargs)

    def test_rejects_bad_trajectory(self):
        with pytest.raises(ValueError, match="at least 2 points"):
            TunnelMeshGenerator.generate_tube(np.array([[0, 0, 0]], dtype=float), radius=1.0)
        with pytest.raises(ValueError, match=r"shape \(N, 3\)"):
            TunnelMeshGenerator.generate_tube(np.zeros((4, 2)), radius=1.0)


class TestFaultCuttingEngine:
    PLANE_POINT_NORMAL = ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))

    def test_rigid_throw_moves_only_positive_side(self):
        pts = np.array([[0, 0, 5.0], [0, 0, -5.0]])
        out = FaultCuttingEngine.apply_dislocation(
            pts, self.PLANE_POINT_NORMAL, np.array([0.0, 0.0, 10.0])
        )
        assert np.allclose(out[0], [0, 0, 15.0])
        assert np.allclose(out[1], [0, 0, -5.0])

    def test_split_throw_moves_both_sides_by_half(self):
        pts = np.array([[0, 0, 5.0], [0, 0, -5.0]])
        out = FaultCuttingEngine.apply_dislocation(
            pts, self.PLANE_POINT_NORMAL, np.array([0.0, 0.0, 10.0]), split_throw=True
        )
        assert np.allclose(out[0], [0, 0, 10.0])
        assert np.allclose(out[1], [0, 0, -10.0])

    def test_abcd_plane_form_matches_point_normal_form(self):
        pts = np.array([[0, 0, 5.0], [0, 0, -5.0]])
        throw = np.array([0.0, 0.0, 10.0])
        via_abcd = FaultCuttingEngine.apply_dislocation(pts, (0.0, 0.0, 1.0, 0.0), throw)
        via_pn = FaultCuttingEngine.apply_dislocation(pts, self.PLANE_POINT_NORMAL, throw)
        assert np.allclose(via_abcd, via_pn)

    def test_input_shape_is_preserved(self):
        grid = np.zeros((4, 5, 3))
        grid[..., 2] = np.linspace(-10, 10, 20).reshape(4, 5)
        out = FaultCuttingEngine.apply_dislocation(
            grid, self.PLANE_POINT_NORMAL, np.array([0.0, 0.0, 1.0])
        )
        assert out.shape == grid.shape

    @pytest.mark.parametrize("style", ["linear", "exponential", "gaussian"])
    def test_decay_tapers_to_zero_at_the_edge(self, style):
        # Points at |z| = 0, 5, 10 with a 10-unit decay zone.
        pts = np.array([[0, 0, 0.5], [0, 0, 5.0], [0, 0, 10.0]])
        out = FaultCuttingEngine.apply_dislocation(
            pts,
            self.PLANE_POINT_NORMAL,
            np.array([0.0, 0.0, 100.0]),
            decay_distance=10.0,
            decay_style=style,
        )
        displacement = out[:, 2] - pts[:, 2]
        # Monotonically decreasing, and exactly zero at/outside the decay distance.
        assert displacement[0] > displacement[1] > displacement[2]
        assert displacement[2] == pytest.approx(0.0)

    def test_per_point_throw_vector(self):
        pts = np.array([[0, 0, 1.0], [0, 0, 2.0]])
        throw = np.array([[0, 0, 10.0], [0, 0, 20.0]])
        out = FaultCuttingEngine.apply_dislocation(pts, self.PLANE_POINT_NORMAL, throw)
        assert np.allclose(out[:, 2], [11.0, 22.0])

    @pytest.mark.parametrize(
        ("kwargs", "exc"),
        [
            ({"fault_plane": [(0, 0, 0), (0, 0, 1)]}, TypeError),
            ({"fault_plane": ((0, 0, 0),)}, ValueError),
            ({"fault_plane": (0.0, 0.0, 0.0, 5.0)}, ValueError),
            ({"throw_vector": np.zeros((7, 3))}, ValueError),
            ({"decay_distance": -1.0}, ValueError),
            ({"decay_distance": 5.0, "decay_style": "cubic"}, ValueError),
        ],
    )
    def test_rejects_bad_inputs(self, kwargs, exc):
        call = {
            "surface_points": np.array([[0, 0, 1.0], [0, 0, -1.0]]),
            "fault_plane": self.PLANE_POINT_NORMAL,
            "throw_vector": np.array([0.0, 0.0, 1.0]),
        }
        call.update(kwargs)
        with pytest.raises(exc):
            FaultCuttingEngine.apply_dislocation(**call)

    def test_rejects_non_3d_points(self):
        with pytest.raises(ValueError, match="last dimension"):
            FaultCuttingEngine.apply_dislocation(
                np.zeros((5, 2)), self.PLANE_POINT_NORMAL, np.array([0.0, 0.0, 1.0])
            )
