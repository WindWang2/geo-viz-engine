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


def test_index_xyz_to_world_sample0_at_box_top():
    """GL overlays must use Renderer3D time-down Z (sample 0 at top)."""
    from geoviz_seismic.renderer_3d import sample_to_z

    host = WellSeismicJointWidget.__new__(WellSeismicJointWidget)
    host._scene = None

    class _Renderer:
        _volume_spacing = (1.0, 1.0, 2.0)
        _volume_data_cpu = np.zeros((8, 9, 20), dtype=np.float32)

    host._renderer = _Renderer()
    world = host._index_xyz_to_world(np.array([[3.0, 4.0, 0.0], [3.0, 4.0, 19.0]]))
    assert world[0, 0] == pytest.approx(3.0)
    assert world[0, 1] == pytest.approx(4.0)
    assert world[0, 2] == pytest.approx(sample_to_z(0, 20, 2.0))
    assert world[1, 2] == pytest.approx(sample_to_z(19, 20, 2.0))
    assert world[0, 2] > world[1, 2]


def test_traj_without_renderer_stays_in_index_space():
    scene = _scene_with_gr(1, 32)
    host = _overlay_host(scene)
    track = next(iter(scene.gr_well_trajectories().values()))
    pos = host._traj_to_render(track.points)
    idx = scene.world_to_render_xyz_array(track.points)
    np.testing.assert_allclose(pos, idx, atol=1e-5)


def test_sync_from_scene_load_volume_uses_balanced_spacing():
    """Joint 3D cube must use the same axis-balanced spacing as SeismicView."""
    from geoviz_well_seismic_3d.volume_access import InMemoryVolumeAccess

    data = np.zeros((10, 20, 40), dtype=np.float32)
    scene = WellSeismicScene()
    scene.set_survey_from_corners(P1, P2, P3, n_samples=40, dt_ms=2.0)
    scene.set_volume_access(InMemoryVolumeAccess(data))

    host = WellSeismicJointWidget.__new__(WellSeismicJointWidget)
    host._scene = scene
    host._last_volume_key = None
    host._cmap_applied = False
    host._profile = None
    host._gr_legend = None
    host._well_items = []
    host._curtain_items = []
    host._probe_item = None
    host._overlay_specs_token = None
    host._overlay_specs_cached = None
    host._status = type("Status", (), {"setText": lambda self, text: None})()
    called = {}

    class _Renderer:
        _loaded = False

        def load_volume(self, arr, **kwargs):
            called["spacing"] = kwargs.get("spacing")
            called["shape"] = tuple(arr.shape)
            self._loaded = True

        def set_render_mode(self, mode):
            called["mode"] = mode

        def set_colormap(self, name):
            called["cmap"] = name

        def set_survey_mapping(self, **kwargs):
            called["survey"] = kwargs

    host._renderer = _Renderer()
    host.set_well_trajectories = lambda *args, **kwargs: None
    host.set_fence_curtains = lambda *args, **kwargs: None
    host.sync_orthogonal_slices = lambda: None
    host._sync_from_scene()
    assert called["shape"] == (10, 20, 40)
    # Same formula SeismicView uses: each axis maps to ~200 world units.
    assert called["spacing"] == pytest.approx((20.0, 10.0, 5.0))


def test_apply_survey_mapping_pushes_t0_dt_strides():
    host = WellSeismicJointWidget.__new__(WellSeismicJointWidget)
    scene = WellSeismicScene()
    scene.set_survey_from_corners(P1, P2, P3, n_samples=901, dt_ms=2.0)

    class _Vol:
        strides = (5, 4, 6)

    scene._volume = _Vol()
    host._scene = scene
    called = {}

    class _Renderer:
        def set_survey_mapping(self, **kwargs):
            called.update(kwargs)

    host._renderer = _Renderer()
    host._apply_survey_mapping()
    assert called["t0_ms"] == pytest.approx(0.0)
    assert called["dt_ms"] == pytest.approx(2.0)
    assert called["ds_factor"] == (5, 4, 6)


def test_set_well_trajectories_adds_gl_text_head_labels():
    """Well-head numbers must be GLTextItem (QLabel children never hit the GLES FBO)."""
    scene = _scene_with_gr(2, 16)
    host = _overlay_host(scene)
    added = []

    class _View:
        def addItem(self, item):
            added.append(item)

        def removeItem(self, item):
            pass

    class _Text:
        def __init__(self, pos=None, text="", color=None, **_kw):
            self.pos = pos
            self.text = text
            self.color = color

    class _GL:
        class GLLinePlotItem:
            def __init__(self, **_kw):
                pass

        class GLScatterPlotItem:
            def __init__(self, **_kw):
                pass

        GLTextItem = _Text

    host._gl = _GL
    host._renderer = type("R", (), {"_view": _View()})()
    host._well_items = []
    host._gr_legend = None
    host._name_chips = []
    host._update_gr_legend = lambda: None
    host.set_well_trajectories(scene.well_trajectories(visible_only=True))
    labels = [item.text for item in added if isinstance(item, _Text)]
    assert labels == ["W0", "W1"]
    for item in added:
        if isinstance(item, _Text):
            assert item.color[0] >= 200
            assert item.color[3] == 255


def test_well_name_chips_are_not_shown(qtbot):
    """QLabel chips duplicate GLTextItem names; they must stay hidden."""
    from PySide6.QtWidgets import QLabel, QWidget

    view = QWidget()
    view.resize(400, 300)
    qtbot.addWidget(view)
    view.show()
    leftover = QLabel("A1", view)
    leftover.show()
    host = WellSeismicJointWidget.__new__(WellSeismicJointWidget)
    host._renderer = type("R", (), {"_view": view})()
    host._name_chips = [leftover]
    host._gr_legend = None
    host._sync_well_name_chips()
    visible = [chip for chip in host._name_chips if chip.isVisible()]
    assert visible == []
    assert leftover.isVisible() is False
