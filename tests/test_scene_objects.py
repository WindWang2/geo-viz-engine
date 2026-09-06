"""Headless tests for the named scene-object registry (geology-3d V5).

Covers the SceneObjectManager state machine (add/replace/remove/clear,
visibility/opacity/clip updates, bounds) and the CPU pick math with stub GL
items — no OpenGL context required.
"""

from __future__ import annotations

import numpy as np
import pytest

from geoviz_seismic.scene_objects import (
    PickHit,
    SceneObjectError,
    SceneObjectManager,
    ray_triangles_first_hit,
    screen_point_to_ray,
)


class StubItem:
    """Records constructor kwargs; mimics the pyqtgraph item surface used."""

    created = 0

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.visible = True
        self.removed = False
        self.calls: list[tuple] = []
        StubItem.created += 1

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def update(self):
        self.calls.append(("update",))

    def setData(self, **kwargs):  # noqa: N802
        self.calls.append(("setData", kwargs))

    def setColor(self, color):  # noqa: N802
        self.calls.append(("setColor", color))

    def setGLOptions(self, opts):  # noqa: N802
        self.calls.append(("setGLOptions", opts))

    def setMeshData(self, **kwargs):  # noqa: N802
        self.calls.append(("setMeshData", kwargs))


class StubGL:
    """Minimal pyqtgraph.opengl stand-in."""

    GLMeshItem = StubItem
    GLLinePlotItem = StubItem
    GLScatterPlotItem = StubItem
    GLTextItem = StubItem


class StubView:
    def __init__(self):
        self.added: list[object] = []
        self.removed: list[object] = []
        self.width = lambda: 800
        self.height = lambda: 600
        self.viewMatrix = lambda: None
        self.projectionMatrix = lambda: None

    def addItem(self, item):
        self.added.append(item)

    def removeItem(self, item):
        self.removed.append(item)
        self.added.remove(item)


@pytest.fixture()
def rig():
    view = StubView()
    mgr = SceneObjectManager(lambda: view, lambda: StubGL())
    return mgr, view


TRI_VERTS = np.array(
    [
        [0.0, 0.0, 0.0],
        [10.0, 0.0, 0.0],
        [0.0, 10.0, 0.0],
    ],
    dtype=np.float32,
)
TRI_FACES = np.array([[0, 1, 2]], dtype=np.int64)


def test_ray_triangle_hit_and_miss():
    hit = ray_triangles_first_hit(
        np.array([1.0, 1.0, 5.0]), np.array([0.0, 0.0, -1.0]), TRI_VERTS, TRI_FACES
    )
    assert hit is not None
    dist, face = hit
    assert face == 0
    assert dist == pytest.approx(5.0, abs=1e-6)

    # Outside the triangle (u+v > 1)
    assert (
        ray_triangles_first_hit(
            np.array([9.0, 9.0, 5.0]),
            np.array([0.0, 0.0, -1.0]),
            TRI_VERTS,
            TRI_FACES,
        )
        is None
    )
    # Parallel ray
    assert (
        ray_triangles_first_hit(
            np.array([1.0, 1.0, 5.0]),
            np.array([1.0, 0.0, 0.0]),
            TRI_VERTS,
            TRI_FACES,
        )
        is None
    )
    # Behind the origin (t < 0)
    assert (
        ray_triangles_first_hit(
            np.array([1.0, 1.0, -5.0]),
            np.array([0.0, 0.0, -1.0]),
            TRI_VERTS,
            TRI_FACES,
        )
        is None
    )
    # max_distance bounds the hit
    assert (
        ray_triangles_first_hit(
            np.array([1.0, 1.0, 5.0]),
            np.array([0.0, 0.0, -1.0]),
            TRI_VERTS,
            TRI_FACES,
            max_distance=1.0,
        )
        is None
    )


def test_add_mesh_replaces_atomically(rig):
    mgr, view = rig
    mgr.add_object("fault:a", verts=TRI_VERTS, faces=TRI_FACES, pickable=True, kind="fault")
    first_item = mgr.get("fault:a").item
    assert first_item in view.added

    mgr.add_object("fault:a", verts=TRI_VERTS, faces=TRI_FACES, pickable=True, kind="fault")
    second_item = mgr.get("fault:a").item
    assert first_item in view.removed
    assert second_item in view.added
    assert first_item not in view.added  # exactly one live item
    assert len(mgr) == 1


def test_validation_failures(rig):
    mgr, _ = rig
    with pytest.raises(SceneObjectError):
        mgr.add_object("x", verts=np.zeros((2, 4)), faces=np.zeros((1, 3), dtype=int))
    bad = np.array([[0, 0, np.nan], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    with pytest.raises(SceneObjectError):
        mgr.add_object("x", verts=bad, faces=np.array([[0, 1, 2]]))
    with pytest.raises(SceneObjectError):
        mgr.add_object(
            "x",
            verts=TRI_VERTS,
            faces=np.array([[0, 1, -7]]),  # negative index
        )
    with pytest.raises(SceneObjectError):
        mgr.add_object("x", verts=TRI_VERTS, faces=TRI_FACES, mode="wat")
    with pytest.raises(SceneObjectError):
        mgr.add_object("x", verts=TRI_VERTS, faces=TRI_FACES, kind="wat")
    with pytest.raises(SceneObjectError):
        mgr.add_object("x", verts=TRI_VERTS, faces=TRI_FACES, clip_planes=[(0, 0, 0, 1)])
    # mesh without faces
    with pytest.raises(SceneObjectError):
        mgr.add_object("x", verts=TRI_VERTS, faces=None, mode="mesh")


def test_visibility_opacity_color_updates(rig):
    mgr, _ = rig
    mgr.add_object(
        "vol:s1", verts=TRI_VERTS, faces=TRI_FACES, opacity=0.5, kind="volume"
    )
    obj = mgr.get("vol:s1")
    item = obj.item

    mgr.set_visibility("vol:s1", False)
    assert not obj.visible and not item.visible
    mgr.set_visibility("vol:s1", True)
    assert obj.visible and item.visible

    mgr.set_opacity("vol:s1", 0.25)
    # uniform-color meshes flip glOptions and re-color on opacity change
    assert ("setGLOptions", "translucent") in item.calls
    assert ("setColor", obj.color) in item.calls
    mgr.set_color("vol:s1", (0.2, 0.4, 0.8))
    assert obj.color[:3] == pytest.approx((0.2, 0.4, 0.8))

    with pytest.raises(KeyError):
        mgr.set_opacity("missing", 0.5)


def test_opacity_rescale_does_not_compound_face_colors(rig):
    mgr, _ = rig
    fc = np.full((1, 4), (1.0, 0.0, 0.0, 1.0), dtype=np.float32)
    mgr.add_object(
        "vol:fc", verts=TRI_VERTS, faces=TRI_FACES, face_colors=fc, kind="volume"
    )
    item = mgr.get("vol:fc").item
    mgr.set_opacity("vol:fc", 0.5)
    mgr.set_opacity("vol:fc", 0.2)
    mgr.set_opacity("vol:fc", 1.0)
    setmesh = [c for c in item.calls if c[0] == "setMeshData"]
    assert len(setmesh) == 3
    # Base face alpha must survive the round of rescales exactly (uploads are
    # always recomputed from the registry copy, never compounded).
    final = mgr._upload_face_colors(mgr.get("vol:fc"))
    assert np.allclose(final[:, 3], 1.0, atol=1e-6)
    assert np.allclose(mgr.get("vol:fc").face_colors[:, 3], 1.0, atol=1e-6)


def test_clip_planes_validation_and_dispatch(rig):
    mgr, _ = rig
    mgr.add_object("h:1", verts=TRI_VERTS, faces=TRI_FACES, kind="horizon")
    mgr.set_clip_planes("h:1", [(0.0, 0.0, -1.0, 5.0)])
    assert mgr.get("h:1").clip_planes == ((0.0, 0.0, -1.0, 5.0),)
    mgr.set_clip_planes("h:1", None)
    assert mgr.get("h:1").clip_planes is None
    with pytest.raises(SceneObjectError):
        mgr.set_clip_planes("h:1", [(1.0, 1.0, 1.0, 0.0)] * 7)


def test_bounds_and_clear_by_kind(rig):
    mgr, view = rig
    mgr.add_object("well:w1", verts=TRI_VERTS, faces=TRI_FACES, kind="well")
    mgr.add_object(
        "well:w2",
        verts=TRI_VERTS + np.array([5, 5, 5], dtype=np.float32),
        faces=TRI_FACES,
        kind="well",
    )
    mgr.add_object("fault:f1", verts=TRI_VERTS, faces=TRI_FACES, kind="fault")

    b = mgr.bounds(visible_only=True)
    assert b[0] == pytest.approx([0, 0, 0], abs=1e-6)
    assert b[1] == pytest.approx([15, 15, 5], abs=1e-6)
    hidden = mgr.bounds(kinds=["fault"], visible_only=False)
    assert hidden[1] == pytest.approx([10, 10, 0], abs=1e-6)

    assert mgr.clear(kind="well") == 2
    assert mgr.names() == ["fault:f1"]
    assert mgr.clear() == 1
    assert len(mgr) == 0
    assert mgr.bounds() is None


def test_pick_returns_nearest_object(rig):
    mgr, _ = rig
    # "far" sits 5 units deeper along the ray so the nearest-wins order is
    # deterministic.
    far_verts = TRI_VERTS - np.array([0.0, 0.0, 5.0], dtype=np.float32)
    mgr.add_object("far", verts=far_verts, faces=TRI_FACES, pickable=True)
    near_verts = np.array(
        [[1.0, 1.0, 0.0], [5.0, 1.0, 0.0], [1.0, 5.0, 0.0]], dtype=np.float32
    )
    mgr.add_object("near", verts=near_verts, faces=TRI_FACES, pickable=True)
    # invisible objects are not pickable
    mgr.add_object(
        "ghost",
        verts=near_verts - np.array([0.5, 0.5, 0.0], dtype=np.float32),
        faces=TRI_FACES,
        pickable=True,
        visible=False,
    )
    # unpickable objects are skipped
    mgr.add_object(
        "nopick",
        verts=near_verts / 2,
        faces=TRI_FACES,
        pickable=False,
    )

    hit = mgr.pick([1.0, 1.0, 5.0], [0.0, 0.0, -1.0])
    assert isinstance(hit, PickHit)
    assert hit.name == "near"
    assert hit.point[2] == pytest.approx(0.0, abs=1e-6)
    assert hit.distance == pytest.approx(5.0, abs=1e-6)

    assert mgr.pick([1.0, 1.0, 5.0], [0.0, 0.0, -1.0], kinds=["fault"]) is None


def test_pick_respects_kind_and_kind_filter(rig):
    mgr, _ = rig
    mgr.add_object("well:w", verts=TRI_VERTS, faces=TRI_FACES, pickable=True, kind="well")
    hit = mgr.pick([1.0, 1.0, 5.0], [0.0, 0.0, -1.0], kinds=["well"])
    assert hit is not None and hit.kind == "well"


def test_lines_points_objects_store_payload(rig):
    mgr, view = rig
    path = np.array([[0, 0, 0], [1, 1, 1], [2, 0, 2]], dtype=np.float32)
    mgr.add_object("well:dev", verts=path, mode="lines", kind="well", pickable=True)
    obj = mgr.get("well:dev")
    assert obj.faces is None
    assert obj.item.kwargs["pos"].shape == (3, 3)
    # lines are excluded from mesh picking but still counted in bounds
    assert mgr.pick([0.5, 0.5, 0.5], [0, 0, -1.0]) is None
    assert mgr.bounds() is not None


def test_view_absent_is_tolerated():
    mgr = SceneObjectManager(lambda: None, lambda: StubGL())
    mgr.add_object("x", verts=TRI_VERTS, faces=TRI_FACES)
    assert mgr.get("x").item is None  # registry state survives, no GL item
    assert mgr.bounds() is not None
    assert mgr.pick([1, 1, 5], [0, 0, -1]) is None
    assert mgr.remove_object("x") is True


def test_screen_point_to_ray_math():
    class FakeMat:
        def __init__(self, m):
            self.m = np.asarray(m, dtype=float)

        def __mul__(self, other):
            return FakeMat(self.m @ other.m)

        def inverted(self):
            inv = np.linalg.inv(self.m)
            return FakeMat(inv), True

        def map(self, v):
            out = self.m @ np.array([v.x(), v.y(), v.z(), v.w()])
            return FakeVec(out)

    class FakeVec:
        def __init__(self, v):
            self.v = v

        def x(self):
            return self.v[0]

        def y(self):
            return self.v[1]

        def z(self):
            return self.v[2]

        def w(self):
            return self.v[3]

    # Identity view + orthographic-ish projection over [-1,1]^2: center of the
    # widget looks straight down -z.
    ident = FakeMat(np.eye(4))
    proj = FakeMat(np.diag([1, 1, 1, 1]))
    ray = screen_point_to_ray(400, 300, 800, 600, ident, proj)
    assert ray is not None
    origin, direction = ray
    assert origin == pytest.approx([0, 0, -1], abs=1e-9)
    assert direction == pytest.approx([0, 0, 1], abs=1e-9)


def test_line_picking_with_radius(rig):
    mgr, _ = rig
    path = np.array([[0, 0, 0], [0, 0, -20]], dtype=np.float32)
    mgr.add_object(
        "well:line",
        verts=path,
        mode="lines",
        line_mode="line_strip",
        kind="well",
        pickable=True,
        pick_radius=1.5,
    )
    # ray passing 1 unit away from the line hits within the radius
    hit = mgr.pick([1.0, 0.0, -10.0], [-1.0, 0.0, 0.0])
    assert hit is not None and hit.name == "well:line"
    assert hit.point[2] == pytest.approx(-10.0, abs=1e-5)
    # lateral offset 1.0 (within radius 1.5) -> hit; 3.0 -> miss
    hit1 = mgr.pick([5.0, 1.0, -10.0], [-1.0, 0.0, 0.0])
    assert hit1 is not None
    assert mgr.pick([5.0, 3.0, -10.0], [-1.0, 0.0, 0.0]) is None
    # zero radius disables line picking
    mgr.add_object(
        "well:noline",
        verts=path,
        mode="lines",
        kind="well",
        pickable=True,
        pick_radius=0.0,
    )
    assert mgr.pick([1.0, 0.0, -10.0], [-1.0, 0.0, 0.0], kinds=["well"]) is not None


def test_bounds_of_names(rig):
    mgr, _ = rig
    mgr.add_object("a", verts=TRI_VERTS, faces=TRI_FACES)
    mgr.add_object(
        "b", verts=TRI_VERTS + np.array([5, 5, 5], dtype=np.float32), faces=TRI_FACES
    )
    b = mgr.bounds_of_names(["a"])
    assert b[1] == pytest.approx([10, 10, 0], abs=1e-6)
    ab = mgr.bounds_of_names(["a", "b"])
    assert ab[1] == pytest.approx([15, 15, 5], abs=1e-6)
    assert mgr.bounds_of_names(["missing"]) is None
